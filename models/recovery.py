"""
models/recovery.py — Récupération après arrêt anormal.

`session.json` ne suffit pas : il n'est écrit qu'à des moments choisis
(changement d'onglet, enregistrement, fermeture). Écrire pendant deux heures
sans jamais enregistrer, puis subir une coupure de courant, faisait perdre
tout le travail.

Ce module tient un **journal** des documents modifiés, réécrit périodiquement
tant qu'il reste des changements en attente. Le fichier est supprimé lors
d'une fermeture propre : le retrouver au démarrage signifie donc, et
seulement, que la session précédente s'est mal terminée.
"""

import json
import os
import threading
import time

from models.scheduler import scheduler

_DATA_DIR = os.path.join(os.path.expanduser("~"), ".carib")
_RECOVERY_FILE = os.path.join(_DATA_DIR, "recovery.json")

#: Fréquence d'écriture du journal tant qu'il reste des modifications.
#: 15 s borne la perte maximale ; assez rare pour rester invisible.
JOURNAL_INTERVAL = 15.0

#: Au-delà, on considère le journal périmé et on ne propose plus rien.
MAX_AGE_SECONDS = 30 * 24 * 3600

#: Cle d'ordonnancement du journal periodique.
_JOURNAL_TASK = "recovery.journal"


class RecoveryJournal:
    """Écrit périodiquement les documents non enregistrés sur le disque."""

    def __init__(self, get_docs, interval: float = JOURNAL_INTERVAL):
        #: Callable retournant la liste des documents ouverts.
        self._get_docs = get_docs
        self._interval = interval
        self._lock = threading.Lock()
        self._running = False
        #: Empreinte du dernier journal écrit — évite de réécrire à l'identique.
        self._last_signature: tuple | None = None

    # ------------------------------------------------------------------
    def start(self):
        with self._lock:
            if self._running:
                return
            self._running = True
        self._schedule()

    def stop(self):
        with self._lock:
            self._running = False
        scheduler.cancel(_JOURNAL_TASK)

    def _schedule(self):
        with self._lock:
            if not self._running:
                return
        scheduler.schedule(_JOURNAL_TASK, self._interval, self._tick)

    def _tick(self):
        try:
            self.snapshot()
        except Exception:
            pass          # un échec de journalisation ne doit jamais gêner
        self._schedule()

    # ------------------------------------------------------------------
    def snapshot(self):
        """Écrit le journal si des modifications sont en attente."""
        try:
            docs = self._get_docs() or []
        except Exception:
            return

        entries = [
            {
                "title": d.title,
                "path": d.path,
                "content": d.content,
                "encoding": getattr(d, "encoding", "utf-8"),
                "newline": getattr(d, "newline", "\n"),
            }
            for d in docs if d.modified and d.content
        ]

        if not entries:
            clear()
            self._last_signature = None
            return

        signature = tuple((e["title"], e["path"], len(e["content"]),
                           hash(e["content"])) for e in entries)
        if signature == self._last_signature:
            return
        self._last_signature = signature

        _write({"saved_at": time.time(), "pid": os.getpid(), "documents": entries})


# ---------------------------------------------------------------------------
# Lecture / écriture
# ---------------------------------------------------------------------------

def _write(payload: dict):
    try:
        os.makedirs(_DATA_DIR, exist_ok=True)
        tmp = _RECOVERY_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, _RECOVERY_FILE)
    except OSError:
        pass


def load() -> list[dict]:
    """Documents récupérables laissés par une session interrompue.

    Retourne une liste vide si la session précédente s'est fermée
    normalement (le journal est alors supprimé).
    """
    if not os.path.isfile(_RECOVERY_FILE):
        return []
    try:
        with open(_RECOVERY_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError, ValueError):
        clear()
        return []

    if not isinstance(data, dict):
        clear()
        return []

    saved_at = float(data.get("saved_at", 0) or 0)
    if saved_at and time.time() - saved_at > MAX_AGE_SECONDS:
        clear()
        return []

    documents = data.get("documents")
    if not isinstance(documents, list):
        clear()
        return []

    return [d for d in documents
            if isinstance(d, dict) and isinstance(d.get("content"), str)]


def has_pending() -> bool:
    return bool(load())


def clear():
    """Supprime le journal — à appeler à toute fermeture propre."""
    try:
        os.remove(_RECOVERY_FILE)
    except OSError:
        pass


def age_label() -> str:
    """Ancienneté du journal, en français lisible."""
    try:
        with open(_RECOVERY_FILE, "r", encoding="utf-8") as fh:
            saved_at = float(json.load(fh).get("saved_at", 0))
    except (OSError, ValueError, json.JSONDecodeError, TypeError):
        return ""
    if not saved_at:
        return ""

    seconds = max(0, int(time.time() - saved_at))
    if seconds < 90:
        return "il y a moins d'une minute"
    minutes = seconds // 60
    if minutes < 60:
        return f"il y a {minutes} minutes"
    hours = minutes // 60
    if hours < 24:
        return f"il y a {hours} heure{'s' if hours > 1 else ''}"
    days = hours // 24
    return f"il y a {days} jour{'s' if days > 1 else ''}"
