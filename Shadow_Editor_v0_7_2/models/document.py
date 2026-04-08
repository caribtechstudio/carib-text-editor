"""
models/document.py — Représentation d'un document ouvert dans l'éditeur.
"""


MAX_UNDO = 50


class Document:
    """Un document avec titre, contenu, chemin sur disque et flag de modification."""

    def __init__(self, title="Sans titre", content="", path=None, modified=False):
        self.title = title
        self.content = content
        self.path = path
        self.modified = modified
        self.undo_stack: list[str] = []
        self.redo_stack: list[str] = []

    def push_undo(self, text: str):
        """Enregistre un snapshot dans la pile undo (si différent du dernier)."""
        if self.undo_stack and self.undo_stack[-1] == text:
            return
        self.undo_stack.append(text)
        if len(self.undo_stack) > MAX_UNDO:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def undo(self) -> str | None:
        """Annule : restaure le snapshot précédent, empile l'état actuel dans redo."""
        if not self.undo_stack:
            return None
        self.redo_stack.append(self.content)
        self.content = self.undo_stack.pop()
        return self.content

    def redo(self) -> str | None:
        """Rétablit : restaure le snapshot suivant, empile l'état actuel dans undo."""
        if not self.redo_stack:
            return None
        self.undo_stack.append(self.content)
        self.content = self.redo_stack.pop()
        return self.content
