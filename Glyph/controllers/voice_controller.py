"""
controllers/voice_controller.py — Orchestration des fonctions vocales.
"""

from models.voice_manager import sr_available, tts_available
from theme import T


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

    def voice_typing(self, e=None):
        if not sr_available():
            self._snack("speech_recognition n'est pas installé.",
                        self._c(T.L_WARNING, T.D_WARNING))
            return
        if self._voice.voice_on:
            self._snack("Dictée déjà en cours.")
            return

        self._snack("Parlez maintenant…")
        page, editor, tab, rebuild = self._page, self.editor, self._tab, self._rebuild
        get_cursor = self._get_cursor

        def on_result(text):
            d = tab.cur_doc()
            if not d or not text:
                return

            def _apply():
                # Insertion au curseur, comme toute autre saisie.
                pos = get_cursor()
                pos = max(0, min(pos, len(d.content)))
                d.apply_change(d.content[:pos] + text + d.content[pos:])
                d.modified = True
                editor.value = d.content
                rebuild()

            page.run_thread(_apply)

        def on_error(exc):
            page.run_thread(lambda: self._snack(f"Dictée : {exc}"))

        self._voice.listen_speech(on_result=on_result, on_error=on_error)

    def voice_ms(self, e=None):
        self._voice.trigger_windows_dictation(on_error=self._snack)
