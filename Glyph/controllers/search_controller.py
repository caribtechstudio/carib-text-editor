"""
controllers/search_controller.py — Logique de recherche dans le texte.
"""

import flet as ft


class SearchController:
    """Gère la recherche : exécution, navigation, mise à jour de la status bar."""

    def __init__(self, state, editor, search_state, tab_ctrl,
                 update_status, rebuild, page):
        self._state = state
        self._editor = editor
        self._search = search_state
        self._tab = tab_ctrl
        self._update_status = update_status
        self._rebuild = rebuild
        self._page = page
        # Widgets persistants mis à jour sans rebuild
        self.counter_ref = None        # ft.Text — compteur "1/5"
        self.highlight_container = None  # ft.Container — couche highlight
        self._c = None                  # theme helper, défini par app_controller

    # ------------------------------------------------------------------
    # Ouverture / Fermeture
    # ------------------------------------------------------------------
    def toggle_search(self):
        if self._search.visible:
            self.close_search()
        else:
            self.open_search()

    def open_search(self):
        self._search.visible = True
        self._rebuild()

    def close_search(self):
        self._search.reset()
        self._clear_selection()
        self._update_status()
        self.highlight_container = None
        self._rebuild()

    # ------------------------------------------------------------------
    # Recherche (sans rebuild — mise à jour légère)
    # ------------------------------------------------------------------
    def on_query_change(self, e):
        self._search.query = e.control.value
        self._search_and_update()

    def _search_and_update(self):
        """Exécute la recherche et met à jour le highlight.

        Si la structure change (passage de 0→N matches ou N→0 matches),
        un rebuild complet est nécessaire pour créer/détruire le Stack.
        Sinon, mise à jour légère des spans sans rebuild.
        """
        had_matches = bool(self._search.matches)
        d = self._tab.cur_doc()
        if not d:
            return
        self._search.search(d.content)
        has_matches = bool(self._search.matches)

        # Structure change → rebuild (crée ou détruit le Stack overlay)
        if had_matches != has_matches:
            self._select_current_match()
            self._rebuild()
            return

        # Même structure → mise à jour légère
        self._select_current_match()
        self._refresh_highlight(d.content)
        self._refresh_counter()
        self._update_status()
        self._page.update()

    # ------------------------------------------------------------------
    # Recherche (avec rebuild — pour toggles d'options)
    # ------------------------------------------------------------------
    def _execute_search_rebuild(self):
        d = self._tab.cur_doc()
        if not d:
            return
        self._search.search(d.content)
        self._select_current_match()
        self._rebuild()

    # ------------------------------------------------------------------
    # Navigation — focus l'éditeur pour rendre la sélection visible
    # ------------------------------------------------------------------
    def go_next(self):
        self._search.go_next()
        self._select_current_match()
        self._focus_editor()
        self._refresh_highlight_current()
        self._refresh_counter()
        self._update_status()
        self._page.update()

    def go_prev(self):
        self._search.go_prev()
        self._select_current_match()
        self._focus_editor()
        self._refresh_highlight_current()
        self._refresh_counter()
        self._update_status()
        self._page.update()

    # ------------------------------------------------------------------
    # Options toggles (besoin de rebuild pour changer l'état visuel)
    # ------------------------------------------------------------------
    def toggle_case(self):
        self._search.case_sensitive = not self._search.case_sensitive
        self._execute_search_rebuild()

    def toggle_whole_word(self):
        self._search.whole_word = not self._search.whole_word
        self._execute_search_rebuild()

    def toggle_regex(self):
        self._search.use_regex = not self._search.use_regex
        self._execute_search_rebuild()

    # ------------------------------------------------------------------
    # Sélection dans l'éditeur
    # ------------------------------------------------------------------
    def _select_current_match(self):
        match = self._search.current_match()
        if match:
            start, end = match
            self._editor.selection = ft.TextSelection(
                base_offset=start, extent_offset=end,
            )
        else:
            self._clear_selection()

    def _focus_editor(self):
        """Donne le focus à l'éditeur pour rendre la sélection visible."""
        self._editor.focus()

    def _clear_selection(self):
        text = self._editor.value or ""
        cursor = len(text)
        self._editor.selection = ft.TextSelection(
            base_offset=cursor, extent_offset=cursor,
        )

    # ------------------------------------------------------------------
    # Highlight layer — mise à jour sans rebuild
    # ------------------------------------------------------------------
    def _refresh_highlight(self, text):
        """Reconstruit les spans de la couche highlight."""
        if not self.highlight_container or not self._c:
            return
        from views.search_bar import build_highlight_text
        self.highlight_container.content = build_highlight_text(
            text, self._search.matches, self._search.current_index, self._c,
        )

    def _refresh_highlight_current(self):
        """Rafraîchit le highlight pour refléter le match courant."""
        d = self._tab.cur_doc()
        if not d:
            return
        self._refresh_highlight(d.content)

    # ------------------------------------------------------------------
    # Compteur dans la barre de recherche
    # ------------------------------------------------------------------
    def _refresh_counter(self):
        """Met à jour le widget compteur sans rebuild."""
        if not self.counter_ref:
            return
        from theme import T
        s = self._search
        self.counter_ref.value = s.label
        if s.matches:
            self.counter_ref.color = (self._page.theme_mode == ft.ThemeMode.DARK
                                      and T.D_ACCENT or T.L_ACCENT)
        else:
            self.counter_ref.color = (self._page.theme_mode == ft.ThemeMode.DARK
                                      and T.D_MUTED or T.L_MUTED)

    # ------------------------------------------------------------------
    # Appelé quand on change d'onglet
    # ------------------------------------------------------------------
    def on_tab_switch(self):
        """Relance la recherche sur le contenu du nouvel onglet."""
        if self._search.visible and self._search.query:
            self._search_and_update()
