"""
models/editor_state.py — État global de l'éditeur.
"""

from constants import MODE_TEXT
from models.search_state import SearchState


class EditorState:
    """Centralise tout l'état applicatif de l'éditeur."""

    def __init__(self):
        self.docs: list = []
        self.idx: int = 0
        self.mode: str = MODE_TEXT
        self.show_ai: bool = False
        self.sidebar_key: str = "docs"
        self.sidebar_collapsed: bool = True

        # État du panneau IA
        self.ai_corr: list = []
        self.ai_sugg: list = []
        self.ai_score: int = -1
        self.ai_loading: bool = False
        self.ai_error: str = ""
        self.checker = None

        # Barre d'outils
        self.show_toolbar: bool = True

        # Sauvegarde automatique
        self.auto_save: bool = False

        # Zoom
        self.zoom_level: int = 100  # 50–200 %, pas de 10

        # Recherche
        self.search = SearchState()
