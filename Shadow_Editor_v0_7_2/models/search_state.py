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
        self.query = ""
        self.matches.clear()
        self.current_index = -1
