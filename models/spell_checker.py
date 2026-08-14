"""
models/spell_checker.py — Correcteur orthographique local (pyspellchecker).

Le dictionnaire français pèse plusieurs mégaoctets une fois décompressé.
Le charger dans le constructeur, sur le thread d'interface, coûtait entre
0,3 et 0,8 seconde **à chaque démarrage** — alors que beaucoup
d'utilisateurs n'appuient jamais sur F6.

Il est donc chargé paresseusement, dans un thread, au premier besoin.
L'import de `spellchecker` lui-même est différé pour la même raison.
"""

import threading


class SpellCheckerWrapper:
    """Correcteur à chargement différé."""

    def __init__(self, dictionary_path: str | None = None):
        self._dictionary_path = dictionary_path
        self._spell = None
        self._load_started = False
        self._loaded = threading.Event()
        self._lock = threading.Lock()
        #: Renseigné si le chargement échoue, pour un message utile.
        self.load_error: str = ""

    # ------------------------------------------------------------------
    # Chargement
    # ------------------------------------------------------------------
    def preload(self):
        """Démarre le chargement en arrière-plan (à appeler une fois l'UI affichée)."""
        with self._lock:
            if self._load_started:
                return
            self._load_started = True
        threading.Thread(target=self._load, daemon=True).start()

    def _load(self):
        try:
            from spellchecker import SpellChecker
        except ImportError:
            self.load_error = ("pyspellchecker n'est pas installé.\n"
                               "Lancez : pip install pyspellchecker")
            self._loaded.set()
            return

        try:
            if self._dictionary_path:
                self._spell = SpellChecker(local_dictionary=self._dictionary_path)
            else:
                self._spell = SpellChecker(language="fr")
        except Exception as exc:
            self.load_error = f"Dictionnaire illisible : {exc}"
        finally:
            self._loaded.set()

    def ensure_loaded(self, timeout: float = 10.0) -> bool:
        """Force le chargement et attend qu'il aboutisse."""
        self.preload()
        self._loaded.wait(timeout)
        return self._spell is not None

    # ------------------------------------------------------------------
    # Utilisation
    # ------------------------------------------------------------------
    @property
    def available(self) -> bool:
        """True si le correcteur est prêt (ou pourra l'être)."""
        return self._spell is not None or not self._loaded.is_set()

    @property
    def ready(self) -> bool:
        return self._spell is not None

    def check(self, text: str) -> list[str]:
        """Mots inconnus du dictionnaire. Charge le dictionnaire si besoin."""
        if not self.ensure_loaded():
            return []
        from models.text_utils import iter_words
        words = {w for w in iter_words(text) if len(w) > 2}
        if not words:
            return []
        return list(self._spell.unknown(words))
