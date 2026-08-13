"""
controllers/tab_controller.py — Gestion des onglets de documents.

Toute bascule d'un document vers un autre passe par `_leave()` puis
`_enter()`. Ces deux bornes sont appelées **ici**, et non par les appelants :
la barre d'onglets, le bouton « + », Ctrl+N, Ctrl+Tab, la palette de
commandes, l'ouverture de fichier et la fermeture d'onglet empruntent des
chemins différents, et il suffisait qu'un seul d'entre eux oublie de
réinitialiser le contexte d'édition pour que le curseur, la sélection ou la
base d'annulation d'un onglet se retrouvent appliqués à un autre.
"""

from constants import MODE_READ
from models.document import Document


class TabController:
    """Ajout, fermeture et navigation entre onglets."""

    def __init__(self, state, editor, ph, services,
                 on_leave_document=None, on_enter_document=None):
        self.state = state
        self.editor = editor
        self.ph = ph
        self._rebuild = services.rebuild
        self._update_status = services.update_status
        self._on_tabs_changed = services.save_session
        #: Bornes de changement de document, fournies par AppController.
        self._on_leave = on_leave_document or (lambda: None)
        self._on_enter = on_enter_document or (lambda: None)

    # ------------------------------------------------------------------
    # Bornes de changement de document
    # ------------------------------------------------------------------
    def _leave(self):
        """Quitte le document actif en préservant son contenu et son historique."""
        self.save_content()
        self._on_leave()

    def _enter(self):
        """Prend en charge le document devenu actif."""
        self._on_enter()

    # ------------------------------------------------------------------
    # Accès
    # ------------------------------------------------------------------
    def cur_doc(self):
        s = self.state
        return s.docs[s.idx] if 0 <= s.idx < len(s.docs) else None

    def save_content(self):
        """Recopie le contenu du widget vers le document actif."""
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

    # ------------------------------------------------------------------
    # Création
    # ------------------------------------------------------------------
    def add_tab(self, title="", content="", path=None):
        # Créer un onglet, c'est quitter le document courant : le contenu et
        # la salve de frappe en cours doivent être figés avant tout.
        self._leave()
        idx = len(self.state.docs)
        self.state.docs.append(
            Document(title=title or f"Sans titre {idx}", content=content, path=path))
        self._activate(idx)

    def add_tab_from_file(self, title, loaded, path):
        """Crée un onglet à partir d'un `LoadedFile`, métadonnées comprises."""
        # Si le fichier est déjà ouvert, on s'y rend au lieu de le dupliquer.
        import os
        target = os.path.normcase(os.path.abspath(path))
        for i, d in enumerate(self.state.docs):
            if d.path and os.path.normcase(os.path.abspath(d.path)) == target:
                self.switch_tab(i)
                return

        self._leave()

        doc = Document(
            title=title, content=loaded.text, path=path,
            encoding=loaded.encoding, newline=loaded.newline,
            mtime=loaded.mtime, size=loaded.size,
            encoding_confident=loaded.confident,
        )

        # Remplacer l'onglet vide par défaut plutôt que d'en empiler un second.
        if (len(self.state.docs) == 1 and not self.state.docs[0].path
                and not self.state.docs[0].content
                and not self.state.docs[0].modified):
            self.state.docs[0] = doc
            self._activate(0)
            return

        self.state.docs.append(doc)
        self._activate(len(self.state.docs) - 1)

    def _activate(self, idx: int):
        self.state.idx = idx
        self.sync_editor()
        self._enter()
        self._rebuild()
        self._on_tabs_changed()

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------
    def switch_tab(self, idx):
        if idx == self.state.idx or not (0 <= idx < len(self.state.docs)):
            return
        self._leave()
        self.state.idx = idx
        self.sync_editor()
        self._enter()
        self._rebuild()

    def next_tab(self):
        if len(self.state.docs) > 1:
            self.switch_tab((self.state.idx + 1) % len(self.state.docs))

    def prev_tab(self):
        if len(self.state.docs) > 1:
            self.switch_tab((self.state.idx - 1) % len(self.state.docs))

    # ------------------------------------------------------------------
    # Fermeture
    # ------------------------------------------------------------------
    def close_tab(self, idx):
        if not (0 <= idx < len(self.state.docs)):
            return

        # Fermer un onglet d'arrière-plan ne doit pas déplacer le curseur de
        # celui qu'on est en train d'écrire : les bornes ne se déclenchent
        # que si le document actif change réellement.
        previous = self.cur_doc()
        self._leave()

        if len(self.state.docs) <= 1:
            self.state.docs[0] = Document()
            self.state.idx = 0
        else:
            self.state.docs.pop(idx)
            if self.state.idx > idx:
                self.state.idx -= 1
            elif self.state.idx >= len(self.state.docs):
                self.state.idx = len(self.state.docs) - 1

        self.sync_editor()
        if self.cur_doc() is not previous:
            self._enter()
        self._rebuild()
        self._on_tabs_changed()
