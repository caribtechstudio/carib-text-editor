"""
views/editor_area.py — Création du widget éditeur de texte.
"""

import flet as ft

from core.constants import EDITOR_FONT

from core.theme import T


def create_editor(c, hint_text, on_change, on_selection_change=None):
    """Crée et retourne le TextField principal de l'éditeur."""
    return ft.TextField(
        multiline=True,
        min_lines=25,
        expand=True,
        border=ft.InputBorder.NONE,
        hint_text=hint_text,
        hint_style=ft.TextStyle(
            size=16, font_family=EDITOR_FONT, letter_spacing=0.2,
            color=c(T.L_MUTED, T.D_MUTED), italic=True,
        ),
        text_size=16,
        text_style=ft.TextStyle(
            size=16, height=1.4, font_family=EDITOR_FONT, letter_spacing=0.2,
            color=c(T.L_PRIMARY, T.D_PRIMARY),
        ),
        selection_color=ft.Colors.with_opacity(0.45, c(T.L_HL_CURRENT, T.D_HL_CURRENT)),
        cursor_color=c(T.L_ACCENT, T.D_ACCENT),
        cursor_height=22,
        cursor_width=1.5,
        focused_border_color=ft.Colors.with_opacity(0.08, c(T.L_ACCENT, T.D_ACCENT)),
        content_padding=ft.Padding(40, 36, 40, 36),
        bgcolor=ft.Colors.TRANSPARENT,
        focused_bgcolor=ft.Colors.TRANSPARENT,
        hover_color=ft.Colors.TRANSPARENT,
        on_change=on_change,
        on_selection_change=on_selection_change,
    )
