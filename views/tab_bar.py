"""
views/tab_bar.py — Barre d'onglets des documents.
"""

import flet as ft

from core.constants import (ICON_XS, ICON_SM, RADIUS_MD, svg_icon, svg_icon_btn,
                            UI_FONT, UI_FONT_STRONG, MOTION_FAST, hover_effect)
from core.theme import T


def build_tab_bar(state, c, callbacks):
    """
    Construit la barre d'onglets.

    callbacks attendus : switch_tab(idx), close_tab(idx), add_tab()
    """
    tabs = []
    for i, d in enumerate(state.docs):
        active = (i == state.idx)
        title = d.title
        idle_bg = c(T.L_ACCENT_LT, T.D_ACCENT_LT) if active else ft.Colors.TRANSPARENT
        hover_bg = idle_bg if active else c(T.L_HOVER, T.D_HOVER)
        tabs.append(ft.Container(
            on_click=lambda e, idx=i: callbacks["switch_tab"](idx),
            height=34, padding=ft.Padding(11, 0, 6, 0),
            border_radius=RADIUS_MD,
            bgcolor=idle_bg,
            border=ft.Border.all(1, c(T.L_ACCENT, T.D_ACCENT)) if active
            else None,
            ink=True,
            scale=ft.Scale(scale=1.0),
            animate=ft.Animation(MOTION_FAST, ft.AnimationCurve.EASE_OUT),
            animate_scale=ft.Animation(MOTION_FAST, ft.AnimationCurve.EASE_OUT),
            on_hover=hover_effect(idle_bg, hover_bg, scale=1.01,
                                  hover_opacity=1.0),
            content=ft.Row(spacing=6, controls=[
                svg_icon("document", size=ICON_SM,
                         color=c(T.L_ACCENT, T.D_ACCENT) if active
                         else c(T.L_TERTIARY, T.D_TERTIARY)),
                ft.Text(title, size=13,
                        font_family=UI_FONT_STRONG if active else UI_FONT,
                        weight=ft.FontWeight.W_700 if active else ft.FontWeight.W_600,
                        color=c(T.L_PRIMARY, T.D_PRIMARY) if active
                        else c(T.L_TERTIARY, T.D_TERTIARY)),
                ft.Container(width=6, height=6, border_radius=3,
                             visible=d.modified,
                             bgcolor=c(T.L_ACCENT, T.D_ACCENT)),
                ft.Container(
                    width=22, height=22, border_radius=6, ink=True,
                    alignment=ft.Alignment(0, 0), tooltip="Fermer",
                    on_click=lambda e, idx=i: callbacks["close_tab"](idx),
                    scale=ft.Scale(scale=1.0),
                    animate_scale=ft.Animation(MOTION_FAST, ft.AnimationCurve.EASE_OUT),
                    animate_opacity=ft.Animation(MOTION_FAST, ft.AnimationCurve.EASE_OUT),
                    on_hover=hover_effect(scale=1.08, hover_opacity=0.65),
                    content=svg_icon("clear-alt", size=ICON_XS,
                                     color=c(T.L_MUTED, T.D_MUTED))),
            ]),
        ))

    ai_button = ft.Container(
        height=32, padding=ft.Padding(12, 0, 12, 0), border_radius=9,
        bgcolor=c(T.L_ACCENT, T.D_ACCENT), ink=True,
        tooltip="Demander à l’IA  Ctrl+K",
        on_click=lambda e: callbacks["open_command_bar"](),
        scale=ft.Scale(scale=1.0),
        animate_scale=ft.Animation(MOTION_FAST, ft.AnimationCurve.EASE_OUT),
        animate_opacity=ft.Animation(MOTION_FAST, ft.AnimationCurve.EASE_OUT),
        on_hover=hover_effect(scale=1.025, hover_opacity=0.90),
        content=ft.Row(spacing=7, tight=True, controls=[
            svg_icon("sparkles", size=ICON_XS, color="#FFFFFF"),
            ft.Text("Demander à l’IA", size=12.5, font_family=UI_FONT_STRONG,
                    color="#FFFFFF"),
        ]),
    )

    return ft.Container(
        height=52,
        border=ft.Border.only(bottom=ft.BorderSide(1, c(T.L_BORDER, T.D_BORDER))),
        bgcolor=c(T.L_BG, T.D_BG), padding=ft.Padding(14, 0, 12, 0),
        content=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Row(spacing=0, scroll=ft.ScrollMode.AUTO, expand=True, controls=tabs),
                ft.Row(spacing=8, controls=[
                    svg_icon_btn("add", size=ICON_SM,
                                 color=c(T.L_TERTIARY, T.D_TERTIARY),
                                 tooltip="Nouvel onglet", padding=7,
                                 on_click=lambda e: callbacks["add_tab"]()),
                    ai_button,
                ]),
            ],
        ),
    )
