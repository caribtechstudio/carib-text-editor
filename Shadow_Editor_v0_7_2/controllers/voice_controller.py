"""
controllers/voice_controller.py — Orchestration des fonctions vocales.
"""

from theme import T
from models.voice_manager import TTS_AVAILABLE, SR_AVAILABLE


class VoiceController:
    """Gère l'assistant vocal, la lecture et la dictée."""

    def __init__(self, page, voice, editor, c,
                 tab_ctrl, show_snack, rebuild_fn):
        self._page = page
        self._voice = voice
        self.editor = editor
        self._c = c
        self._tab = tab_ctrl
        self._snack = show_snack
        self._rebuild = rebuild_fn

    def call_assistant(self, e=None):
        d = self._tab.cur_doc()
        if not d:
            return
        msg = "Bonjour, je suis Glyph Assistant. Comment puis-je vous aider ?\n"
        d.content = (self.editor.value or "") + msg
        self.editor.value = d.content
        d.modified = True
        self._rebuild()
        if TTS_AVAILABLE:
            self._voice.speak_text(msg)

    def read_text(self, e=None):
        if not TTS_AVAILABLE:
            self._snack("pyttsx3 non installé.",
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
        self._voice.speak_text(d.content)

    def voice_typing(self, e=None):
        if not SR_AVAILABLE:
            self._snack("speech_recognition non installé.",
                         self._c(T.L_WARNING, T.D_WARNING))
            return
        if self._voice.voice_on:
            self._snack("Dictée en cours.")
            return
        self._snack("Parlez maintenant…")

        page = self._page
        rebuild = self._rebuild
        editor = self.editor
        tab = self._tab

        def on_result(text):
            d = tab.cur_doc()
            if d:
                d.content = (d.content or "") + text
                def _sync():
                    editor.value = d.content
                    rebuild()
                page.run_thread(_sync)

        def on_error(exc):
            snack = self._snack
            page.run_thread(lambda: snack(f"Erreur : {exc}"))

        self._voice.listen_speech(on_result=on_result, on_error=on_error)

    def voice_ms(self, e=None):
        self._voice.trigger_windows_dictation(
            on_error=lambda msg: self._snack(msg)
        )
