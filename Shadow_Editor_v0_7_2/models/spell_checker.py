"""
models/spell_checker.py — Wrapper autour de pyspellchecker.
"""

try:
    from spellchecker import SpellChecker
    SPELL_AVAILABLE = True
except ImportError:
    SPELL_AVAILABLE = False


class SpellCheckerWrapper:
    """Correcteur orthographique simple avec fallback si pyspellchecker absent."""

    def __init__(self, dictionary_path: str | None = None):
        self.spell = None
        if SPELL_AVAILABLE and dictionary_path:
            try:
                self.spell = SpellChecker(local_dictionary=dictionary_path)
            except Exception:
                pass

    @property
    def available(self) -> bool:
        return self.spell is not None

    def check(self, text: str) -> list[str]:
        """Retourne la liste des mots inconnus."""
        if not self.spell:
            return []
        return list(self.spell.unknown(text.split()))
