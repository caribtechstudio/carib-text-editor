"""
models/llm/credentials.py — Stockage des cles API.

Les cles ne sont **jamais** ecrites dans `session.json`. Sous Windows elles
sont chiffrees par DPAPI (`CryptProtectData`), c'est-a-dire liees au compte
utilisateur : un autre compte de la meme machine, ou une copie du fichier
sur une autre machine, ne peut pas les dechiffrer. Aucune dependance
supplementaire n'est necessaire, DPAPI fait partie de Windows.

Sur les autres systemes on retombe sur un fichier a permissions restreintes
(0600). Ce n'est pas du chiffrement : la fonction `is_secure()` le signale
pour que l'interface puisse prevenir l'utilisateur.
"""

import base64
import ctypes
import json
import os
import sys

_DATA_DIR = os.path.join(os.path.expanduser("~"), ".glyph")
_KEYS_FILE = os.path.join(_DATA_DIR, "credentials.dat")

_IS_WINDOWS = sys.platform == "win32"

#: Entropie supplementaire : un attaquant doit connaitre cette valeur en plus
#: d'avoir compromis le compte Windows pour dechiffrer le fichier.
_ENTROPY = b"Glyph.credentials.v1"


# ---------------------------------------------------------------------------
# DPAPI (Windows)
# ---------------------------------------------------------------------------

class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", ctypes.c_uint32),
                ("pbData", ctypes.POINTER(ctypes.c_char))]


def _make_blob(data: bytes) -> _DataBlob:
    buf = ctypes.create_string_buffer(data, len(data))
    return _DataBlob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))


def _blob_bytes(blob: _DataBlob) -> bytes:
    return ctypes.string_at(blob.pbData, blob.cbData)


def _free_blob(blob: _DataBlob) -> None:
    if blob.pbData:
        ctypes.windll.kernel32.LocalFree(blob.pbData)


def _dpapi_protect(data: bytes) -> bytes:
    blob_in = _make_blob(data)
    blob_entropy = _make_blob(_ENTROPY)
    blob_out = _DataBlob()
    ok = ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(blob_in), None, ctypes.byref(blob_entropy),
        None, None, 0, ctypes.byref(blob_out),
    )
    if not ok:
        raise OSError("CryptProtectData a echoue.")
    try:
        return _blob_bytes(blob_out)
    finally:
        _free_blob(blob_out)


def _dpapi_unprotect(data: bytes) -> bytes:
    blob_in = _make_blob(data)
    blob_entropy = _make_blob(_ENTROPY)
    blob_out = _DataBlob()
    ok = ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(blob_in), None, ctypes.byref(blob_entropy),
        None, None, 0, ctypes.byref(blob_out),
    )
    if not ok:
        raise OSError("CryptUnprotectData a echoue.")
    try:
        return _blob_bytes(blob_out)
    finally:
        _free_blob(blob_out)


# ---------------------------------------------------------------------------
# API publique
# ---------------------------------------------------------------------------

def is_secure() -> bool:
    """True si les cles sont reellement chiffrees (DPAPI disponible)."""
    return _IS_WINDOWS


def _ensure_dir():
    os.makedirs(_DATA_DIR, exist_ok=True)


def _read_all() -> dict[str, str]:
    if not os.path.isfile(_KEYS_FILE):
        return {}
    try:
        with open(_KEYS_FILE, "rb") as fh:
            raw = fh.read()
        if not raw:
            return {}
        if _IS_WINDOWS:
            raw = _dpapi_unprotect(raw)
        else:
            raw = base64.b64decode(raw)
        data = json.loads(raw.decode("utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError, json.JSONDecodeError):
        # Fichier corrompu, ou chiffre pour un autre compte Windows :
        # on repart d'un jeu vide plutot que de bloquer l'application.
        return {}


def _write_all(data: dict[str, str]) -> None:
    _ensure_dir()
    raw = json.dumps(data).encode("utf-8")
    raw = _dpapi_protect(raw) if _IS_WINDOWS else base64.b64encode(raw)

    # Ecriture atomique, meme traitement que pour les documents.
    tmp = _KEYS_FILE + ".tmp"
    with open(tmp, "wb") as fh:
        fh.write(raw)
        fh.flush()
        os.fsync(fh.fileno())
    if not _IS_WINDOWS:
        os.chmod(tmp, 0o600)
    os.replace(tmp, _KEYS_FILE)


def get_key(provider: str) -> str:
    """Cle en clair pour un fournisseur, ou "" si absente."""
    return _read_all().get(provider, "")


def set_key(provider: str, key: str) -> None:
    """Enregistre (ou remplace) la cle d'un fournisseur."""
    data = _read_all()
    if key:
        data[provider] = key
    else:
        data.pop(provider, None)
    _write_all(data)


def delete_key(provider: str) -> None:
    set_key(provider, "")


def configured_providers() -> list[str]:
    """Fournisseurs pour lesquels une cle est enregistree."""
    return [k for k, v in _read_all().items() if v]


def mask(key: str) -> str:
    """Representation affichable d'une cle : « sk-…a1b2 ».

    L'interface ne doit jamais afficher autre chose que ce masque.
    """
    if not key:
        return ""
    if len(key) <= 10:
        return "•" * len(key)
    return f"{key[:3]}…{key[-4:]}"
