"""
models/session_manager.py — Persistance de la session (options + onglets).

Sauvegarde et restaure l'état complet de l'application :
- Préférences utilisateur (thème, zoom, auto-save, etc.)
- Onglets ouverts (y compris contenu non sauvegardé)
"""

import json
import os

from models.document import Document
from models.file_manager import read_file

# Dossier de données utilisateur
_DATA_DIR = os.path.join(os.path.expanduser("~"), ".glyph")
_SESSION_FILE = os.path.join(_DATA_DIR, "session.json")


def _ensure_data_dir():
    """Crée le dossier ~/.glyph/ s'il n'existe pas."""
    try:
        os.makedirs(_DATA_DIR, exist_ok=True)
    except OSError:
        pass


def save_session(state, theme_mode: str, active_editor_content: str | None = None):
    """Sérialise l'état complet dans ~/.glyph/session.json.

    Args:
        state: EditorState courant.
        theme_mode: "light" ou "dark".
        active_editor_content: contenu actuel du widget éditeur
            (pour synchroniser avant la sauvegarde).
    """
    _ensure_data_dir()

    # Synchroniser le contenu de l'onglet actif avec le widget éditeur
    if active_editor_content is not None and state.docs:
        if 0 <= state.idx < len(state.docs):
            state.docs[state.idx].content = active_editor_content

    tabs = []
    for i, d in enumerate(state.docs):
        tab_data = {
            "title": d.title,
            "path": d.path,
            "modified": d.modified,
        }
        # Stocker le contenu si :
        # - le document n'a pas de chemin (fichier non enregistré)
        # - le document a été modifié (changements non sauvegardés sur disque)
        if not d.path or d.modified:
            tab_data["content"] = d.content
        tabs.append(tab_data)

    session = {
        "settings": {
            "theme": theme_mode,
            "auto_save": state.auto_save,
            "zoom_level": state.zoom_level,
            "show_toolbar": state.show_toolbar,
            "sidebar_collapsed": state.sidebar_collapsed,
            "mode": state.mode,
            "ai_selected_model": state.ai_selected_model,
        },
        "tabs": tabs,
        "active_tab": state.idx,
    }

    try:
        with open(_SESSION_FILE, "w", encoding="utf-8") as f:
            json.dump(session, f, ensure_ascii=False, indent=2)
    except OSError:
        pass  # Échec silencieux — ne pas bloquer l'application


def load_session() -> dict | None:
    """Charge la session depuis ~/.glyph/session.json.

    Returns:
        dict avec clés "settings", "tabs", "active_tab" ou None si absent/corrompu.
    """
    if not os.path.isfile(_SESSION_FILE):
        return None
    try:
        with open(_SESSION_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return None
        return data
    except (OSError, json.JSONDecodeError, ValueError):
        return None


def restore_docs(tabs_data: list) -> tuple[list[Document], int]:
    """Reconstruit la liste de Documents à partir des données de session.

    Args:
        tabs_data: liste de dicts représentant les onglets sauvegardés.

    Returns:
        (docs, nombre_de_fichiers_manquants)
    """
    docs = []
    missing_count = 0

    for tab in tabs_data:
        if not isinstance(tab, dict):
            continue

        title = tab.get("title", "Sans titre")
        path = tab.get("path")
        modified = tab.get("modified", False)
        saved_content = tab.get("content")

        if path:
            # Fichier avec chemin — tenter de relire depuis le disque
            disk_content = read_file(path)
            if disk_content is not None:
                if modified and saved_content is not None:
                    # Restaurer le contenu modifié non sauvegardé
                    content = saved_content
                else:
                    # Fichier non modifié → contenu frais depuis le disque
                    content = disk_content
                    modified = False
            else:
                # Fichier disparu ou inaccessible
                missing_count += 1
                if saved_content is not None:
                    # On a le contenu en session → le garder comme doc sans chemin
                    content = saved_content
                    path = None
                    modified = True
                else:
                    # Pas de contenu sauvé → ignorer cet onglet
                    continue
        else:
            # Document sans chemin (non sauvegardé)
            content = saved_content or ""

        docs.append(Document(title=title, content=content, path=path, modified=modified))

    return docs, missing_count
