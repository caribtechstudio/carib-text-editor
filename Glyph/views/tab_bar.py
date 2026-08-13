"""
views/tab_bar.py — Barre d'onglets des documents.
"""

import flet as ft

from constants import (ICON_XS, ICON_SM, ICON_MD, svg_icon, svg_icon_btn, UI_FONT, UI_FONT_STRONG)
from theme import T


def build_tab_bar(state, c, callbacks):
    """
    Construit la barre d'onglets.

    callbacks attendus : switch_tab(idx), close_tab(idx), add_tab()
    """
    tabs = []
    for i, d in enumerate(state.docs):
        active = (i == state.idx)
        title = d.title + (" •" if d.modified else "")
        tabs.append(ft.Container(
            on_click=lambda e, idx=i: callbacks["switch_tab"](idx),
            padding=ft.Padding(14, 8, 6, 8),
            border=ft.Border.only(
                bottom=ft.BorderSide(2, c(T.L_ACCENT, T.D_ACCENT) if active
                                     else ft.Colors.TRANSPARENT)
            ),
            ink=True,
            content=ft.Row(spacing=6, controls=[
                svg_icon("document", size=ICON_SM,
                         color=c(T.L_ACCENT, T.D_ACCENT) if active
                         else c(T.L_TERTIARY, T.D_TERTIARY)),
                ft.Text(title, size=13,
                        font_family=UI_FONT_STRONG if active else UI_FONT,
                        weight=ft.FontWeight.W_700 if active else ft.FontWeight.W_600,
                        color=c(T.L_PRIMARY, T.D_PRIMARY) if active
                        else c(T.L_TERTIARY, T.D_TERTIARY)),
                ft.IconButton(
                    icon=ft.Icons.CLOSE, icon_size=14,
                    icon_color=c(T.L_MUTED, T.D_MUTED), tooltip="Fermer",
                    style=ft.ButtonStyle(padding=2, shape=ft.RoundedRectangleBorder(radius=4)),
                    on_click=lambda e, idx=i: callbacks["close_tab"](idx),
                ),
            ]),
        ))

    return ft.Container(
        border=ft.Border.only(bottom=ft.BorderSide(1, c(T.L_BORDER, T.D_BORDER))),
        bgcolor=c(T.L_BG, T.D_BG), padding=ft.Padding(8, 0, 0, 0),
        content=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Row(spacing=0, scroll=ft.ScrollMode.AUTO, expand=True, controls=tabs),
                ft.Container(
                    padding=ft.Padding(0, 0, 8, 0),
                    content=svg_icon_btn("add", size=ICON_SM,
                        color=c(T.L_TERTIARY, T.D_TERTIARY),
                        tooltip="Nouvel onglet", padding=6,
                        on_click=lambda e: callbacks["add_tab"]()),
                ),
            ],
        ),
    )
