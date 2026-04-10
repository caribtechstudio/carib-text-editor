"""
controllers/editor_controller.py — Gestion du texte, emojis et calculatrice.
"""

import threading

from constants import MODE_CALC
from models.calculator import eval_safe
from my_emoji import EMOJI_DICT

AUTO_SAVE_DELAY = 3.0  # secondes après la dernière frappe
UNDO_SNAPSHOT_DELAY = 0.5  # secondes de pause avant snapshot undo


class EditorController:
    """Gère les événements de saisie dans l'éditeur."""

    def __init__(self, state, editor, cur_doc_fn, rebuild_fn, update_status_fn, page):
        self.state = state
        self.editor = editor
        self._cur_doc = cur_doc_fn
        self._rebuild = rebuild_fn
        self._update_status = update_status_fn
        self._page = page
        self._auto_save_timer: threading.Timer | None = None
        self._auto_save_callback = None  # sera défini par AppController
        self._undo_timer: threading.Timer | None = None
        self._last_snapshot: str | None = None

    def on_text_changed(self, e):
        d = self._cur_doc()
        if not d:
            return
        d.content = e.control.value or ""
        self._schedule_undo_snapshot(d)
        if not d.modified:
            d.modified = True
            self._update_status()
            self._page.update()
            self.editor.focus()
            self._schedule_auto_save()
            return
        self._update_status()
        self.check_emoji_auto()
        self.detect_calc()
        self._page.update()
        self._schedule_auto_save()

    def _schedule_undo_snapshot(self, d):
        """Debounce : capture un snapshot undo après 500ms sans frappe."""
        if self._undo_timer:
            self._undo_timer.cancel()
        # Au premier changement, on sauvegarde l'état avant modification
        if self._last_snapshot is None:
            self._last_snapshot = d.undo_stack[-1] if d.undo_stack else ""

        def _take_snapshot():
            if self._last_snapshot is not None and d.content != self._last_snapshot:
                d.push_undo(self._last_snapshot)
            self._last_snapshot = d.content

        self._undo_timer = threading.Timer(UNDO_SNAPSHOT_DELAY, _take_snapshot)
        self._undo_timer.daemon = True
        self._undo_timer.start()

    def force_snapshot(self):
        """Force un snapshot immédiat (appelé avant paste, cut, clear, etc.)."""
        if self._undo_timer:
            self._undo_timer.cancel()
            self._undo_timer = None
        d = self._cur_doc()
        if not d:
            return
        d.push_undo(d.content)
        self._last_snapshot = None

    def reset_snapshot_tracking(self):
        """Reset le suivi après un switch d'onglet."""
        if self._undo_timer:
            self._undo_timer.cancel()
            self._undo_timer = None
        self._last_snapshot = None

    def _schedule_auto_save(self):
        """Reset le timer de sauvegarde auto (debounce).

        Se déclenche pour tous les docs (avec ou sans chemin) :
        - Avec chemin → sauvegarde sur disque + session.
        - Sans chemin → sauvegarde session uniquement (contenu temporaire).
        """
        if self._auto_save_timer:
            self._auto_save_timer.cancel()
        if not self.state.auto_save or not self._auto_save_callback:
            return
        d = self._cur_doc()
        if not d:
            return
        self._auto_save_timer = threading.Timer(AUTO_SAVE_DELAY, self._trigger_auto_save)
        self._auto_save_timer.daemon = True
        self._auto_save_timer.start()

    def _trigger_auto_save(self):
        """Appelé par le timer — exécute le callback sur le thread principal."""
        if self._auto_save_callback:
            self._page.run_thread(self._auto_save_callback)

    def check_emoji_auto(self):
        d = self._cur_doc()
        if not d or not d.content:
            return
        words = d.content.split()
        if not words:
            return
        last = words[-1]
        emoji = EMOJI_DICT.get(last)
        if emoji:
            d.content = d.content.rsplit(last, 1)[0] + emoji
            self.editor.value = d.content

    def detect_calc(self):
        if self.state.mode != MODE_CALC:
            return
        d = self._cur_doc()
        if not d or not d.content:
            return
        lines = d.content.split("\n")
        last = lines[-1].strip()
        if not last.endswith("="):
            return
        expr = last[:-1].strip()
        result = eval_safe(expr)
        lines[-1] = last + " " + result
        d.content = "\n".join(lines)
        self.editor.value = d.content
