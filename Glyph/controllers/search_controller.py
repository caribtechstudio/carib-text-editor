"""
controllers/search_controller.py — Logique de recherche dans le texte.
"""

import flet as ft


class SearchController:
    """Gère la recherche : exécution, navigation, mise à jour de la status bar."""

    def __init__(self, state, editor, search_state, tab_ctrl,
                 update_status, rebuild, page, show_snack=None,
                 refresh_layer=None):
        self._snack = show_snack
        self._state = state
        self._editor = editor
        self._search = search_state
        self._tab = tab_ctrl
        self._update_status = update_status
        self._rebuild = rebuild
        #: Redessine la couche de surlignage sans toucher au reste de
        #: l'interface — en particulier sans recréer le champ de recherche.
        self._refresh_layer = refresh_layer or rebuild
        self._page = page
        #: Compteur « 1/5 » de la barre de recherche. Contrôle persistant :
        #: sa valeur est écrite en place, la barre n'est jamais reconstruite
        #: pendant la saisie (sinon le champ perdrait le focus).
        self.counter_ref = None

    # ------------------------------------------------------------------
    # Ouverture / Fermeture
    # ------------------------------------------------------------------
    @property
    def visible(self) -> bool:
        """La barre de recherche est-elle affichée ?

        Exposée pour que les appelants n'aient pas à traverser deux niveaux
        de champs privés (`ctrl._search._search.visible`).
        """
        return self._search.visible

    def toggle_search(self):
        if self._search.visible and not self._search.replace_visible:
            self.close_search()
        else:
            self._search.replace_visible = False
            self.open_search()

    def toggle_replace(self):
        """Ctrl+H — ouvre la recherche avec le champ de remplacement deplie."""
        if self._search.visible and self._search.replace_visible:
            self.close_search()
            return
        self._search.visible = True
        self._search.replace_visible = True
        self._rebuild()

    def open_search(self):
        self._search.visible = True
        self._rebuild()

    def seed_query(self, text: str):
        """Pre-remplit la recherche (ex. : la selection courante)."""
        if text and "\n" not in text and len(text) <= 200:
            self._search.query = text

    def close_search(self):
        self._search.reset()
        self._clear_selection()
        self._update_status()
        self._rebuild()

    # ------------------------------------------------------------------
    # Recherche (sans rebuild — mise à jour légère)
    # ------------------------------------------------------------------
    def on_query_change(self, e):
        self._search.query = e.control.value
        self._search_and_update()

    def _search_and_update(self):
        """Exécute la recherche et met à jour le surlignage.

        L'ancienne version reconstruisait toute l'interface dès que l'on
        passait de « aucun résultat » à « au moins un » — donc typiquement au
        troisième caractère tapé. Cela recréait le champ de recherche
        lui-même, qui perdait alors le focus en pleine saisie.

        La couche de surlignage étant désormais un contrôle permanent, il n'y
        a plus de structure à créer ni à détruire : on remplace ses spans.
        """
        d = self._tab.cur_doc()
        if not d:
            return
        self._search.search(d.content)
        self._select_current_match()
        self._refresh_layer()
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
        self._refresh_layer()
        self._refresh_counter()
        self._update_status()
        self._page.update()

    def go_prev(self):
        self._search.go_prev()
        self._select_current_match()
        self._focus_editor()
        self._refresh_layer()
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
    # Remplacement
    # ------------------------------------------------------------------
    def on_replacement_change(self, e):
        self._search.replacement = e.control.value or ""

    def replace_current(self, e=None):
        """Remplace l'occurrence courante puis passe a la suivante."""
        d = self._tab.cur_doc()
        if not d or not self._search.query:
            return
        self._tab.save_content()

        new_text, replaced = self._search.replace_current(d.content)
        if not replaced:
            return

        d.apply_change(new_text)
        d.modified = True
        self._editor.value = new_text
        self._select_current_match()
        self._rebuild()

    def replace_all(self, e=None):
        """Remplace toutes les occurrences en une seule etape annulable."""
        d = self._tab.cur_doc()
        if not d or not self._search.query:
            return
        self._tab.save_content()

        new_text, count = self._search.replace_all(d.content)
        if not count:
            self._notify("Aucune occurrence a remplacer.")
            return

        d.apply_change(new_text)
        d.modified = True
        self._editor.value = new_text
        self._select_current_match()
        self._rebuild()
        self._notify(f"{count} occurrence(s) remplacee(s).")

    def _notify(self, message: str):
        if self._snack:
            self._snack(message)

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
    # Compteur dans la barre de recherche
    # ------------------------------------------------------------------
    def _refresh_counter(self):
        """Met à jour le widget compteur sans rebuild."""
        if not self.counter_ref:
            return
        from core.theme import T
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
