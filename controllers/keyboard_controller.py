"""
controllers/keyboard_controller.py -- Dispatch des raccourcis clavier.

L'ordre de traitement est significatif : les surcouches (revue de diff,
palette, barre Ctrl+K, autocomplétion) capturent les touches avant que
l'éditeur ne les voie.
"""

import flet as ft


class KeyboardController:
    """Mappe les raccourcis clavier aux actions correspondantes."""

    def __init__(self, page, c, tab_ctrl, file_ctrl, ai_ctrl, voice_ctrl,
                 check_spelling, show_emoji_picker, request_close,
                 toggle_toolbar=None, undo=None, redo=None,
                 search_ctrl=None, zoom_in=None, zoom_out=None,
                 set_mode=None, autocomplete_ctrl=None, ai_ux=None,
                 goto_line=None, close_tab=None, show_help_fn=None,
                 toggle_md_preview=None, zoom_reset=None):
        self._page = page
        self._c = c
        self._tab = tab_ctrl
        self._file = file_ctrl
        self._ai = ai_ctrl
        self._voice = voice_ctrl
        self._check_spelling = check_spelling
        self._show_emoji_picker = show_emoji_picker
        self._request_close = request_close
        self._toggle_toolbar = toggle_toolbar
        self._undo = undo
        self._redo = redo
        self._search = search_ctrl
        self._zoom_in = zoom_in
        self._zoom_out = zoom_out
        self._zoom_reset = zoom_reset
        self._set_mode = set_mode
        self._ac = autocomplete_ctrl
        self._ux = ai_ux
        self._goto_line = goto_line
        self._close_tab = close_tab
        self._show_help = show_help_fn
        self._toggle_md_preview = toggle_md_preview

    # ------------------------------------------------------------------
    async def on_keyboard_event(self, e: ft.KeyboardEvent):
        if self._handle_overlays(e):
            return
        if self._handle_ctrl_shift(e):
            return
        if await self._handle_ctrl(e):
            return
        self._handle_function_keys(e)

    # ------------------------------------------------------------------
    # Surcouches — elles ont la priorité absolue
    # ------------------------------------------------------------------
    def _handle_overlays(self, e) -> bool:
        state = self._ux.state if self._ux else None

        # 1. Revue de modification IA : Tab accepte, Échap refuse.
        if state and state.diff_active:
            if e.key == "Tab":
                self._ux.accept_diff()
                return True
            if e.key == "Escape":
                self._ux.reject_diff()
                return True
            return True          # tout le reste est neutralisé pendant la revue

        # 2. Palette de commandes.
        if state and state.palette_visible:
            if e.key == "Escape":
                self._ux.close_palette()
                return True
            if e.key == "Arrow Down":
                self._ux.navigate_palette(1)
                return True
            if e.key == "Arrow Up":
                self._ux.navigate_palette(-1)
                return True
            if e.key in ("Enter", "Numpad Enter"):
                self._ux.run_palette_selection()
                return True
            return False         # la frappe alimente le champ de recherche

        # 3. Barre Ctrl+K.
        if state and state.kbar_visible:
            if e.key == "Escape":
                self._ux.close_command_bar()
                return True
            return False

        # 4. Suggestion en texte fantôme.
        #    Tab l'accepte entièrement, Ctrl+→ un seul mot, Échap l'écarte.
        #    Les flèches restent à l'éditeur : on ne détourne plus la
        #    navigation dans le texte pour choisir dans une liste.
        if self._ac and self._ac.has_suggestion:
            if e.key == "Tab" and self._ac.accept():
                return True
            if e.key == "Arrow Right" and e.ctrl and self._ac.accept_word():
                return True
            if e.key == "Escape":
                self._ac.dismiss()
                return True

        # 5. Échap ferme la recherche.
        if e.key == "Escape" and self._search and self._search.visible:
            self._search.close_search()
            return True

        return False

    # ------------------------------------------------------------------
    # Ctrl + Maj
    # ------------------------------------------------------------------
    def _handle_ctrl_shift(self, e) -> bool:
        if not (e.ctrl and e.shift):
            return False

        if e.key == "P":
            if self._ux:
                self._ux.toggle_palette()
            return True
        if e.key == "Tab":
            self._tab.prev_tab()
            return True
        if e.key == "M":
            if self._toggle_md_preview:
                self._toggle_md_preview()
            return True
        return False

    # ------------------------------------------------------------------
    # Ctrl
    # ------------------------------------------------------------------
    async def _handle_ctrl(self, e) -> bool:
        if not e.ctrl:
            return False

        # Ctrl+Maj+S est géré ici pour rester avant Ctrl+S.
        if e.shift and e.key == "S":
            await self._file.save_file_as()
            return True

        key = e.key
        if key == "K":
            if self._ux:
                self._ux.toggle_command_bar()
        elif key == "F":
            if self._search:
                self._search.toggle_search()
        elif key == "H":
            if self._search:
                self._search.toggle_replace()
        elif key == "G":
            if self._goto_line:
                self._goto_line()
        elif key == "N":
            self._tab.add_tab()
        elif key == "W":
            if self._close_tab:
                self._close_tab()
        elif key == "Tab":
            self._tab.next_tab()
        elif key == "O":
            await self._file.open_file()
        elif key == "S":
            await self._file.save_file()
        elif key == "E":
            self._show_emoji_picker()
        elif key == "P":
            self._file.print_file()
        elif key == "Z":
            if self._undo:
                self._undo()
        elif key == "Y":
            if self._redo:
                self._redo()
        elif key == "T":
            if self._toggle_toolbar:
                self._toggle_toolbar()
        elif key in ("Numpad Add", "+", "="):
            if self._zoom_in:
                self._zoom_in()
        elif key in ("Numpad Subtract", "-"):
            if self._zoom_out:
                self._zoom_out()
        elif key in ("Numpad 0", "0"):
            if self._zoom_reset:
                self._zoom_reset()
        elif key == "1":
            if self._set_mode:
                self._set_mode("text")
        elif key == "2":
            if self._set_mode:
                self._set_mode("calc")
        elif key == "3":
            if self._set_mode:
                self._set_mode("read")
        else:
            return False
        return True

    # ------------------------------------------------------------------
    # Touches de fonction
    # ------------------------------------------------------------------
    def _handle_function_keys(self, e):
        if e.key == "F1":
            if self._show_help:
                self._show_help()
        elif e.key == "F3":
            self._voice.read_text()
        elif e.key in ("F4", "F5"):
            # F5 reste accepté : c'était le raccourci de la dictée Windows
            # avant que celle-ci ne devienne le seul mode de dictée.
            self._voice.dictation()
        elif e.key == "F6":
            self._check_spelling()
        elif e.key == "F7":
            self._ai.run_correction()
        elif e.key == "F8":
            self._ai.run_translate_fr_en()
        elif e.key == "F9":
            self._ai.run_reformulate()
