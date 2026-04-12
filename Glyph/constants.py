"""
constants.py — Constantes globales de l'application Glyph.
"""

import os
import sys

import flet as ft

APP_NAME = "Glyph"
APP_VERSION = "0.10.1"

MODE_TEXT = "text"
MODE_CALC = "calc"
MODE_READ = "read"


def resource_path(rel: str) -> str:
    """Résout un chemin relatif vers les ressources (compatible PyInstaller)."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


def svg_icon(name: str, size: int = 22, color=None) -> ft.Image:
    """Crée une icône SVG depuis ressource/icon/."""
    return ft.Image(src=f"icon/{name}.svg", width=size, height=size, color=color)


def svg_icon_btn(name: str, size: int = 22, color=None, tooltip=None,
                 on_click=None, padding=6, hover_color=None) -> ft.Container:
    """Bouton cliquable avec icône SVG (remplace ft.IconButton)."""
    return ft.Container(
        width=size + padding * 2, height=size + padding * 2,
        border_radius=6, alignment=ft.Alignment(0, 0),
        ink=True, tooltip=tooltip, on_click=on_click,
        content=svg_icon(name, size=size, color=color),
    )
