"""
controllers/tab_controller.py — Gestion des onglets de documents.
"""

from constants import MODE_READ
from models.document import Document


class TabController:
    """Gère l'ajout, la suppression et la navigation entre onglets."""

    def __init__(self, state, editor, ph, rebuild_fn, update_status_fn):
        self.state = state
        self.editor = editor
        self.ph = ph
        self._rebuild = rebuild_fn
        self._update_status = update_status_fn

    def cur_doc(self):
        s = self.state
        return s.docs[s.idx] if 0 <= s.idx < len(s.docs) else None

    def add_tab(self, title="", content="", path=None):
        idx = len(self.state.docs)
        self.state.docs.append(
            Document(title=title or f"Sans titre {idx}", content=content, path=path)
        )
        self.state.idx = idx
        self.sync_editor()
        self._rebuild()

    def switch_tab(self, idx):
        if idx == self.state.idx:
            return
        self.save_content()
        self.state.idx = idx
        self.sync_editor()
        self._rebuild()

    def close_tab(self, idx):
        if len(self.state.docs) <= 1:
            self.state.docs[0] = Document()
            self.state.idx = 0
            self.sync_editor()
            self._rebuild()
            return
        self.state.docs.pop(idx)
        if self.state.idx >= len(self.state.docs):
            self.state.idx = len(self.state.docs) - 1
        self.sync_editor()
        self._rebuild()

    def save_content(self):
        d = self.cur_doc()
        if d:
            d.content = self.editor.value or ""

    def sync_editor(self):
        d = self.cur_doc()
        if not d:
            return
        self.editor.value = d.content
        self.editor.read_only = (self.state.mode == MODE_READ)
        self.editor.hint_text = self.ph.get_random_phrase()
        self._update_status()
