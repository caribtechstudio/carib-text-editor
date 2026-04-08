"""
views/tab_bar.py — Barre d'onglets des documents.
"""

import flet as ft

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
                ft.Icon(ft.Icons.DESCRIPTION_OUTLINED, size=15,
                        color=c(T.L_ACCENT, T.D_ACCENT) if active
                        else c(T.L_TERTIARY, T.D_TERTIARY)),
                ft.Text(title, size=13,
                        font_family="Nunito SemiBold" if active else "Nunito",
                        weight=ft.FontWeight.W_600 if active else ft.FontWeight.W_400,
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
                    content=ft.IconButton(
                        icon=ft.Icons.ADD, icon_size=18, tooltip="Nouvel onglet",
                        icon_color=c(T.L_TERTIARY, T.D_TERTIARY),
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=6), padding=6),
                        on_click=lambda e: callbacks["add_tab"](),
                    ),
                ),
            ],
        ),
    )
