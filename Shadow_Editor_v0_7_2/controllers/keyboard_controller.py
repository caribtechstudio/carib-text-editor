"""
controllers/keyboard_controller.py — Dispatch des raccourcis clavier.
"""

import flet as ft

from views.dialogs.help_dialog import show_help


class KeyboardController:
    """Mappe les raccourcis clavier aux actions correspondantes."""

    def __init__(self, page, c, tab_ctrl, file_ctrl, ai_ctrl, voice_ctrl,
                 check_spelling, show_emoji_picker, request_close,
                 toggle_toolbar=None, undo=None, redo=None,
                 search_ctrl=None):
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

    async def on_keyboard_event(self, e: ft.KeyboardEvent):
        # Recherche : Ctrl+F ouvre/ferme, Escape ferme
        if e.ctrl and e.key == "F":
            if self._search:
                self._search.toggle_search()
            return
        if e.key == "Escape":
            if self._search and self._search._search.visible:
                self._search.close_search()
                return
        if e.ctrl and e.key == "N":
            self._tab.add_tab()
        elif e.ctrl and e.key == "O":
            await self._file.open_file()
        elif e.ctrl and e.shift and e.key == "S":
            await self._file.save_file_as()
        elif e.ctrl and e.key == "S":
            await self._file.save_file()
        elif e.ctrl and e.key == "E":
            self._show_emoji_picker()
        elif e.ctrl and e.key == "P":
            self._file.print_file()
        elif e.key == "F1":
            show_help(self._page, self._c)
        elif e.key == "F2":
            self._voice.call_assistant()
        elif e.key == "F3":
            self._voice.read_text()
        elif e.key == "F4":
            self._voice.voice_typing()
        elif e.key == "F5":
            self._voice.voice_ms()
        elif e.key == "F6":
            self._check_spelling()
        elif e.key == "F7":
            self._ai.run_ai_check()
        elif e.ctrl and e.key == "Z":
            if self._undo:
                self._undo()
        elif e.ctrl and e.key == "Y":
            if self._redo:
                self._redo()
        elif e.ctrl and e.key == "T":
            if self._toggle_toolbar:
                self._toggle_toolbar()
        elif e.alt and e.key == "F4":
            await self._request_close()
