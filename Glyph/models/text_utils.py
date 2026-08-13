"""
models/text_utils.py — Utilitaires de texte centrés sur la position du curseur.

Toutes les fonctions d'analyse de l'éditeur (autocomplétion, remplacement
d'emoji, mode calcul) doivent raisonner sur le curseur, jamais sur la fin du
document. Ce module regroupe ces primitives pour éviter que chaque contrôleur
ne réinvente — différemment — la notion de « mot courant ».
"""

import re

#: Caractères acceptés dans un mot (français, apostrophes droite et typographique).
WORD_CHARS = r"a-zA-ZàâäéèêëïîôöùûüÿçÀÂÄÉÈÊËÏÎÔÖÙÛÜŸÇ'’\-"

_WORD_BEFORE_RE = re.compile(rf"[{WORD_CHARS}]+$")
_WORD_AFTER_RE = re.compile(rf"^[{WORD_CHARS}]+")
_WORD_RE = re.compile(rf"[{WORD_CHARS}]+")


def clamp_cursor(text: str, cursor: int | None) -> int:
    """Ramène une position de curseur dans les bornes du texte."""
    if cursor is None:
        return len(text)
    return max(0, min(int(cursor), len(text)))


def word_before_cursor(text: str, cursor: int | None) -> str:
    """Mot en cours de saisie, c.-à-d. juste à gauche du curseur.

    Retourne "" si le caractère précédent n'appartient pas à un mot.
    """
    cursor = clamp_cursor(text, cursor)
    if cursor == 0:
        return ""
    match = _WORD_BEFORE_RE.search(text, 0, cursor)
    return match.group(0) if match else ""


def word_bounds_at_cursor(text: str, cursor: int | None) -> tuple[int, int]:
    """Bornes (début, fin) du mot sous le curseur.

    Le mot inclut la partie déjà tapée à gauche ET la fin du mot à droite,
    de sorte qu'accepter une complétion au milieu d'un mot le remplace
    entièrement plutôt que d'en dupliquer la fin.
    """
    cursor = clamp_cursor(text, cursor)
    before = _WORD_BEFORE_RE.search(text, 0, cursor)
    start = before.start() if before else cursor
    after = _WORD_AFTER_RE.search(text[cursor:])
    end = cursor + (after.end() if after else 0)
    return start, end


def replace_word_at_cursor(text: str, cursor: int | None,
                           replacement: str) -> tuple[str, int]:
    """Remplace le mot sous le curseur. Retourne (nouveau_texte, nouveau_curseur)."""
    start, end = word_bounds_at_cursor(text, cursor)
    new_text = text[:start] + replacement + text[end:]
    return new_text, start + len(replacement)


def line_bounds_at_cursor(text: str, cursor: int | None) -> tuple[int, int]:
    """Bornes (début, fin) de la ligne contenant le curseur, hors saut de ligne."""
    cursor = clamp_cursor(text, cursor)
    start = text.rfind("\n", 0, cursor) + 1
    end = text.find("\n", cursor)
    if end == -1:
        end = len(text)
    return start, end


def line_col_at_cursor(text: str, cursor: int | None) -> tuple[int, int]:
    """Position humaine (ligne, colonne), toutes deux à base 1."""
    cursor = clamp_cursor(text, cursor)
    line = text.count("\n", 0, cursor) + 1
    col = cursor - (text.rfind("\n", 0, cursor) + 1) + 1
    return line, col


def count_words(text: str) -> int:
    """Nombre de mots — coûteux sur les gros documents, à appeler avec parcimonie."""
    if not text.strip():
        return 0
    return len(_WORD_RE.findall(text))


def iter_words(text: str):
    """Itère sur les mots du texte (utilisé pour construire le dictionnaire)."""
    return (m.group(0) for m in _WORD_RE.finditer(text))
