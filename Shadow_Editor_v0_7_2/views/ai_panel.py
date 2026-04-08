"""
views/ai_panel.py — Panneau latéral des corrections IA.
"""

import flet as ft

from theme import T
from ai_checker import OLLAMA_MODEL


def build_ai_panel(state, c, callbacks):
    """
    Construit le panneau de corrections IA.

    callbacks attendus : close_ai(), apply_correction(original, replacement)
    """
    if not state.show_ai:
        return ft.Container(visible=False)

    items = []

    # Header
    items.append(ft.Container(
        padding=ft.Padding(16, 14, 16, 14),
        border=ft.Border.only(bottom=ft.BorderSide(1, c(T.L_BORDER, T.D_BORDER))),
        content=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Text("Corrections IA", size=14, weight=ft.FontWeight.W_600,
                        font_family="Nunito SemiBold",
                        color=c(T.L_PRIMARY, T.D_PRIMARY)),
                ft.IconButton(icon=ft.Icons.CLOSE, icon_size=18,
                              icon_color=c(T.L_MUTED, T.D_MUTED),
                              on_click=lambda e: callbacks["close_ai"]()),
            ],
        ),
    ))

    if state.ai_loading:
        items.append(ft.Container(
            padding=40, alignment=ft.Alignment(0, 0),
            content=ft.Column(horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=16,
                              controls=[
                ft.ProgressRing(width=32, height=32, color=c(T.L_ACCENT, T.D_ACCENT)),
                ft.Text(f"Analyse avec {OLLAMA_MODEL}…", size=13,
                        color=c(T.L_TERTIARY, T.D_TERTIARY)),
            ]),
        ))
    elif state.ai_error:
        items.append(ft.Container(
            padding=24,
            content=ft.Row(spacing=10, controls=[
                ft.Icon(ft.Icons.ERROR_OUTLINE, color=c(T.L_ERROR, T.D_ERROR), size=20),
                ft.Text(state.ai_error, size=13, color=c(T.L_ERROR, T.D_ERROR), expand=True),
            ]),
        ))
    elif state.ai_score >= 0:
        _build_results(items, state, c, callbacks)
    else:
        items.append(ft.Container(
            padding=40, alignment=ft.Alignment(0, 0),
            content=ft.Column(horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=12,
                              controls=[
                ft.Icon(ft.Icons.SPELLCHECK, size=40, color=c(T.L_MUTED, T.D_MUTED)),
                ft.Text("Appuyez sur F7", size=13, color=c(T.L_TERTIARY, T.D_TERTIARY)),
            ]),
        ))

    return ft.Container(
        width=340, bgcolor=c(T.L_SURFACE, T.D_SURFACE),
        border=ft.Border.only(left=ft.BorderSide(1, c(T.L_BORDER, T.D_BORDER))),
        shadow=ft.BoxShadow(spread_radius=0, blur_radius=12,
                            color=ft.Colors.with_opacity(0.04, ft.Colors.BLACK),
                            offset=ft.Offset(-2, 0)),
        content=ft.Column(spacing=0, expand=True, scroll=ft.ScrollMode.AUTO, controls=items),
    )


def _build_results(items, state, c, callbacks):
    """Ajoute le score, les corrections et les suggestions aux items."""
    sc = c(T.L_SUCCESS, T.D_SUCCESS) if state.ai_score >= 80 \
        else c(T.L_WARNING, T.D_WARNING) if state.ai_score >= 50 \
        else c(T.L_ERROR, T.D_ERROR)

    items.append(ft.Container(
        padding=20,
        content=ft.Column(horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8,
                          controls=[
            ft.Text(str(state.ai_score), size=36, weight=ft.FontWeight.BOLD, color=sc),
            ft.Text("Score de qualité", size=12, color=c(T.L_TERTIARY, T.D_TERTIARY)),
            ft.ProgressBar(value=state.ai_score / 100, color=sc,
                           bgcolor=c(T.L_BORDER, T.D_BORDER), bar_height=6, border_radius=3),
        ]),
    ))

    dot_colors = {"orthographe": "#DC2626", "grammaire": "#EA580C",
                  "conjugaison": "#9333EA", "accord": "#2563EB", "ponctuation": "#059669"}

    for cr in state.ai_corr:
        dc = dot_colors.get(cr.get("type", "").lower(), "#DC2626")
        items.append(ft.Container(
            padding=ft.Padding(16, 12, 16, 12),
            border=ft.Border.only(bottom=ft.BorderSide(1, c(T.L_BORDER, T.D_BORDER))),
            content=ft.Column(spacing=6, controls=[
                ft.Row(spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER,
                       controls=[
                    ft.Container(width=8, height=8, border_radius=4, bgcolor=dc),
                    ft.Text(cr["original"], size=13,
                            style=ft.TextStyle(decoration=ft.TextDecoration.LINE_THROUGH),
                            color=c(T.L_ERROR, T.D_ERROR)),
                    ft.Text("→", size=13, color=c(T.L_MUTED, T.D_MUTED)),
                    ft.Text(cr["correction"], size=13, weight=ft.FontWeight.W_500,
                            color=c(T.L_SUCCESS, T.D_SUCCESS)),
                ]),
                ft.Text(f"{cr.get('type','').capitalize()} — {cr.get('explication','')}",
                        size=11, color=c(T.L_MUTED, T.D_MUTED)),
                ft.Row(spacing=8, controls=[
                    ft.OutlinedButton("Appliquer", height=28, style=ft.ButtonStyle(
                        color=c(T.L_SUCCESS, T.D_SUCCESS),
                        side=ft.BorderSide(1, c(T.L_SUCCESS, T.D_SUCCESS)),
                        shape=ft.RoundedRectangleBorder(radius=6),
                        padding=ft.Padding(12, 0, 12, 0),
                        text_style=ft.TextStyle(size=11)),
                        on_click=lambda e, o=cr["original"], r=cr["correction"]:
                            callbacks["apply_correction"](o, r)),
                    ft.OutlinedButton("Ignorer", height=28, style=ft.ButtonStyle(
                        color=c(T.L_MUTED, T.D_MUTED),
                        side=ft.BorderSide(1, c(T.L_BORDER, T.D_BORDER)),
                        shape=ft.RoundedRectangleBorder(radius=6),
                        padding=ft.Padding(12, 0, 12, 0),
                        text_style=ft.TextStyle(size=11))),
                ]),
            ]),
        ))

    for sg in state.ai_sugg:
        items.append(ft.Container(
            padding=ft.Padding(16, 12, 16, 12),
            border=ft.Border.only(bottom=ft.BorderSide(1, c(T.L_BORDER, T.D_BORDER))),
            content=ft.Column(spacing=6, controls=[
                ft.Row(spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER,
                       controls=[
                    ft.Container(width=8, height=8, border_radius=4, bgcolor="#8B5CF6"),
                    ft.Text(sg["original"], size=13, color=c(T.L_SECONDARY, T.D_SECONDARY)),
                    ft.Text("→", size=13, color=c(T.L_MUTED, T.D_MUTED)),
                    ft.Text(sg["suggestion"], size=13, weight=ft.FontWeight.W_500,
                            color="#8B5CF6"),
                ]),
                ft.Text(f"{sg.get('type','').capitalize()} — {sg.get('explication','')}",
                        size=11, color=c(T.L_MUTED, T.D_MUTED)),
                ft.Row(spacing=8, controls=[
                    ft.OutlinedButton("Appliquer", height=28, style=ft.ButtonStyle(
                        color="#8B5CF6", side=ft.BorderSide(1, "#8B5CF6"),
                        shape=ft.RoundedRectangleBorder(radius=6),
                        padding=ft.Padding(12, 0, 12, 0),
                        text_style=ft.TextStyle(size=11)),
                        on_click=lambda e, o=sg["original"], r=sg["suggestion"]:
                            callbacks["apply_correction"](o, r)),
                    ft.OutlinedButton("Ignorer", height=28, style=ft.ButtonStyle(
                        color=c(T.L_MUTED, T.D_MUTED),
                        side=ft.BorderSide(1, c(T.L_BORDER, T.D_BORDER)),
                        shape=ft.RoundedRectangleBorder(radius=6),
                        padding=ft.Padding(12, 0, 12, 0),
                        text_style=ft.TextStyle(size=11))),
                ]),
            ]),
        ))

    if not state.ai_corr and not state.ai_sugg:
        items.append(ft.Container(
            padding=24, alignment=ft.Alignment(0, 0),
            content=ft.Column(horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8,
                              controls=[
                ft.Text("✨", size=32),
                ft.Text("Texte parfait !", size=14, weight=ft.FontWeight.W_500,
                        color=c(T.L_SUCCESS, T.D_SUCCESS)),
            ]),
        ))
