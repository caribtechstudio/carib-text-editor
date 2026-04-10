"""
constants.py — Constantes globales de l'application Glyph.
"""

import os
import sys

APP_NAME = "Glyph"
APP_VERSION = "0.9"

MODE_TEXT = "text"
MODE_CALC = "calc"
MODE_READ = "read"


def resource_path(rel: str) -> str:
    """Résout un chemin relatif vers les ressources (compatible PyInstaller)."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)
