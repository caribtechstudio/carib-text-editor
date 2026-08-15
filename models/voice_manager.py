"""
models/voice_manager.py — Synthèse vocale et dictée.

Les imports sont **différés**. `pyttsx3` tire `comtypes`/`pywin32` : au
niveau module, cet import coûtait plusieurs centaines de millisecondes **à
chaque démarrage**, alors que la plupart des sessions n'utilisent jamais la
voix. La disponibilité est donc évaluée à la demande, puis mémorisée.

Note sur la dictée
------------------
Jusqu'à la 0.13.2, la dictée passait par `speech_recognition.recognize_google`.
Deux raisons de l'avoir supprimée en 0.14.0 :

  * **Confidentialité.** L'audio du microphone partait chez un tiers sans
    qu'aucun consentement ne soit demandé — le garde-fou de la couche IA ne
    couvrait que le texte, et le mode confidentiel ne bloquait pas cet envoi.
  * **Licence.** Sans argument `key`, cette fonction utilise une clé de
    démonstration Google partagée, explicitement réservée aux tests et
    révocable sans préavis. Elle n'est pas utilisable en production.

La dictée passe désormais exclusivement par celle de Windows (Win+H), qui
s'exécute sous le contrôle et les réglages de l'utilisateur. Carib n'accède
jamais lui-même au microphone.
"""

import ctypes
import logging
import sys
import threading

log = logging.getLogger(__name__)

#: Cache de la vérification de disponibilité : None = pas encore testé.
_tts_available: bool | None = None


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


class VoiceManager:
    """Synthèse vocale et dictée, toujours hors du thread d'interface."""

    def __init__(self):
        self.tts_on = False

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
    # Dictée
    # ------------------------------------------------------------------
    @staticmethod
    def trigger_windows_dictation(on_error=None) -> None:
        """Lance la dictée intégrée de Windows (Win+H).

        C'est le **seul** chemin de dictée de Carib : aucune capture audio
        n'est réalisée par l'application, et rien ne transite par un service
        tiers de son fait.

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
            log.warning("Dictée Windows indisponible : %s", exc)
            if on_error:
                on_error(f"Impossible de lancer la dictée Windows : {exc}")
