"""
views/command_bar.py — Barre de commande IA (Ctrl+K).

Un seul raccourci remplace les huit boutons de la barre d'outils :
l'utilisateur sélectionne du texte, appuie sur Ctrl+K, et décrit ce qu'il
veut en français. Les actions prédéfinies restent accessibles en un clic,
sous forme de puces, pour ceux qui préfèrent ne pas taper.

C'est le modèle de Notion AI et de Cursor : une intention exprimée
librement, au lieu d'un menu à explorer.
"""

import flet as ft

from core.constants import ICON_SM, svg_icon, UI_FONT, UI_FONT, UI_FONT_STRONG
from core.theme import T

#: Actions proposées sous le champ. Le libellé est ce que voit l'utilisateur,
#: la clé est le mode IA correspondant.
QUICK_ACTIONS = (
    ("Corriger", "correction"),
    ("Reformuler", "reformulate"),
    ("Ton naturel", "natural"),
    ("Ton pro", "professional"),
    ("Résumer", "summarize"),
    ("FR → EN", "translate_fr_en"),
    ("EN → FR", "translate_en_fr"),
    ("Mots-clés", "keywords"),
)


def build_command_bar(state, c, callbacks, scope_label: str, provider_label: str):
    """Construit la barre Ctrl+K.

    callbacks attendus :
        on_query_change, on_submit, on_close, run_mode(mode)
    """
    field = ft.TextField(
        value=state.kbar_query,
        hint_text="Que voulez-vous faire de ce texte ?",
        hint_style=ft.TextStyle(size=14, font_family=UI_FONT,
                                color=c(T.L_MUTED, T.D_MUTED), italic=True),
        text_size=14,
        text_style=ft.TextStyle(size=14, font_family=UI_FONT,
                                color=c(T.L_PRIMARY, T.D_PRIMARY)),
        border=ft.InputBorder.NONE,
        content_padding=ft.Padding(4, 0, 4, 0),
        cursor_color=c(T.L_ACCENT, T.D_ACCENT),
        cursor_height=18, cursor_width=1.5,
        bgcolor=ft.Colors.TRANSPARENT,
        focused_bgcolor=ft.Colors.TRANSPARENT,
        hover_color=ft.Colors.TRANSPARENT,
        expand=True, autofocus=True,
        on_change=callbacks["on_query_change"],
        on_submit=lambda e: callbacks["on_submit"](),
    )

    def chip(label, mode):
        return ft.Container(
            padding=ft.Padding(10, 5, 10, 5), border_radius=14,
            bgcolor=c(T.L_HOVER, T.D_HOVER), ink=True,
            on_click=lambda e, m=mode: callbacks["run_mode"](m),
            content=ft.Text(label, size=11, font_family=UI_FONT_STRONG,
                            color=c(T.L_SECONDARY, T.D_SECONDARY)),
        )

    header = ft.Row(
        spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            svg_icon("sparkles", size=ICON_SM, color=c(T.L_ACCENT, T.D_ACCENT)),
            field,
            ft.Container(
                padding=ft.Padding(8, 3, 8, 3), border_radius=10,
                bgcolor=c(T.L_ACCENT_LT, T.D_ACCENT_LT),
                content=ft.Text("Entrée", size=10, font_family=UI_FONT_STRONG,
                                color=c(T.L_ACCENT, T.D_ACCENT))),
            ft.IconButton(
                icon=ft.Icons.CLOSE, icon_size=ICON_SM,
                icon_color=c(T.L_TERTIARY, T.D_TERTIARY),
                tooltip="Fermer  Échap",
                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=4),
                                     padding=2),
                on_click=lambda e: callbacks["on_close"]()),
        ],
    )

    # Ligne de contexte : sur quoi l'action va s'appliquer, et où part le texte.
    # C'est cette transparence qui rend l'IA acceptable dans un éditeur de texte.
    context_row = ft.Row(
        spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.Text(scope_label, size=10, font_family=UI_FONT,
                    color=c(T.L_MUTED, T.D_MUTED)),
            ft.Container(width=1, height=10, bgcolor=c(T.L_BORDER, T.D_BORDER)),
            ft.Text(provider_label, size=10, font_family=UI_FONT,
                    color=c(T.L_MUTED, T.D_MUTED)),
        ],
    )

    chips = ft.Row(spacing=6, wrap=True,
                   controls=[chip(label, mode) for label, mode in QUICK_ACTIONS])

    inner = ft.Container(
        padding=ft.Padding(14, 10, 10, 12), border_radius=12,
        bgcolor=c(T.L_SURFACE, T.D_SURFACE),
        border=ft.Border.all(1, c(T.L_ACCENT, T.D_ACCENT)),
        shadow=ft.BoxShadow(spread_radius=0, blur_radius=24,
                            color=ft.Colors.with_opacity(0.16, ft.Colors.BLACK),
                            offset=ft.Offset(0, 8)),
        content=ft.Column(spacing=10, tight=True,
                          controls=[header, context_row, chips]),
    )

    return ft.Container(
        content=ft.Container(content=inner, width=620),
        alignment=ft.Alignment(0, -0.55),
        padding=ft.Padding(40, 0, 40, 0),
    )
