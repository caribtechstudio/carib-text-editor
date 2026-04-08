"""
models/file_manager.py — Opérations fichier (lecture, écriture, renommage).
"""

import os


def read_file(filepath: str) -> str | None:
    """Lit un fichier texte en essayant utf-8 puis latin-1. Retourne None en cas d'échec."""
    for enc in ("utf-8", "latin-1"):
        try:
            with open(filepath, "r", encoding=enc) as fh:
                return fh.read()
        except UnicodeDecodeError:
            continue
        except OSError:
            return None
    return None


def write_file(path: str, content: str) -> None:
    """Écrit du contenu dans un fichier. Lève OSError en cas d'échec."""
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)


def rename_file_on_disk(old_path: str, new_name: str) -> str:
    """Renomme un fichier sur le disque. Retourne le nouveau chemin. Lève OSError en cas d'échec."""
    new_path = os.path.join(os.path.dirname(old_path), new_name)
    os.rename(old_path, new_path)
    return new_path
