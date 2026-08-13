"""
controllers/session_controller.py — Persistance de l'état applicatif.

Extrait d'`AppController` : lecture des préférences au démarrage, écriture
regroupée pendant l'usage, restauration des onglets, liste des fichiers
récents et dossier de travail.

Le découpage suit une frontière nette : ce module traduit entre
`EditorState` et le disque, et ne touche jamais à la mise en page.
"""

import os

from models.session_manager import (build_session, flush_pending, load_session,
                                    restore_docs, save_session)

VALID_MODES = ("text", "calc", "read")


class SessionController:
    """Charge, applique et enregistre la session."""

    def __init__(self, page, state, get_editor_value, is_dark):
        self._page = page
        self.state = state
        self._editor_value = get_editor_value
        self._is_dark = is_dark
        #: Instantané lu au démarrage, libéré une fois appliqué.
        self._data = load_session()

    # ==================================================================
    # Écriture
    # ==================================================================
    def save(self):
        """Planifie une écriture (regroupée, hors du thread d'interface)."""
        save_session(self.state, self._theme(), self._editor_value())

    def save_now(self):
        """Écrit immédiatement — fermeture de l'application."""
        save_session(self.state, self._theme(), self._editor_value(), immediate=True)
        flush_pending()

    def _theme(self) -> str:
        return "dark" if self._is_dark() else "light"

    def snapshot(self) -> dict:
        """Instantané en mémoire, sans accès disque (utile aux tests)."""
        return build_session(self.state, self._theme(), self._editor_value())

    # ==================================================================
    # Lecture
    # ==================================================================
    def apply_settings(self):
        """Applique les préférences. À appeler avant le premier rendu."""
        import flet as ft

        data = self._data
        if not data or "settings" not in data:
            return
        s = data["settings"]
        state = self.state

        self._page.theme_mode = (ft.ThemeMode.DARK if s.get("theme") == "dark"
                                 else ft.ThemeMode.LIGHT)
        state.auto_save = bool(s.get("auto_save", False))

        zoom = s.get("zoom_level", 100)
        if isinstance(zoom, (int, float)) and 50 <= zoom <= 200:
            state.zoom_level = int(zoom)

        state.show_toolbar = bool(s.get("show_toolbar", True))
        state.sidebar_collapsed = bool(s.get("sidebar_collapsed", True))
        if s.get("mode") in VALID_MODES:
            state.mode = s["mode"]

        for key in ("ac_enabled", "syntax_enabled", "show_line_numbers",
                    "md_preview", "stay_resident"):
            if key in s:
                setattr(state, key, bool(s[key]))

        workspace = s.get("workspace_path", "")
        if isinstance(workspace, str) and workspace and os.path.isdir(workspace):
            state.workspace_path = workspace

        # Un fichier récent disparu du disque ne doit plus être proposé.
        recent = s.get("recent_files", [])
        if isinstance(recent, list):
            state.recent_files = [p for p in recent
                                  if isinstance(p, str) and os.path.isfile(p)]

    def restore_tabs(self) -> tuple[bool, int]:
        """Restaure les onglets. Retourne (a_restauré, nb_fichiers_manquants)."""
        data = self._data
        if not data or not isinstance(data.get("tabs"), list) or not data["tabs"]:
            return False, 0

        docs, missing = restore_docs(data["tabs"])
        if not docs:
            return False, missing

        self.state.docs = docs
        active = data.get("active_tab", 0)
        self.state.idx = (active if isinstance(active, int) and 0 <= active < len(docs)
                          else 0)
        return True, missing

    def release(self):
        """Libère l'instantané de démarrage : il peut peser des mégaoctets."""
        self._data = None

    # ==================================================================
    # Fichiers récents et espace de travail
    # ==================================================================
    def push_recent(self, path: str):
        self.state.push_recent(path)

    def open_workspace(self, path: str) -> bool:
        if not path or not os.path.isdir(path):
            return False
        self.state.workspace_path = path
        self.state.workspace_expanded_dirs = set()
        return True

    def close_workspace(self):
        self.state.workspace_path = ""
        self.state.workspace_expanded_dirs = set()

    def toggle_workspace_dir(self, path: str):
        key = os.path.normcase(path)
        expanded = self.state.workspace_expanded_dirs
        expanded.discard(key) if key in expanded else expanded.add(key)
