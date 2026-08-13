"""
views/status_bar.py — Barre de statut en bas de l'éditeur.

Elle porte désormais deux informations que tous les bons éditeurs affichent
et que Glyph omettait — la position du curseur et l'encodage du fichier —
ainsi qu'un badge IA qui indique en permanence **où part le texte** et **ce
que ça coûte**. C'est cette transparence permanente qui rend une IA
acceptable dans un outil où l'on écrit des choses privées.
"""

import flet as ft

from constants import UI_FONT

from theme import T


def _sep(c):
    return ft.Container(width=1, height=14, bgcolor=c(T.L_BORDER, T.D_BORDER))


def build_status_bar(c, st_mode, st_msg, st_chars, st_words, st_zoom=None,
                     st_pos=None, st_encoding=None, ai_badge=None):
    """Construit la barre de statut.

    Args:
        st_pos: widget « Ln 12, Col 4 ».
        st_encoding: widget « UTF-8 · CRLF ».
        ai_badge: contrôle cliquable indiquant le moteur IA et le coût.
    """
    left = [st_mode, st_msg]

    right: list[ft.Control] = []
    if st_pos is not None:
        right.append(st_pos)
        right.append(_sep(c))
    right.extend([st_chars, st_words])
    if st_encoding is not None:
        right.append(_sep(c))
        right.append(st_encoding)
    if st_zoom is not None:
        right.append(_sep(c))
        right.append(st_zoom)
    if ai_badge is not None:
        right.append(_sep(c))
        right.append(ai_badge)

    return ft.Container(
        height=36, bgcolor=c(T.L_STATUS, T.D_STATUS),
        border=ft.Border.only(top=ft.BorderSide(1, c(T.L_BORDER, T.D_BORDER))),
        padding=ft.Padding(20, 0, 12, 0),
        content=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Row(spacing=16, controls=left),
                ft.Row(spacing=12, controls=right),
            ],
        ),
    )


def build_ai_badge(c, label: str, is_local: bool, warning: bool, on_click):
    """Badge IA cliquable : « ChatGPT · 0,03 € » ou « Ollama · local »."""
    if warning:
        color = c(T.L_WARNING, T.D_WARNING)
    elif is_local:
        color = c(T.L_SUCCESS, T.D_SUCCESS)
    else:
        color = c(T.L_TERTIARY, T.D_TERTIARY)

    return ft.Container(
        padding=ft.Padding(8, 3, 8, 3), border_radius=6, ink=True,
        on_click=lambda e: on_click(),
        tooltip="Configurer l'intelligence artificielle",
        content=ft.Row(spacing=6, tight=True, controls=[
            ft.Container(width=6, height=6, border_radius=3, bgcolor=color),
            ft.Text(label, size=12, font_family=UI_FONT, color=color),
        ]),
    )
