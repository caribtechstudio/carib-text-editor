"""
views/dialogs/voice_dialog.py — Menu des fonctions vocales.
"""

import flet as ft

from theme import T
from views.dialogs._common import dlg_btn


def show_voice_menu(page, c, callbacks):
    """
    Affiche le menu vocal.

    callbacks attendus : read_text(), voice_typing(), voice_ms()
    """
    dlg = ft.AlertDialog(
        title=ft.Text("Fonctions vocales", size=16, font_family="Nunito SemiBold", weight=ft.FontWeight.W_600),
        content=ft.Container(
            width=360,
            content=ft.Column(spacing=8, controls=[
                dlg_btn("Lire le texte (F3)", ft.Icons.VOLUME_UP, c,
                        lambda e: (page.pop_dialog(), callbacks["read_text"]())),
                dlg_btn("Dictée Google (F4)", ft.Icons.MIC, c,
                        lambda e: (page.pop_dialog(), callbacks["voice_typing"]())),
                dlg_btn("Dictée Microsoft (F5)", ft.Icons.KEYBOARD_VOICE, c,
                        lambda e: (page.pop_dialog(), callbacks["voice_ms"]())),
            ]),
        ),
        actions=[ft.TextButton("Fermer", on_click=lambda e: page.pop_dialog())],
    )
    page.show_dialog(dlg)
