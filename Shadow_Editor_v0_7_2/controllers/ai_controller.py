"""
controllers/ai_controller.py — Orchestration du correcteur IA.
"""

import threading

from theme import T
from ai_checker import OllamaManager, GrammarChecker
from views.dialogs.setup_dialog import show_setup_dialog


class AIController:
    """Gère le lancement et l'affichage des corrections IA."""

    def __init__(self, page, state, editor, c,
                 tab_ctrl, show_snack, rebuild_fn):
        self._page = page
        self.state = state
        self.editor = editor
        self._c = c
        self._tab = tab_ctrl
        self._snack = show_snack
        self._rebuild = rebuild_fn

    def run_ai_check(self, e=None):
        self._tab.save_content()
        d = self._tab.cur_doc()
        if not d or not d.content.strip():
            self._snack("Rien à analyser.")
            return
        if not OllamaManager.is_ollama_installed():
            show_setup_dialog(self._page, self._c)
            return
        if not OllamaManager.is_server_running():
            self._snack("Démarrage d'Ollama…")
            OllamaManager.start_server()
            import time
            def retry():
                time.sleep(2.5)
                self._page.run_thread(self.run_ai_check)
            threading.Thread(target=retry, daemon=True).start()
            return
        if not OllamaManager.is_model_available():
            show_setup_dialog(self._page, self._c)
            return
        if self.state.checker and self.state.checker.is_running:
            self._snack("Analyse déjà en cours.")
            return

        self.state.show_ai = True
        self.state.ai_loading = True
        self.state.ai_error = ""
        self.state.ai_score = -1
        self.state.ai_corr = []
        self.state.ai_sugg = []
        self._rebuild()

        page = self._page
        state = self.state
        rebuild = self._rebuild

        def on_result(corr, sugg, score):
            state.ai_corr = corr
            state.ai_sugg = sugg
            state.ai_score = score
            state.ai_loading = False
            page.run_thread(rebuild)

        def on_error(msg):
            state.ai_error = msg
            state.ai_loading = False
            page.run_thread(rebuild)

        state.checker = GrammarChecker(on_result=on_result, on_error=on_error)
        state.checker.check(d.content.strip())

    def apply_correction(self, original, replacement):
        d = self._tab.cur_doc()
        if not d:
            return
        if original in d.content:
            d.content = d.content.replace(original, replacement, 1)
            self.editor.value = d.content
            d.modified = True
            self._snack(f'"{original}" → "{replacement}"',
                         self._c(T.L_SUCCESS, T.D_SUCCESS))
        else:
            self._snack(f'"{original}" introuvable.',
                         self._c(T.L_WARNING, T.D_WARNING))

    def close_ai(self):
        self.state.show_ai = False
        self._rebuild()
