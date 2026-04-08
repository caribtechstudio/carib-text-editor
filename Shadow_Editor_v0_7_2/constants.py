"""
constants.py — Constantes globales de l'application Shadow Editor.
"""

import os
import sys

APP_NAME = "Carib Text Editor"
APP_VERSION = "0.8.0"

MODE_TEXT = "text"
MODE_CALC = "calc"
MODE_READ = "read"


def resource_path(rel: str) -> str:
    """Résout un chemin relatif vers les ressources (compatible PyInstaller)."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)
