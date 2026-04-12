"""
models/editor_state.py -- Etat global de l'editeur.
"""

from constants import MODE_TEXT
from models.search_state import SearchState


class EditorState:
    """Centralise tout l'etat applicatif de l'editeur."""

    def __init__(self):
        self.docs: list = []
        self.idx: int = 0
        self.mode: str = MODE_TEXT
        self.show_ai: bool = False
        self.sidebar_key: str = "docs"
        self.sidebar_collapsed: bool = True

        # ---- Etat du panneau IA (multi-mode) ----
        # Mode IA actif : correction, translate_fr_en, translate_en_fr,
        #                 reformulate, natural, professional, summarize, keywords
        self.ai_mode: str = "correction"
        self.ai_loading: bool = False
        self.ai_error: str = ""
        self.ai_result: dict = {}  # resultat brut du JSON parse

        # Correction specifique (retro-compat)
        self.ai_corr: list = []
        self.ai_sugg: list = []
        self.ai_score: int = -1

        # Traduction specifique
        self.ai_translation: str = ""
        self.ai_translation_notes: list = []

        # Reformulation / naturel / professionnel
        self.ai_reformulation: str = ""
        self.ai_reformulation_changes: list = []

        # Resume
        self.ai_summary: str = ""
        self.ai_key_points: list = []
        self.ai_reduction: str = ""

        # Mots-cles
        self.ai_theme: str = ""
        self.ai_primary_keywords: list = []
        self.ai_secondary_keywords: list = []

        # Processeur IA en cours
        self.ai_processor = None
        self.ai_elapsed: float = 0.0  # temps de reponse en secondes

        # Modele selectionne (persiste en session)
        self.ai_selected_model: str = ""

        # Barre d'outils
        self.show_toolbar: bool = True

        # Sauvegarde automatique
        self.auto_save: bool = False

        # Zoom
        self.zoom_level: int = 100  # 50-200 %, pas de 10

        # Recherche
        self.search = SearchState()

        # Autocompletion
        self.ac_enabled: bool = True          # activer/desactiver
        self.ac_suggestions: list[str] = []   # mots proposes (local)
        self.ac_ai_suggestion: str = ""       # phrase IA
        self.ac_selected: int = 0             # index selectionne dans la popup
        self.ac_visible: bool = False         # popup affichee
        self.ac_prefix: str = ""              # prefix en cours de saisie

    def clear_ai_results(self):
        """Remet a zero tous les resultats IA."""
        self.ai_loading = False
        self.ai_error = ""
        self.ai_result = {}
        self.ai_corr = []
        self.ai_sugg = []
        self.ai_score = -1
        self.ai_translation = ""
        self.ai_translation_notes = []
        self.ai_reformulation = ""
        self.ai_reformulation_changes = []
        self.ai_summary = ""
        self.ai_key_points = []
        self.ai_reduction = ""
        self.ai_theme = ""
        self.ai_primary_keywords = []
        self.ai_secondary_keywords = []

    def dispatch_ai_result(self, mode: str, data: dict):
        """Distribue le resultat JSON parse dans les champs adaptes au mode."""
        self.ai_result = data
        self.ai_error = ""

        if mode == "correction":
            self.ai_corr = self._validate_corrections(data.get("corrections", []))
            self.ai_sugg = self._validate_suggestions(data.get("suggestions", []))
            try:
                self.ai_score = max(0, min(100, int(float(data.get("score", 100)))))
            except (ValueError, TypeError):
                self.ai_score = 100

        elif mode in ("translate_fr_en", "translate_en_fr"):
            self.ai_translation = str(data.get("translation", "")).strip()
            self.ai_translation_notes = data.get("notes", [])

        elif mode in ("reformulate", "natural", "professional"):
            self.ai_reformulation = str(data.get("result", "")).strip()
            self.ai_reformulation_changes = data.get("changes", [])

        elif mode == "summarize":
            self.ai_summary = str(data.get("result", "")).strip()
            self.ai_key_points = data.get("key_points", [])
            self.ai_reduction = str(data.get("reduction", "")).strip()

        elif mode == "keywords":
            self.ai_theme = str(data.get("theme", "")).strip()
            self.ai_primary_keywords = data.get("primary_keywords", [])
            self.ai_secondary_keywords = data.get("secondary_keywords", [])

    @staticmethod
    def _validate_corrections(raw: list) -> list:
        result = []
        for c in raw:
            if not isinstance(c, dict):
                continue
            orig = str(c.get("original", "")).strip()
            corr = str(c.get("correction", "")).strip()
            if orig and corr and orig != corr:
                result.append({
                    "original":    orig,
                    "correction":  corr,
                    "type":        str(c.get("type", "orthographe")).strip(),
                    "explication": str(c.get("explication", "")).strip(),
                })
        return result

    @staticmethod
    def _validate_suggestions(raw: list) -> list:
        result = []
        for s in raw:
            if not isinstance(s, dict):
                continue
            orig = str(s.get("original", "")).strip()
            sug = str(s.get("suggestion", "")).strip()
            if orig and sug and orig != sug:
                result.append({
                    "original":    orig,
                    "suggestion":  sug,
                    "type":        str(s.get("type", "reformulation")).strip(),
                    "explication": str(s.get("explication", "")).strip(),
                })
        return result
