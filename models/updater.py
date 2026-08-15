"""
models/updater.py — Mise a jour depuis les releases GitHub.

Le principe est volontairement minimal : aucun serveur a exploiter, aucun
compte, aucun identifiant. Carib demande a l'API publique de GitHub la
description de la derniere version publiee, compare son numero au sien, et
propose le telechargement de l'installeur.

Trois regles gouvernent ce module, parce qu'il telecharge puis **execute**
un programme sur la machine de l'utilisateur :

  1. **Rien n'est jamais automatique.** La verification demande l'accord de
     l'utilisateur au premier lancement ; le telechargement et l'installation
     demandent une action explicite a chaque fois.
  2. **L'origine est verrouillee.** Seuls les domaines de GitHub sont
     acceptes, en HTTPS, y compris apres redirection — c'est la que mene
     l'URL d'un actif de release.
  3. **Le fichier est verifie avant d'etre lance.** Taille, empreinte
     SHA-256 publiee avec la release, et signature Authenticode : une
     signature *invalide* fait echouer la mise a jour. Une absence de
     signature est toleree tant que l'application n'est pas signee, mais
     elle est journalisee.

Un echec de mise a jour ne doit jamais empecher d'ecrire du texte : toutes
les erreurs remontent sous forme d'`UpdateError` portant un message deja
redige, et l'appelant se contente de l'afficher.
"""

import hashlib
import json
import logging
import os
import re
import sys
import threading
import time
from dataclasses import dataclass, field

from core.constants import APP_VERSION, GITHUB_REPO

log = logging.getLogger(__name__)

_DATA_DIR = os.path.join(os.path.expanduser("~"), ".carib")
_PREFS_FILE = os.path.join(_DATA_DIR, "update.json")
_DOWNLOAD_DIR = os.path.join(_DATA_DIR, "updates")

#: Une verification par jour suffit largement pour un editeur de texte.
CHECK_INTERVAL = 24 * 3600

CONNECT_TIMEOUT = 6
READ_TIMEOUT = 20

#: Au-dela, ce n'est plus un installeur : on refuse plutot que de remplir le
#: disque de l'utilisateur.
MAX_ASSET_BYTES = 400 * 1024 * 1024

#: Hotes autorises pour le telechargement. GitHub redirige les actifs de
#: release vers un domaine de stockage : les deux doivent figurer ici.
_ALLOWED_HOSTS = frozenset({
    "github.com",
    "api.github.com",
    "objects.githubusercontent.com",
    "release-assets.githubusercontent.com",
    "raw.githubusercontent.com",
})

_USER_AGENT = f"Carib/{APP_VERSION} (+https://github.com/{GITHUB_REPO})"

_SHA256_RE = re.compile(r"\b([a-fA-F0-9]{64})\b")


class UpdateError(Exception):
    """Erreur portant un message deja formule pour l'utilisateur."""

    def __init__(self, user_message: str, detail: str = ""):
        super().__init__(user_message)
        self.user_message = user_message
        self.detail = detail


class UpdateCancelled(Exception):
    """L'utilisateur a interrompu le telechargement."""


# ---------------------------------------------------------------------------
# Comparaison de versions
# ---------------------------------------------------------------------------

_VERSION_RE = re.compile(r"^v?(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:[.\-+](.*))?$")


def parse_version(raw: str) -> tuple:
    """« v1.2.3 » → (1, 2, 3, 1, 0). Leve ValueError si illisible.

    Le quatrieme element distingue une preversion (0) d'une version finale
    (1) : sans lui, « 1.0.0-beta » serait vu comme egal a « 1.0.0 », et une
    preversion se proposerait comme mise a jour d'une version stable.
    """
    text = (raw or "").strip()
    match = _VERSION_RE.match(text)
    if not match:
        raise ValueError(f"Numero de version illisible : {raw!r}")

    major, minor, patch = (int(match.group(i) or 0) for i in (1, 2, 3))
    suffix = (match.group(4) or "").strip().lower()

    if not suffix:
        return (major, minor, patch, 1, 0)
    if suffix.isdigit():
        # « 0.13.2.4 » : quatrieme composant numerique, pas une preversion.
        return (major, minor, patch, 1, int(suffix))

    # « 1.0.0-beta.2 » : preversion, donc anterieure a « 1.0.0 ».
    number = re.search(r"(\d+)", suffix)
    return (major, minor, patch, 0, int(number.group(1)) if number else 0)


def is_newer(candidate: str, current: str = APP_VERSION) -> bool:
    """La version distante est-elle strictement plus recente que la locale ?"""
    try:
        return parse_version(candidate) > parse_version(current)
    except ValueError:
        # Une etiquette exotique ne doit pas declencher de proposition.
        log.warning("Etiquette de version ignoree : %r", candidate)
        return False


# ---------------------------------------------------------------------------
# Preferences
# ---------------------------------------------------------------------------

@dataclass
class UpdatePrefs:
    """Reglages de mise a jour, dans ~/.carib/update.json."""

    #: None = jamais demande. L'utilisateur n'a pas encore tranche, et aucune
    #: connexion ne doit avoir lieu avant qu'il ne le fasse.
    enabled: bool | None = None
    #: Version que l'utilisateur a explicitement choisi de ne plus se voir
    #: proposer.
    skipped_version: str = ""
    last_check: float = 0.0

    @classmethod
    def load(cls) -> "UpdatePrefs":
        try:
            with open(_PREFS_FILE, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError, ValueError):
            return cls()
        if not isinstance(data, dict):
            return cls()

        enabled = data.get("enabled")
        try:
            last = float(data.get("last_check", 0.0) or 0.0)
        except (TypeError, ValueError):
            last = 0.0
        return cls(
            enabled=None if enabled is None else bool(enabled),
            skipped_version=str(data.get("skipped_version", "") or ""),
            last_check=last,
        )

    def save(self) -> None:
        try:
            os.makedirs(_DATA_DIR, exist_ok=True)
            tmp = _PREFS_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump({
                    "enabled": self.enabled,
                    "skipped_version": self.skipped_version,
                    "last_check": self.last_check,
                }, fh, ensure_ascii=False, indent=2)
            os.replace(tmp, _PREFS_FILE)
        except OSError as exc:
            log.warning("Preferences de mise a jour non enregistrees : %s", exc)

    def due(self, now: float | None = None) -> bool:
        """Faut-il verifier maintenant ?"""
        if self.enabled is not True:
            return False
        now = time.time() if now is None else now
        return (now - self.last_check) >= CHECK_INTERVAL


# ---------------------------------------------------------------------------
# Description d'une mise a jour
# ---------------------------------------------------------------------------

@dataclass
class UpdateInfo:
    version: str
    tag: str
    name: str = ""
    notes: str = ""
    page_url: str = ""
    published_at: str = ""
    asset_name: str = ""
    asset_url: str = ""
    asset_size: int = 0
    sha256: str = ""
    #: Renseigne quand la release ne fournit pas d'installeur telechargeable.
    assets: list = field(default_factory=list)

    @property
    def can_download(self) -> bool:
        return bool(self.asset_url)

    def short_notes(self, limit: int = 1200) -> str:
        text = (self.notes or "").strip()
        if len(text) <= limit:
            return text
        return text[:limit].rstrip() + "\n…"


# ---------------------------------------------------------------------------
# Reseau
# ---------------------------------------------------------------------------

def _requests():
    try:
        import requests
        return requests
    except ImportError as exc:  # pragma: no cover - requests est obligatoire
        raise UpdateError(
            "Le module « requests » est absent : recherche de mise a jour "
            "impossible.", str(exc)) from exc


def _check_host(url: str) -> None:
    """Refuse toute URL qui ne mene pas chez GitHub, en HTTPS."""
    from urllib.parse import urlparse

    parsed = urlparse(url or "")
    if parsed.scheme != "https" or parsed.hostname not in _ALLOWED_HOSTS:
        raise UpdateError(
            "La mise a jour a ete interrompue : le fichier propose ne "
            "provient pas de GitHub.",
            f"URL refusee : {url}")


def _pick_installer(assets: list) -> dict | None:
    """Choisit l'actif qui est l'installeur Windows."""
    executables = [a for a in assets
                   if str(a.get("name", "")).lower().endswith(".exe")]
    if not executables:
        return None
    for asset in executables:
        if "setup" in str(asset.get("name", "")).lower():
            return asset
    return executables[0]


def _extract_sha256(assets: list, body: str, asset_name: str,
                    fetch=None) -> str:
    """Empreinte attendue de l'installeur.

    Deux sources, dans cet ordre : un actif « SHA256SUMS.txt » publie avec la
    release, puis le corps du texte de la release. Retourne "" si aucune n'est
    exploitable — le telechargement reste alors possible, mais la verification
    se limite a la taille et a la signature.
    """
    for asset in assets:
        name = str(asset.get("name", "")).lower()
        if name in ("sha256sums.txt", "sha256sums") or name.endswith(".sha256"):
            url = asset.get("browser_download_url") or ""
            if not url or fetch is None:
                continue
            try:
                _check_host(url)
                content = fetch(url)
            except Exception as exc:
                log.warning("SHA256SUMS illisible : %s", exc)
                continue
            digest = _parse_sums(content, asset_name)
            if digest:
                return digest

    # Repli : une empreinte citee dans les notes de version. On privilegie la
    # ligne qui nomme l'installeur, puis le cas ou le texte n'en contient
    # qu'une seule — sans ambiguite possible.
    for line in (body or "").splitlines():
        if asset_name and asset_name.lower() in line.lower():
            match = _SHA256_RE.search(line)
            if match:
                return match.group(1).lower()

    found = {h.lower() for h in _SHA256_RE.findall(body or "")}
    return found.pop() if len(found) == 1 else ""


def _parse_sums(content: str, asset_name: str) -> str:
    """Lit un fichier au format `sha256sum` et en extrait la bonne ligne.

    Format attendu, celui produit par `sha256sum` et par `Get-FileHash` :

        d41d8c...  Carib_v0.14.0_Setup.exe
        e3b0c4... *Carib_v0.14.0_Setup.exe
    """
    target = (asset_name or "").lower()
    entries = []
    for line in (content or "").splitlines():
        match = _SHA256_RE.search(line)
        if not match:
            continue
        digest = match.group(1).lower()
        name = line.replace(match.group(1), "").strip().lstrip("*").strip()
        entries.append((digest, name.lower()))

    if not entries:
        return ""
    if target:
        for digest, name in entries:
            if name.endswith(target):
                return digest
    # Une seule empreinte listee : elle ne peut concerner que cet actif.
    return entries[0][0] if len(entries) == 1 else ""


def check(current_version: str = APP_VERSION, *, repo: str = GITHUB_REPO,
          session=None) -> UpdateInfo | None:
    """Interroge GitHub. Retourne l'info si une version plus recente existe.

    Retourne None si Carib est a jour ou si le depot ne publie encore rien.
    Leve `UpdateError` si la verification n'a pas pu aboutir.
    """
    if not repo:
        log.info("GITHUB_REPO vide : recherche de mise a jour desactivee.")
        return None

    requests = _requests()
    http = session or requests
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    _check_host(url)

    try:
        response = http.get(
            url,
            headers={"Accept": "application/vnd.github+json",
                     "User-Agent": _USER_AGENT,
                     "X-GitHub-Api-Version": "2022-11-28"},
            timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
        )
    except Exception as exc:
        raise UpdateError(
            "Impossible de contacter GitHub.\nVerifiez votre connexion internet.",
            str(exc)) from exc

    status = getattr(response, "status_code", 0)
    if status == 404:
        # Depot sans release publiee : ce n'est pas une erreur.
        log.info("Aucune release publiee sur %s.", repo)
        return None
    if status == 403:
        raise UpdateError(
            "GitHub limite temporairement les requetes.\nReessayez plus tard.",
            "HTTP 403")
    if status >= 400:
        raise UpdateError(
            f"GitHub a repondu une erreur ({status}).", f"HTTP {status}")

    try:
        payload = response.json()
    except Exception as exc:
        raise UpdateError("Reponse inattendue de GitHub.", str(exc)) from exc
    if not isinstance(payload, dict):
        raise UpdateError("Reponse inattendue de GitHub.", repr(payload)[:200])

    tag = str(payload.get("tag_name") or "").strip()
    if not tag:
        return None
    version = tag.lstrip("vV")

    if not is_newer(version, current_version):
        return None

    assets = [a for a in (payload.get("assets") or []) if isinstance(a, dict)]
    installer = _pick_installer(assets)
    body = str(payload.get("body") or "")

    def _fetch(u: str) -> str:
        resp = http.get(u, headers={"User-Agent": _USER_AGENT},
                        timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
        if getattr(resp, "status_code", 0) >= 400:
            raise UpdateError("Fichier d'empreintes indisponible.")
        return resp.text

    asset_name = str(installer.get("name", "")) if installer else ""
    try:
        digest = _extract_sha256(assets, body, asset_name, fetch=_fetch)
    except Exception as exc:            # jamais bloquant
        log.warning("Empreinte non recuperee : %s", exc)
        digest = ""

    info = UpdateInfo(
        version=version,
        tag=tag,
        name=str(payload.get("name") or "") or f"Carib {version}",
        notes=body,
        page_url=str(payload.get("html_url") or ""),
        published_at=str(payload.get("published_at") or ""),
        assets=[str(a.get("name", "")) for a in assets],
    )
    if installer:
        info.asset_name = asset_name
        info.asset_url = str(installer.get("browser_download_url") or "")
        try:
            info.asset_size = int(installer.get("size") or 0)
        except (TypeError, ValueError):
            info.asset_size = 0
        info.sha256 = digest

    log.info("Mise a jour disponible : %s (actif : %s)",
             version, info.asset_name or "aucun")
    return info


# ---------------------------------------------------------------------------
# Telechargement
# ---------------------------------------------------------------------------

def download(info: UpdateInfo, *, on_progress=None, cancel: threading.Event | None = None,
             session=None) -> str:
    """Telecharge et verifie l'installeur. Retourne son chemin.

    `on_progress(recu, total)` est appele au fil de l'eau ; `total` vaut 0 si
    le serveur ne l'annonce pas.
    """
    if not info.can_download:
        raise UpdateError(
            "Cette version ne fournit pas d'installeur telechargeable.\n"
            "Ouvrez la page de la release pour la recuperer a la main.")

    _check_host(info.asset_url)
    if info.asset_size and info.asset_size > MAX_ASSET_BYTES:
        raise UpdateError(
            "Le fichier propose est anormalement volumineux : telechargement "
            "annule.", f"{info.asset_size} octets")

    requests = _requests()
    http = session or requests

    os.makedirs(_DOWNLOAD_DIR, exist_ok=True)
    _prune_old_downloads(keep=info.asset_name)

    target = os.path.join(_DOWNLOAD_DIR, os.path.basename(info.asset_name))
    partial = target + ".part"

    try:
        response = http.get(
            info.asset_url, stream=True,
            headers={"Accept": "application/octet-stream",
                     "User-Agent": _USER_AGENT},
            timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
        )
    except Exception as exc:
        raise UpdateError("Le telechargement n'a pas pu demarrer.\n"
                          "Verifiez votre connexion internet.", str(exc)) from exc

    if getattr(response, "status_code", 0) >= 400:
        raise UpdateError(
            f"GitHub a refuse le telechargement ({response.status_code}).")

    # `requests` a suivi les redirections : l'URL finale doit, elle aussi,
    # rester chez GitHub. Sans cette seconde verification, une redirection
    # suffirait a contourner la premiere.
    _check_host(getattr(response, "url", info.asset_url))

    total = info.asset_size
    try:
        declared = int(response.headers.get("Content-Length") or 0)
        total = declared or total
    except (TypeError, ValueError, AttributeError):
        pass
    if total > MAX_ASSET_BYTES:
        raise UpdateError("Le fichier propose est anormalement volumineux.")

    hasher = hashlib.sha256()
    received = 0
    try:
        with open(partial, "wb") as fh:
            for chunk in response.iter_content(chunk_size=64 * 1024):
                if cancel is not None and cancel.is_set():
                    raise UpdateCancelled()
                if not chunk:
                    continue
                received += len(chunk)
                if received > MAX_ASSET_BYTES:
                    raise UpdateError("Telechargement interrompu : fichier trop volumineux.")
                hasher.update(chunk)
                fh.write(chunk)
                if on_progress:
                    on_progress(received, total)
            fh.flush()
            os.fsync(fh.fileno())
    except UpdateCancelled:
        _silent_remove(partial)
        raise
    except UpdateError:
        _silent_remove(partial)
        raise
    except Exception as exc:
        _silent_remove(partial)
        raise UpdateError("Le telechargement a echoue.\nReessayez plus tard.",
                          str(exc)) from exc
    finally:
        try:
            response.close()
        except Exception:
            pass

    # --- Verifications, avant toute execution ---------------------------
    if info.asset_size and received != info.asset_size:
        _silent_remove(partial)
        raise UpdateError(
            "Le fichier telecharge est incomplet : mise a jour annulee.",
            f"{received} octets recus, {info.asset_size} attendus")

    digest = hasher.hexdigest()
    if info.sha256:
        if digest.lower() != info.sha256.lower():
            _silent_remove(partial)
            log.error("Empreinte SHA-256 incorrecte (attendu %s, obtenu %s)",
                      info.sha256, digest)
            raise UpdateError(
                "L'empreinte du fichier telecharge ne correspond pas a celle "
                "publiee.\nPar securite, la mise a jour est annulee.",
                f"attendu {info.sha256}, obtenu {digest}")
        log.info("Empreinte SHA-256 verifiee.")
    else:
        log.warning("Aucune empreinte publiee pour %s : verification limitee.",
                    info.asset_name)

    os.replace(partial, target)

    state, detail = verify_signature(target)
    if state == "invalid":
        _silent_remove(target)
        log.error("Signature Authenticode invalide : %s", detail)
        raise UpdateError(
            "La signature numerique du fichier telecharge est invalide.\n"
            "Par securite, la mise a jour est annulee.", detail)
    if state == "unsigned":
        log.warning("Installeur non signe (%s).", detail)

    log.info("Installeur pret : %s (%d octets)", target, received)
    return target


def _silent_remove(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass


def _prune_old_downloads(keep: str = "") -> None:
    """Un installeur telecharge pese ~150 Mo : on n'en garde jamais deux."""
    try:
        for name in os.listdir(_DOWNLOAD_DIR):
            if name == keep:
                continue
            _silent_remove(os.path.join(_DOWNLOAD_DIR, name))
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Signature Authenticode
# ---------------------------------------------------------------------------

_TRUST_E_NOSIGNATURE = -2146762496          # 0x800B0100
_TRUST_E_SUBJECT_FORM_UNKNOWN = -2146762477  # 0x800B0113
_TRUST_E_PROVIDER_UNKNOWN = -2146762751     # 0x800B0001


def verify_signature(path: str) -> tuple[str, str]:
    """Verifie la signature Authenticode d'un fichier.

    Retourne ("trusted" | "unsigned" | "invalid" | "skipped", detail).

    Tant que Carib n'est pas signe, "unsigned" reste acceptable : c'est le
    SHA-256 publie avec la release qui fait foi. En revanche une signature
    *presente mais invalide* signale un fichier altere, et doit tout arreter.
    """
    if sys.platform != "win32":
        return "skipped", "verification Authenticode propre a Windows"

    import ctypes
    from ctypes import wintypes

    class _GUID(ctypes.Structure):
        _fields_ = [("Data1", ctypes.c_ulong),
                    ("Data2", ctypes.c_ushort),
                    ("Data3", ctypes.c_ushort),
                    ("Data4", ctypes.c_ubyte * 8)]

    class _FileInfo(ctypes.Structure):
        _fields_ = [("cbStruct", wintypes.DWORD),
                    ("pcwszFilePath", wintypes.LPCWSTR),
                    ("hFile", wintypes.HANDLE),
                    ("pgKnownSubject", ctypes.c_void_p)]

    class _TrustData(ctypes.Structure):
        _fields_ = [("cbStruct", wintypes.DWORD),
                    ("pPolicyCallbackData", ctypes.c_void_p),
                    ("pSIPClientData", ctypes.c_void_p),
                    ("dwUIChoice", wintypes.DWORD),
                    ("fdwRevocationChecks", wintypes.DWORD),
                    ("dwUnionChoice", wintypes.DWORD),
                    ("pFile", ctypes.POINTER(_FileInfo)),
                    ("dwStateAction", wintypes.DWORD),
                    ("hWVTStateData", wintypes.HANDLE),
                    ("pwszURLReference", wintypes.LPCWSTR),
                    ("dwProvFlags", wintypes.DWORD),
                    ("dwUIContext", wintypes.DWORD),
                    ("pSignatureSettings", ctypes.c_void_p)]

    # WINTRUST_ACTION_GENERIC_VERIFY_V2
    action = _GUID(0x00AAC56B, 0xCD44, 0x11D0,
                   (ctypes.c_ubyte * 8)(0x8C, 0xC2, 0x00, 0xC0,
                                        0x4F, 0xC2, 0x95, 0xEE))

    file_info = _FileInfo(ctypes.sizeof(_FileInfo), path, None, None)
    data = _TrustData()
    data.cbStruct = ctypes.sizeof(_TrustData)
    data.dwUIChoice = 2              # WTD_UI_NONE — aucune fenetre
    data.fdwRevocationChecks = 0     # WTD_REVOKE_NONE
    data.dwUnionChoice = 1           # WTD_CHOICE_FILE
    data.pFile = ctypes.pointer(file_info)
    data.dwStateAction = 0           # WTD_STATEACTION_IGNORE — rien a liberer
    data.dwProvFlags = 0x00000010    # WTD_SAFER_FLAG

    try:
        wintrust = ctypes.WinDLL("wintrust.dll")
        wintrust.WinVerifyTrust.restype = ctypes.c_long
        result = wintrust.WinVerifyTrust(None, ctypes.byref(action),
                                         ctypes.byref(data))
    except OSError as exc:
        # wintrust indisponible : on ne bloque pas sur un detail d'OS.
        return "skipped", f"WinVerifyTrust indisponible ({exc})"

    if result == 0:
        return "trusted", "signature valide"
    if result in (_TRUST_E_NOSIGNATURE, _TRUST_E_SUBJECT_FORM_UNKNOWN,
                  _TRUST_E_PROVIDER_UNKNOWN):
        return "unsigned", f"aucune signature (0x{result & 0xFFFFFFFF:08X})"
    return "invalid", f"WinVerifyTrust a retourne 0x{result & 0xFFFFFFFF:08X}"


# ---------------------------------------------------------------------------
# Lancement
# ---------------------------------------------------------------------------

def launch_installer(path: str) -> None:
    """Demarre l'installeur. L'appelant doit ensuite fermer l'application.

    Inno Setup ne peut pas remplacer des fichiers verrouilles : Carib doit
    rendre la main tout de suite apres cet appel.
    """
    if not os.path.isfile(path):
        raise UpdateError("L'installeur telecharge est introuvable.")
    if sys.platform != "win32":
        raise UpdateError("L'installation automatique n'est disponible que "
                          "sous Windows.")
    try:
        log.info("Lancement de l'installeur : %s", path)
        os.startfile(path)          # noqa: S606 — chemin verifie ci-dessus
    except OSError as exc:
        raise UpdateError("Le lancement de l'installeur a echoue.\n"
                          "Ouvrez-le a la main depuis le dossier de "
                          "telechargement.", str(exc)) from exc


def download_dir() -> str:
    return _DOWNLOAD_DIR
