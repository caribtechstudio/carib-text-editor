"""
controllers/voice_controller.py — Orchestration des fonctions vocales.
"""

from models.voice_manager import tts_available
from core.theme import T


class VoiceController:
    """Lecture à voix haute et dictée."""

    def __init__(self, page, voice, editor, c, tab_ctrl, services):
        self._page = page
        self._voice = voice
        self.editor = editor
        self._c = c
        self._tab = tab_ctrl
        self._snack = services.show_snack
        self._rebuild = services.rebuild
        self._get_cursor = services.get_cursor

    def read_text(self, e=None):
        # La disponibilité est évaluée ici, pas à l'import du module :
        # charger pyttsx3 au démarrage coûtait plusieurs centaines de ms.
        if not tts_available():
            self._snack("pyttsx3 n'est pas installé.",
                        self._c(T.L_WARNING, T.D_WARNING))
            return

        self._tab.save_content()
        d = self._tab.cur_doc()
        if not d or not d.content.strip():
            self._snack("Rien à lire.")
            return
        if self._voice.tts_on:
            self._snack("Lecture déjà en cours.")
            return

        self._snack("Lecture en cours…")
        self._voice.speak_text(
            d.content,
            on_error=lambda msg: self._page.run_thread(
                lambda: self._snack(f"Lecture impossible : {msg}",
                                    self._c(T.L_ERROR, T.D_ERROR))),
        )

    def dictation(self, e=None):
        """Dictée Windows (Win+H).

        Seul chemin de dictée depuis la 0.14.0 : la reconnaissance vocale
        Google, qui envoyait le microphone à un tiers sans consentement, a
        été retirée (voir models/voice_manager).
        """
        self._voice.trigger_windows_dictation(
            on_error=lambda msg: self._snack(msg, self._c(T.L_WARNING, T.D_WARNING)))
