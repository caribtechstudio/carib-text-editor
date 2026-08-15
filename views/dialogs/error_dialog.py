"""
views/dialogs/error_dialog.py — Rapport d'erreur inattendue.

Ce dialogue n'existe pas pour s'excuser : il existe pour qu'un utilisateur
qui rencontre un défaut puisse le signaler utilement. Il donne donc trois
choses — ce qui s'est passé, où se trouve le journal, et de quoi le copier
en un clic.

Le journal ne contient jamais le texte des documents, et les clés API y sont
masquées à l'écriture (voir `core/logging_setup`) : on peut donc inviter
l'utilisateur à le joindre à un rapport de bogue sans réserve.
"""

import os
import sys

import flet as ft

from core.constants import (
    APP_VERSION, ICON_SM, ISSUES_URL, UI_FONT, UI_FONT_STRONG, svg_icon,
)
from core.theme import T


def show_crash_report(page, c, title: str, message: str, log_file: str,
                      clipboard=None):
    """Affiche le rapport. `clipboard` est le service `ft.Clipboard` de la
    page ; sans lui, le bouton « Copier » est simplement masqué."""
    from core import logging_setup

    def open_log_folder(e=None):
        folder = os.path.dirname(log_file)
        if sys.platform == "win32" and os.path.isdir(folder):
            try:
                os.startfile(folder)
            except OSError:
                pass

    async def copy_details(e=None):
        # Le presse-papier de Flet est un service asynchrone : il ne peut pas
        # être appelé directement depuis un gestionnaire synchrone.
        payload = (
            f"Carib {APP_VERSION} — {title}\n"
            f"{message}\n\n"
            f"--- Fin du journal ---\n{logging_setup.read_tail(4000)}"
        )
        try:
            await clipboard.set(payload)
            snack.value = "Détails copiés dans le presse-papier."
        except Exception:
            snack.value = "Copie impossible — ouvrez le journal à la main."
        snack.visible = True
        try:
            dlg.update()
        except Exception:
            pass

    snack = ft.Text("", size=11, visible=False, font_family=UI_FONT,
                    color=c(T.L_ACCENT, T.D_ACCENT))

    dlg = ft.AlertDialog(
        modal=True,
        title=ft.Text("Une erreur inattendue s'est produite", size=16,
                      font_family=UI_FONT_STRONG, weight=ft.FontWeight.W_700),
        content=ft.Container(width=520, content=ft.Column(
            spacing=12, tight=True, controls=[
                ft.Text(
                    "Carib continue de fonctionner, mais quelque chose a mal "
                    "tourné. Vos documents ouverts ne sont pas perdus : ils "
                    "sont enregistrés automatiquement toutes les 15 secondes.",
                    size=13, color=c(T.L_SECONDARY, T.D_SECONDARY)),

                ft.Container(
                    padding=ft.Padding(12, 10, 12, 10), border_radius=8,
                    bgcolor=c(T.L_HOVER, T.D_HOVER),
                    content=ft.Column(spacing=4, tight=True, controls=[
                        ft.Text(title, size=12, font_family=UI_FONT_STRONG,
                                color=c(T.L_PRIMARY, T.D_PRIMARY)),
                        ft.Text(message, size=11, selectable=True,
                                color=c(T.L_TERTIARY, T.D_TERTIARY)),
                    ])),

                ft.Row(spacing=8, controls=[
                    svg_icon("info", size=ICON_SM,
                             color=c(T.L_MUTED, T.D_MUTED)),
                    ft.Text(
                        "Le journal technique se trouve dans "
                        f"{log_file}. Il ne contient pas le texte de vos "
                        "documents.",
                        size=10, expand=True, font_family=UI_FONT,
                        color=c(T.L_MUTED, T.D_MUTED)),
                ]),
                snack,
            ])),
        actions=[
            ft.TextButton("Ouvrir le dossier du journal", on_click=open_log_folder),
            *([ft.TextButton("Copier les détails", on_click=copy_details)]
              if clipboard is not None else []),
            ft.TextButton("Signaler", url=ISSUES_URL),
            ft.Button("Fermer", bgcolor=c(T.L_ACCENT, T.D_ACCENT),
                      color="#FFFFFF",
                      on_click=lambda e: page.pop_dialog()),
        ],
        actions_alignment=ft.MainAxisAlignment.END)

    page.show_dialog(dlg)
