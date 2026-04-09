"""
views/status_bar.py — Barre de statut en bas de l'éditeur.
"""

import flet as ft

from theme import T


def build_status_bar(c, st_mode, st_msg, st_chars, st_words, st_zoom=None):
    """Construit la barre de statut."""
    right_controls = [st_chars, st_words]
    if st_zoom:
        right_controls.append(
            ft.Container(width=1, height=14, bgcolor=c(T.L_BORDER, T.D_BORDER)),
        )
        right_controls.append(st_zoom)
    return ft.Container(
        height=36, bgcolor=c(T.L_STATUS, T.D_STATUS),
        border=ft.Border.only(top=ft.BorderSide(1, c(T.L_BORDER, T.D_BORDER))),
        padding=ft.Padding(20, 0, 20, 0),
        content=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Row(spacing=16, controls=[st_mode, st_msg]),
                ft.Row(spacing=16, controls=right_controls),
            ],
        ),
    )
