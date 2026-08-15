"""
views/dialogs/voice_dialog.py — Menu des fonctions vocales.
"""

import flet as ft

from core.constants import ICON_SM, UI_FONT, svg_icon

from core.theme import T
from views.dialogs._common import dlg_btn, modern_dialog, primary_button


def show_voice_menu(page, c, callbacks):
    """
    Affiche le menu vocal.

    callbacks attendus : read_text(), dictation()
    """
    content = ft.Container(
            width=360,
            content=ft.Column(spacing=8, controls=[
                dlg_btn("Lire le texte (F3)", "headphones", c,
                        lambda e: (page.pop_dialog(), callbacks["read_text"]())),
                dlg_btn("Dictée vocale (F4)", "circle-microphone-lines", c,
                        lambda e: (page.pop_dialog(), callbacks["dictation"]())),
                ft.Row(spacing=8, controls=[
                    svg_icon("shield-check", size=ICON_SM,
                             color=c(T.L_MUTED, T.D_MUTED)),
                    ft.Text(
                        "Lecture et dictée s'exécutent sur votre ordinateur. "
                        "Carib n'accède pas au microphone et n'envoie aucun son.",
                        size=11, expand=True, font_family=UI_FONT,
                        color=c(T.L_MUTED, T.D_MUTED)),
                ]),
            ]),
    )
    page.show_dialog(modern_dialog(
        page, c, "Fonctions vocales", content,
        subtitle="Lecture et dictée sur votre ordinateur",
        actions=[primary_button("Fermer", c, lambda e: page.pop_dialog())],
    ))
