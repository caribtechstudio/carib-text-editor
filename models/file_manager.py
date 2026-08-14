"""
models/file_manager.py — Lecture et écriture de fichiers texte, en toute sécurité.

Garanties offertes par ce module :

  * **Écriture atomique** — le fichier de l'utilisateur n'est jamais tronqué.
    On écrit dans un fichier temporaire du même dossier, on force le vidage
    des tampons sur le disque (`fsync`), puis on bascule avec `os.replace`
    qui est atomique sur NTFS comme sur POSIX. Une coupure de courant laisse
    soit l'ancienne version intacte, soit la nouvelle complète — jamais un
    fichier à moitié écrit.

  * **Encodage détecté, jamais deviné en silence** — on lit la signature BOM,
    puis on tente UTF-8 strict. Le repli sur un encodage 8 bits est signalé
    (`confident=False`) pour que l'interface puisse prévenir l'utilisateur
    avant qu'une réécriture ne détruise des caractères.

  * **Fins de ligne préservées** — un fichier Windows (CRLF) relu et
    réenregistré reste en CRLF. Sans cela, ouvrir puis sauvegarder modifie
    chaque ligne du fichier et produit un diff Git de 100 %.

  * **Refus des binaires et des fichiers géants** — plutôt que de figer
    l'application ou de corrompre des données.
"""

import os
import tempfile
from dataclasses import dataclass

# Au-delà de cette taille, le TextField de Flet n'est plus utilisable
# (pas de virtualisation) : mieux vaut refuser proprement que de figer l'UI.
MAX_FILE_BYTES = 32 * 1024 * 1024      # 32 Mo
_SNIFF_BYTES = 8192                    # échantillon pour la détection binaire

DEFAULT_ENCODING = "utf-8"
DEFAULT_NEWLINE = os.linesep if os.linesep in ("\r\n", "\n") else "\n"

# Signatures BOM, de la plus longue à la plus courte (l'ordre compte :
# le BOM UTF-32-LE commence par le BOM UTF-16-LE).
_BOMS = (
    (b"\x00\x00\xfe\xff", "utf-32-be"),
    (b"\xff\xfe\x00\x00", "utf-32-le"),
    (b"\xef\xbb\xbf",     "utf-8-sig"),
    (b"\xfe\xff",         "utf-16-be"),
    (b"\xff\xfe",         "utf-16-le"),
)

# Replis 8 bits testés dans l'ordre. cp1252 couvre le français sous Windows ;
# latin-1 accepte n'importe quel octet et sert de dernier recours.
_FALLBACK_ENCODINGS = ("cp1252", "latin-1")


class FileTooLargeError(OSError):
    """Le fichier dépasse MAX_FILE_BYTES."""


class BinaryFileError(OSError):
    """Le fichier ne ressemble pas à du texte."""


@dataclass
class LoadedFile:
    """Contenu d'un fichier et tout ce qu'il faut pour le réécrire à l'identique."""

    text: str
    encoding: str = DEFAULT_ENCODING
    newline: str = DEFAULT_NEWLINE
    mtime: float = 0.0
    size: int = 0
    #: False quand l'encodage a été deviné par repli (risque de mojibake).
    confident: bool = True


# ---------------------------------------------------------------------------
# Détection
# ---------------------------------------------------------------------------

def detect_newline(text: str) -> str:
    """Détermine le style de fin de ligne dominant d'un texte brut.

    Le texte doit avoir été lu SANS traduction des retours (newline=""),
    sinon tout aura déjà été converti en "\\n" et la détection est inutile.
    """
    crlf = text.count("\r\n")
    cr = text.count("\r") - crlf          # \r isolés (vieux Mac)
    lf = text.count("\n") - crlf
    if crlf >= lf and crlf >= cr and crlf > 0:
        return "\r\n"
    if cr > lf and cr > 0:
        return "\r"
    if lf > 0:
        return "\n"
    return DEFAULT_NEWLINE                # fichier sans aucun saut de ligne


def _detect_encoding(raw: bytes) -> tuple[str, bool]:
    """Retourne (encodage, confiance) pour un contenu binaire."""
    for bom, enc in _BOMS:
        if raw.startswith(bom):
            return enc, True
    try:
        raw.decode("utf-8")
        return "utf-8", True
    except UnicodeDecodeError:
        pass
    for enc in _FALLBACK_ENCODINGS:
        try:
            raw.decode(enc)
            # cp1252 rejette quelques octets, donc un succès est un signal
            # faible mais réel ; latin-1 accepte tout, d'où confiance = False.
            return enc, enc != "latin-1"
        except UnicodeDecodeError:
            continue
    return "latin-1", False


def _looks_binary(raw: bytes) -> bool:
    """Un octet NUL dans l'échantillon = fichier binaire (hors UTF-16/32)."""
    sample = raw[:_SNIFF_BYTES]
    for bom, _ in _BOMS:
        if raw.startswith(bom):
            return False                  # UTF-16/32 contiennent des NUL légitimes
    return b"\x00" in sample


# ---------------------------------------------------------------------------
# Lecture
# ---------------------------------------------------------------------------

def load_file(path: str) -> LoadedFile:
    """Charge un fichier texte avec son encodage et ses fins de ligne.

    Lève :
        FileTooLargeError : au-delà de MAX_FILE_BYTES.
        BinaryFileError   : contenu manifestement binaire.
        OSError           : fichier illisible.
    """
    st = os.stat(path)
    if st.st_size > MAX_FILE_BYTES:
        raise FileTooLargeError(
            f"Fichier trop volumineux ({st.st_size / (1024 * 1024):.0f} Mo). "
            f"Limite : {MAX_FILE_BYTES // (1024 * 1024)} Mo."
        )

    with open(path, "rb") as fh:
        raw = fh.read()

    if _looks_binary(raw):
        raise BinaryFileError("Ce fichier ne semble pas être du texte.")

    encoding, confident = _detect_encoding(raw)
    # errors="replace" : on a déjà validé le décodage, ce garde-fou évite
    # simplement qu'une race sur le fichier fasse planter l'application.
    text = raw.decode(encoding, errors="replace")

    newline = detect_newline(text)
    # On normalise en mémoire : l'éditeur ne manipule que des "\n".
    # Le style d'origine est restitué à l'écriture.
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    return LoadedFile(text=text, encoding=encoding, newline=newline,
                      mtime=st.st_mtime, size=st.st_size, confident=confident)


def read_file(filepath: str) -> str | None:
    """Lecture simple — retourne le texte ou None en cas d'échec.

    Conservé pour les appelants qui n'ont pas besoin des métadonnées.
    """
    try:
        return load_file(filepath).text
    except OSError:
        return None


# ---------------------------------------------------------------------------
# Écriture
# ---------------------------------------------------------------------------

def write_file(path: str, content: str,
               encoding: str = DEFAULT_ENCODING,
               newline: str = DEFAULT_NEWLINE) -> tuple[float, int]:
    """Écrit un fichier de façon atomique. Retourne (mtime, taille).

    Le contenu est supposé normalisé en "\\n" ; `newline` est appliqué à
    l'écriture pour restituer le style d'origine du fichier.

    Lève OSError si l'écriture échoue (le fichier d'origine reste intact).
    """
    directory = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(directory, exist_ok=True)

    # Le fichier temporaire doit être sur le MÊME volume que la cible,
    # sinon os.replace n'est plus atomique (copie inter-volumes).
    fd, tmp_path = tempfile.mkstemp(dir=directory, prefix=".glyph-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding=encoding, newline=newline) as fh:
            fh.write(content)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, path)
    except BaseException:
        # Nettoyer le temporaire sans masquer l'exception d'origine.
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    st = os.stat(path)
    return st.st_mtime, st.st_size


def file_changed_on_disk(path: str, known_mtime: float, known_size: int) -> bool:
    """Indique si le fichier a été modifié en dehors de Glyph depuis sa lecture."""
    if not path or not known_mtime:
        return False
    try:
        st = os.stat(path)
    except OSError:
        return False                      # disparu : traité ailleurs
    # Tolérance d'1 s : certains systèmes de fichiers ont une résolution
    # de mtime grossière (FAT32, montages réseau).
    return abs(st.st_mtime - known_mtime) > 1.0 or st.st_size != known_size


def rename_file_on_disk(old_path: str, new_name: str) -> str:
    """Renomme un fichier. Refuse d'écraser une cible existante.

    Lève OSError si le nom est invalide ou si la cible existe déjà.
    """
    new_name = new_name.strip()
    if not new_name or new_name in (".", ".."):
        raise OSError("Nom de fichier invalide.")
    # La validation porte sur la saisie brute : appliquer `basename` d'abord
    # masquerait un séparateur de chemin au lieu de le refuser, et permettrait
    # d'écrire ailleurs que dans le dossier courant.
    if any(ch in new_name for ch in '<>:"/\\|?*'):
        raise OSError('Le nom ne peut pas contenir < > : " / \\ | ? *')

    new_path = os.path.join(os.path.dirname(old_path), new_name)
    if os.path.normcase(new_path) == os.path.normcase(old_path):
        return old_path
    if os.path.exists(new_path):
        raise OSError(f"« {new_name} » existe déjà dans ce dossier.")
    os.rename(old_path, new_path)
    return new_path
