"""
models/voice_manager.py — Synthèse vocale et reconnaissance vocale.

Les imports sont **différés**. `pyttsx3` tire `comtypes`/`pywin32` et
`speech_recognition` tire de quoi manipuler l'audio : au niveau module, ces
deux imports coûtaient plusieurs centaines de millisecondes **à chaque
démarrage**, alors que la plupart des sessions n'utilisent jamais la voix.

Les disponibilités sont donc évaluées à la demande, puis mémorisées.
"""

import ctypes
import sys
import threading

#: Cache des vérifications de disponibilité : None = pas encore testé.
_tts_available: bool | None = None
_sr_available: bool | None = None


def tts_available() -> bool:
    """pyttsx3 est-il installé ? (import effectué une seule fois)"""
    global _tts_available
    if _tts_available is None:
        try:
            import pyttsx3  # noqa: F401
            _tts_available = True
        except ImportError:
            _tts_available = False
    return _tts_available


def sr_available() -> bool:
    """speech_recognition est-il installé ?"""
    global _sr_available
    if _sr_available is None:
        try:
            import speech_recognition  # noqa: F401
            _sr_available = True
        except ImportError:
            _sr_available = False
    return _sr_available


class VoiceManager:
    """Synthèse et reconnaissance vocales, toujours hors du thread d'interface."""

    def __init__(self):
        self.tts_on = False
        self.voice_on = False

    # ------------------------------------------------------------------
    # Text-to-speech
    # ------------------------------------------------------------------
    def speak_text(self, text: str, on_error=None) -> None:
        """Lit le texte à voix haute dans un thread."""
        if not tts_available():
            if on_error:
                on_error("pyttsx3 n'est pas installé.")
            return

        self.tts_on = True

        def speak():
            try:
                import pyttsx3
                engine = pyttsx3.init()
                engine.say(text)
                engine.runAndWait()
            except Exception as exc:
                if on_error:
                    on_error(str(exc))
            finally:
                self.tts_on = False

        threading.Thread(target=speak, daemon=True).start()

    # ------------------------------------------------------------------
    # Speech-to-text
    # ------------------------------------------------------------------
    def listen_speech(self, on_result=None, on_error=None) -> None:
        """Écoute le micro et transcrit dans un thread."""
        if not sr_available():
            if on_error:
                on_error("speech_recognition n'est pas installé.")
            return

        self.voice_on = True

        def listen():
            try:
                import speech_recognition as sr
                recognizer = sr.Recognizer()
                with sr.Microphone() as source:
                    audio = recognizer.listen(source, timeout=8, phrase_time_limit=15)
                text = recognizer.recognize_google(audio, language="fr-FR")
                if on_result:
                    on_result(text)
            except Exception as exc:
                if on_error:
                    on_error(exc)
            finally:
                self.voice_on = False

        threading.Thread(target=listen, daemon=True).start()

    # ------------------------------------------------------------------
    # Dictée Windows
    # ------------------------------------------------------------------
    @staticmethod
    def trigger_windows_dictation(on_error=None) -> None:
        """Lance la dictée intégrée de Windows (Win+H).

        Envoyé directement via l'API Windows plutôt qu'avec `pyautogui` :
        cette bibliothèque entraînait Pillow et une pile d'automatisation
        complète — une trentaine de mégaoctets dans l'exécutable — pour
        un unique raccourci clavier.
        """
        if sys.platform != "win32":
            if on_error:
                on_error("La dictée Windows n'est disponible que sous Windows.")
            return

        VK_LWIN, VK_H = 0x5B, 0x48
        KEYEVENTF_KEYUP = 0x0002
        try:
            user32 = ctypes.windll.user32
            user32.keybd_event(VK_LWIN, 0, 0, 0)
            user32.keybd_event(VK_H, 0, 0, 0)
            user32.keybd_event(VK_H, 0, KEYEVENTF_KEYUP, 0)
            user32.keybd_event(VK_LWIN, 0, KEYEVENTF_KEYUP, 0)
        except Exception as exc:
            if on_error:
                on_error(f"Impossible de lancer la dictée Windows : {exc}")
