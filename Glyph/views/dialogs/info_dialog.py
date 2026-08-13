"""
views/dialogs/info_dialog.py — Informations et crédits.
"""

import flet as ft

from constants import APP_NAME, APP_VERSION, UI_FONT_STRONG
from theme import T


def show_info(page, c):
    """Affiche la boîte d'informations."""
    dlg = ft.AlertDialog(
        title=ft.Text("Informations", size=16, font_family=UI_FONT_STRONG, weight=ft.FontWeight.W_700),
        content=ft.Column(spacing=8, controls=[
            ft.Text(f"{APP_NAME} — v{APP_VERSION}", size=14, weight=ft.FontWeight.W_500),
            ft.Text("Éditeur de texte moderne avec IA locale.", size=13,
                    color=c(T.L_TERTIARY, T.D_TERTIARY)),
            ft.Text("Licence : CC BY-NC-ND 4.0", size=12,
                    color=c(T.L_MUTED, T.D_MUTED)),
        ]),
        actions=[ft.TextButton("Fermer", on_click=lambda e: page.pop_dialog())],
    )
    page.show_dialog(dlg)


def show_credits(page, c):
    """Affiche la boîte de crédits."""
    dlg = ft.AlertDialog(
        title=ft.Text("Crédits", size=16, font_family=UI_FONT_STRONG, weight=ft.FontWeight.W_700),
        content=ft.Container(
            width=420,
            content=ft.Column(spacing=10, controls=[
                ft.Text("Développé par Arnaud", size=14, weight=ft.FontWeight.W_500,
                        color=c(T.L_PRIMARY, T.D_PRIMARY)),
                ft.Text("• Python + Flet\n• pyspellchecker\n• pyttsx3\n"
                        "• SpeechRecognition\n• Ollama + ministral-3:3b",
                        size=13, color=c(T.L_SECONDARY, T.D_SECONDARY)),
                ft.Text("CC BY-NC-ND 4.0", size=12, color=c(T.L_MUTED, T.D_MUTED)),
            ]),
        ),
        actions=[ft.TextButton("Fermer", on_click=lambda e: page.pop_dialog())],
    )
    page.show_dialog(dlg)
