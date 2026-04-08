"""
models/voice_manager.py — Gestion Text-to-Speech et Speech-to-Text.
"""

import threading

try:
    import pyttsx3
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False

try:
    import speech_recognition as sr
    SR_AVAILABLE = True
except ImportError:
    SR_AVAILABLE = False


class VoiceManager:
    """Gère la synthèse vocale et la reconnaissance vocale."""

    def __init__(self):
        self.tts_on = False
        self.voice_on = False

    def speak_text(self, text: str) -> None:
        """Lit le texte à voix haute dans un thread."""
        self.tts_on = True

        def speak():
            try:
                eng = pyttsx3.init()
                eng.say(text)
                eng.runAndWait()
            except Exception:
                pass
            self.tts_on = False

        threading.Thread(target=speak, daemon=True).start()

    def listen_speech(self, on_result=None, on_error=None) -> None:
        """Écoute le microphone et transcrit dans un thread."""
        self.voice_on = True

        def listen():
            rec = sr.Recognizer()
            try:
                with sr.Microphone() as src:
                    audio = rec.listen(src, timeout=8, phrase_time_limit=15)
                text = rec.recognize_google(audio, language="fr-FR")
                if on_result:
                    on_result(text)
            except Exception as exc:
                if on_error:
                    on_error(exc)
            self.voice_on = False

        threading.Thread(target=listen, daemon=True).start()

    @staticmethod
    def trigger_windows_dictation(on_error=None) -> None:
        """Lance la dictée Windows (Win+H)."""
        try:
            import pyautogui
            pyautogui.hotkey("win", "h")
        except Exception as exc:
            if on_error:
                on_error(str(exc))
