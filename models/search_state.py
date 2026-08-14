"""
models/search_state.py — État de la recherche dans l'éditeur.
"""

import re


class SearchState:
    """Gère l'état de la barre de recherche."""

    def __init__(self):
        self.visible: bool = False
        self.query: str = ""
        self.case_sensitive: bool = False
        self.whole_word: bool = False
        self.use_regex: bool = False
        self.matches: list[tuple[int, int]] = []  # [(start, end), ...]
        self.current_index: int = -1

        # --- Remplacement ---
        #: Le panneau de remplacement est-il deplie ?
        self.replace_visible: bool = False
        self.replacement: str = ""

    @property
    def total(self) -> int:
        return len(self.matches)

    @property
    def label(self) -> str:
        if not self.query:
            return ""
        if not self.matches:
            return "Aucun résultat"
        return f"{self.current_index + 1}/{self.total}"

    def search(self, text: str):
        """Lance la recherche et met à jour les résultats."""
        self.matches.clear()
        self.current_index = -1
        if not self.query or not text:
            return

        try:
            pattern = self._build_pattern()
            for m in re.finditer(pattern, text):
                self.matches.append((m.start(), m.end()))
        except re.error:
            self.matches.clear()
            return

        if self.matches:
            self.current_index = 0

    def _build_pattern(self) -> re.Pattern:
        q = self.query
        if not self.use_regex:
            q = re.escape(q)
        if self.whole_word:
            q = rf"\b{q}\b"
        flags = 0 if self.case_sensitive else re.IGNORECASE
        return re.compile(q, flags)

    def go_next(self):
        if not self.matches:
            return
        self.current_index = (self.current_index + 1) % self.total

    def go_prev(self):
        if not self.matches:
            return
        self.current_index = (self.current_index - 1) % self.total

    def current_match(self) -> tuple[int, int] | None:
        if not self.matches or self.current_index < 0:
            return None
        return self.matches[self.current_index]

    def reset(self):
        self.visible = False
        self.replace_visible = False
        self.query = ""
        self.matches.clear()
        self.current_index = -1

    # ------------------------------------------------------------------
    # Remplacement
    # ------------------------------------------------------------------
    def _expand_replacement(self, text: str, match: tuple[int, int]) -> str:
        """Calcule le texte de remplacement pour un match donne.

        En mode expression reguliere, les references arrieres (\\1, \\g<nom>)
        sont developpees comme dans `re.sub`. En mode litteral, le texte est
        insere tel quel — un « \\1 » tape par l'utilisateur reste « \\1 ».
        """
        if not self.use_regex:
            return self.replacement
        try:
            pattern = self._build_pattern()
            m = pattern.match(text, match[0], match[1])
            if m is None:
                return self.replacement
            return m.expand(self.replacement)
        except (re.error, IndexError):
            return self.replacement

    def replace_current(self, text: str) -> tuple[str, bool]:
        """Remplace le match courant. Retourne (nouveau_texte, a_remplace)."""
        # Le remplacement peut être déclenché avant toute recherche explicite
        # (l'utilisateur tape sa requête puis va droit au bouton) : on
        # s'assure d'avoir des résultats à jour plutôt que de ne rien faire.
        if not self.matches:
            self.search(text)

        match = self.current_match()
        if match is None:
            return text, False

        start, end = match
        replacement = self._expand_replacement(text, match)
        new_text = text[:start] + replacement + text[end:]

        # On relance la recherche sur le texte modifie, puis on se positionne
        # sur le premier match situe apres l'insertion — c'est le
        # comportement attendu d'un « Remplacer » repete.
        cursor = start + len(replacement)
        self.search(new_text)
        if self.matches:
            for i, (s, _) in enumerate(self.matches):
                if s >= cursor:
                    self.current_index = i
                    break
            else:
                self.current_index = 0
        return new_text, True

    def replace_all(self, text: str) -> tuple[str, int]:
        """Remplace toutes les occurrences. Retourne (nouveau_texte, nombre)."""
        self.search(text)
        if not self.matches:
            return text, 0

        # Reconstruction en un seul passage, de gauche a droite : plus rapide
        # et sans risque de decalage d'indices.
        pieces = []
        last = 0
        for match in self.matches:
            start, end = match
            pieces.append(text[last:start])
            pieces.append(self._expand_replacement(text, match))
            last = end
        pieces.append(text[last:])

        count = len(self.matches)
        new_text = "".join(pieces)
        self.search(new_text)
        return new_text, count
