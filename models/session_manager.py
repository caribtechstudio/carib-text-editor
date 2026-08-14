"""
models/session_manager.py — Persistance de la session (options + onglets).

Deux changements importants par rapport a la version precedente :

  * **L'ecriture ne bloque plus l'interface.** Elle etait synchrone et
    declenchee a chaque cran de zoom ou changement d'onglet, alors qu'elle
    serialise le contenu integral de tous les documents non enregistres.
    Elle est desormais regroupee et executee dans un thread.
  * **L'encodage et les fins de ligne sont conserves**, sinon restaurer une
    session reconvertissait silencieusement les fichiers Windows en LF.
"""

import json
import os
import threading

from models.document import Document
from models.scheduler import scheduler
from models.file_manager import (DEFAULT_ENCODING, DEFAULT_NEWLINE, load_file)

_DATA_DIR = os.path.join(os.path.expanduser("~"), ".glyph")
_SESSION_FILE = os.path.join(_DATA_DIR, "session.json")

#: Delai de regroupement des ecritures : un zoom repete ne produit qu'un seul
#: acces disque au lieu d'un par cran.
_SAVE_DEBOUNCE = 1.5

_SAVE_TASK = "session.save"
_save_lock = threading.Lock()
_pending: dict | None = None


def _ensure_data_dir():
    try:
        os.makedirs(_DATA_DIR, exist_ok=True)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------

def build_session(state, theme_mode: str,
                  active_editor_content: str | None = None) -> dict:
    """Construit l'instantane de session — **sans jamais modifier `state`**.

    Cette fonction recopiait auparavant `active_editor_content` dans
    `state.docs[state.idx]`. C'etait une course a la corruption : elle est
    appelee depuis la sauvegarde automatique, donc depuis un thread de
    travail. Entre la lecture de la valeur du widget par l'appelant et
    l'ecriture ici, l'utilisateur peut avoir change d'onglet — le texte de
    l'onglet quitte s'ecrivait alors par-dessus celui du nouvel onglet.

    La recopie est de toute facon inutile : `EditorController.on_text_changed`
    met `document.content` a jour a chaque frappe, sur le thread d'interface.
    Le document fait autorite ; le widget n'est qu'un affichage.

    Le parametre est conserve pour ne pas casser les appelants, mais il ne
    sert plus qu'a completer un document actif reste vide.
    """
    if active_editor_content and state.docs and 0 <= state.idx < len(state.docs):
        active = state.docs[state.idx]
        # Filet de securite strictement additif : on ne remplace jamais un
        # contenu existant, donc aucune frappe ne peut etre perdue ici.
        if not active.content:
            active.content = active_editor_content

    tabs = []
    for d in state.docs:
        tab = {
            "title": d.title,
            "path": d.path,
            "modified": d.modified,
            "encoding": getattr(d, "encoding", DEFAULT_ENCODING),
            "newline": getattr(d, "newline", DEFAULT_NEWLINE),
            "mtime": getattr(d, "mtime", 0.0),
            "size": getattr(d, "size", 0),
        }
        # Le contenu n'est stocke que s'il n'existe nulle part ailleurs :
        # document jamais enregistre, ou modifications en attente.
        if not d.path or d.modified:
            tab["content"] = d.content
        tabs.append(tab)

    return {
        "settings": {
            "theme": theme_mode,
            "auto_save": state.auto_save,
            "zoom_level": state.zoom_level,
            "show_toolbar": state.show_toolbar,
            "sidebar_collapsed": state.sidebar_collapsed,
            "mode": state.mode,
            "ac_enabled": state.ac_enabled,
            "recent_files": state.recent_files,
            "syntax_enabled": getattr(state, "syntax_enabled", True),
            "show_line_numbers": getattr(state, "show_line_numbers", False),
            "md_preview": getattr(state, "md_preview", False),
            "workspace_path": getattr(state, "workspace_path", ""),
            "stay_resident": getattr(state, "stay_resident", False),
        },
        "tabs": tabs,
        "active_tab": state.idx,
    }


def _write(session: dict):
    _ensure_data_dir()
    tmp = _SESSION_FILE + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            # Pas d'indentation : le fichier peut contenir des documents
            # entiers, autant ne pas tripler sa taille pour rien.
            json.dump(session, fh, ensure_ascii=False)
        os.replace(tmp, _SESSION_FILE)
    except OSError:
        pass          # echec silencieux — ne jamais bloquer l'application


def save_session(state, theme_mode: str, active_editor_content: str | None = None,
                 immediate: bool = False):
    """Planifie une sauvegarde de session.

    Args:
        immediate: ecrit tout de suite (fermeture de l'application).
    """
    global _pending

    session = build_session(state, theme_mode, active_editor_content)

    if immediate:
        scheduler.cancel(_SAVE_TASK)
        with _save_lock:
            _pending = None
        _write(session)
        return

    with _save_lock:
        _pending = session
    # Reprogrammer la meme cle remplace l'echeance : cinq crans de zoom
    # successifs ne produisent qu'une seule ecriture disque, la ou l'ancien
    # code en produisait cinq, synchrones, sur le thread d'interface.
    scheduler.schedule(_SAVE_TASK, _SAVE_DEBOUNCE, _flush_pending)


def _flush_pending():
    global _pending
    with _save_lock:
        payload = _pending
        _pending = None
    if payload is not None:
        _write(payload)


def flush_pending():
    """Force l'ecriture d'une sauvegarde en attente (avant de quitter)."""
    scheduler.cancel(_SAVE_TASK)
    _flush_pending()


# ---------------------------------------------------------------------------
# Chargement
# ---------------------------------------------------------------------------

def load_session() -> dict | None:
    """Charge ~/.glyph/session.json, ou None si absent ou corrompu."""
    if not os.path.isfile(_SESSION_FILE):
        return None
    try:
        with open(_SESSION_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError, ValueError):
        return None


def restore_docs(tabs_data: list) -> tuple[list[Document], int]:
    """Reconstruit les documents. Retourne (documents, nb_fichiers_manquants)."""
    docs: list[Document] = []
    missing = 0

    for tab in tabs_data:
        if not isinstance(tab, dict):
            continue

        title = tab.get("title", "Sans titre")
        path = tab.get("path")
        modified = bool(tab.get("modified", False))
        saved_content = tab.get("content")
        encoding = tab.get("encoding") or DEFAULT_ENCODING
        newline = tab.get("newline") or DEFAULT_NEWLINE
        mtime = float(tab.get("mtime", 0.0) or 0.0)
        size = int(tab.get("size", 0) or 0)

        if path:
            try:
                loaded = load_file(path)
            except OSError:
                loaded = None

            if loaded is not None:
                encoding, newline = loaded.encoding, loaded.newline
                mtime, size = loaded.mtime, loaded.size
                if modified and saved_content is not None:
                    content = saved_content       # travail en cours preserve
                else:
                    content = loaded.text
                    modified = False
            else:
                missing += 1
                if saved_content is None:
                    continue                      # rien a restaurer
                # Fichier disparu mais contenu connu : on le garde en
                # document sans chemin plutot que de perdre le travail.
                content = saved_content
                path = None
                modified = True
                mtime, size = 0.0, 0
        else:
            content = saved_content or ""

        docs.append(Document(
            title=title, content=content, path=path, modified=modified,
            encoding=encoding, newline=newline, mtime=mtime, size=size,
        ))

    return docs, missing
