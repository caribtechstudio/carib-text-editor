"""
core/logging_setup.py — Journal technique et filet a exceptions.

Jusqu'ici, une exception non rattrapee laissait une fenetre morte et aucune
trace : impossible d'aider un utilisateur qui ecrit « ca plante ». Ce module
installe trois choses, le plus tot possible au demarrage :

  * un **journal tournant** dans `~/.carib/logs/`, borne a 1,5 Mo au total ;
  * des **gestionnaires d'exception** pour le thread principal, les threads
    de travail et la boucle asyncio de Flet ;
  * un **filtre de redaction** qui empeche une cle API de finir dans un
    fichier que l'utilisateur nous enverra par courriel.

Regle absolue : **le contenu des documents n'est jamais journalise.** Le
journal contient des noms de modules, des numeros de version et des traces
d'appel, rien d'autre. C'est ce qui permet de le documenter comme inoffensif
dans la politique de confidentialite.
"""

import logging
import logging.handlers
import os
import re
import sys
import threading
import traceback

_DATA_DIR = os.path.join(os.path.expanduser("~"), ".carib")
_LOG_DIR = os.path.join(_DATA_DIR, "logs")
_LOG_FILE = os.path.join(_LOG_DIR, "carib.log")

_MAX_BYTES = 512 * 1024
_BACKUPS = 2

_installed = False
_ui_reporter = None
#: Une seule fenetre d'erreur par session : un plantage dans une boucle de
#: rendu en produirait des centaines.
_reported = False
_lock = threading.Lock()

log = logging.getLogger("carib")


# ---------------------------------------------------------------------------
# Redaction
# ---------------------------------------------------------------------------

#: Motifs de secrets. Volontairement larges : un faux positif masque un mot
#: dans le journal, un faux negatif publie une cle.
_SECRET_PATTERNS = (
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{6,}"),
    re.compile(r"sk-[A-Za-z0-9_\-]{12,}"),
    re.compile(r"AIza[A-Za-z0-9_\-]{20,}"),
    re.compile(r"(?i)(bearer|authorization|x-api-key|api[_-]?key)"
               r"(\s*[:=]\s*|\s+)([A-Za-z0-9_\-\.]{8,})"),
)


def redact(text: str) -> str:
    """Remplace tout ce qui ressemble a un secret par « […] »."""
    if not text:
        return text
    out = text
    for pattern in _SECRET_PATTERNS[:3]:
        out = pattern.sub("[cle-masquee]", out)
    out = _SECRET_PATTERNS[3].sub(r"\1\2[masque]", out)
    return out


class _RedactingFilter(logging.Filter):
    """Passe chaque enregistrement par `redact` avant ecriture."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            if isinstance(record.msg, str):
                record.msg = redact(record.msg)
            if record.args:
                if isinstance(record.args, dict):
                    record.args = {k: redact(v) if isinstance(v, str) else v
                                   for k, v in record.args.items()}
                else:
                    record.args = tuple(
                        redact(a) if isinstance(a, str) else a
                        for a in record.args)
        except Exception:
            # Un filtre de journalisation ne doit jamais faire tomber
            # l'application qu'il est cense instrumenter.
            pass
        return True


# ---------------------------------------------------------------------------
# Installation
# ---------------------------------------------------------------------------

def install(version: str = "", *, level: int = logging.INFO) -> str:
    """Met en place le journal et les gestionnaires d'exception.

    Idempotent : un second appel ne fait rien. Retourne le chemin du journal
    (ou "" si le disque a refuse l'ecriture — l'application continue alors
    sans journal plutot que de ne pas demarrer).
    """
    global _installed
    with _lock:
        if _installed:
            return _LOG_FILE if os.path.isdir(_LOG_DIR) else ""
        _installed = True

    root = logging.getLogger()
    root.setLevel(level)

    try:
        os.makedirs(_LOG_DIR, exist_ok=True)
        handler = logging.handlers.RotatingFileHandler(
            _LOG_FILE, maxBytes=_MAX_BYTES, backupCount=_BACKUPS,
            encoding="utf-8", delay=True)
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)-7s %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"))
        handler.addFilter(_RedactingFilter())
        root.addHandler(handler)
        path = _LOG_FILE
    except OSError:
        path = ""

    # En developpement, la console reste la sortie la plus pratique. Dans
    # l'application empaquetee il n'y a pas de console (console=False).
    if sys.stderr is not None and not getattr(sys, "frozen", False):
        console = logging.StreamHandler()
        console.setFormatter(logging.Formatter("%(levelname)-7s %(name)s: %(message)s"))
        console.addFilter(_RedactingFilter())
        root.addHandler(console)

    _install_hooks()

    log.info("=" * 60)
    log.info("Carib %s demarre — Python %s sur %s",
             version or "?", sys.version.split()[0], sys.platform)
    return path


def _install_hooks() -> None:
    previous = sys.excepthook

    def hook(exc_type, exc, tb):
        if issubclass(exc_type, KeyboardInterrupt):
            previous(exc_type, exc, tb)
            return
        _report("Erreur inattendue", exc_type, exc, tb)
        previous(exc_type, exc, tb)

    sys.excepthook = hook

    def thread_hook(args):
        if issubclass(args.exc_type, SystemExit):
            return
        _report(f"Erreur dans le thread « {args.thread.name if args.thread else '?'} »",
                args.exc_type, args.exc_value, args.exc_traceback)

    threading.excepthook = thread_hook


def install_asyncio_handler(loop) -> None:
    """Rattache la boucle asyncio de Flet au meme journal.

    Sans cela, une coroutine qui echoue n'imprime qu'un avertissement dans
    une sortie standard inexistante.
    """
    def handler(_loop, context):
        exc = context.get("exception")
        message = context.get("message") or "erreur asyncio"
        if exc is not None:
            _report("Erreur asynchrone", type(exc), exc, exc.__traceback__)
        else:
            log.error("asyncio: %s", message)

    try:
        loop.set_exception_handler(handler)
    except Exception as exc:
        log.warning("Gestionnaire asyncio non installe : %s", exc)


def _report(title, exc_type, exc, tb) -> None:
    """Journalise, puis previent l'utilisateur une seule fois."""
    global _reported

    try:
        detail = "".join(traceback.format_exception(exc_type, exc, tb))
    except Exception:
        detail = f"{exc_type}: {exc}"
    log.critical("%s\n%s", title, detail)

    with _lock:
        if _reported or _ui_reporter is None:
            return
        _reported = True
        reporter = _ui_reporter

    try:
        reporter(title, f"{exc_type.__name__}: {exc}", _LOG_FILE)
    except Exception:
        log.exception("Le rapport d'erreur n'a pas pu etre affiche.")


# ---------------------------------------------------------------------------
# Interface
# ---------------------------------------------------------------------------

def set_ui_reporter(fn) -> None:
    """Enregistre la fonction qui affichera le dialogue d'erreur.

    Signature attendue : `fn(titre, message, chemin_du_journal)`. Elle est
    appelee depuis un thread quelconque : a la vue de gerer le retour sur le
    thread d'interface.
    """
    global _ui_reporter
    _ui_reporter = fn


def log_path() -> str:
    return _LOG_FILE


def log_dir() -> str:
    return _LOG_DIR


def read_tail(max_chars: int = 8000) -> str:
    """Fin du journal, pour l'afficher ou la copier dans un rapport de bogue."""
    try:
        with open(_LOG_FILE, "r", encoding="utf-8", errors="replace") as fh:
            content = fh.read()
    except OSError as exc:
        return f"(journal illisible : {exc})"
    return content[-max_chars:] if len(content) > max_chars else content


def clear() -> None:
    """Vide le journal et ses rotations — appele par « Effacer mes donnees »."""
    for suffix in ("", ".1", ".2"):
        try:
            os.remove(_LOG_FILE + suffix)
        except OSError:
            pass
