"""
views/dialogs/options_dialog.py — Boîte d'options / préférences.
"""

import flet as ft

from core.constants import (ICON_XS, ICON_SM, ICON_MD, MODE_TEXT, MODE_CALC, MODE_READ, svg_icon, UI_FONT_STRONG)
from core.theme import T
from views.dialogs._common import dlg_btn


def show_options(page, c, dark, callbacks):
    """
    Affiche la boîte d'options.

    callbacks attendus :
        set_mode(mode), toggle_theme(), toggle_auto_save(), is_auto_save(),
        toggle_autocomplete(), is_autocomplete(), show_model_manager(),
        show_privacy(), check_updates(),
        show_help(), show_info(), show_credits()
    """
    dlg = ft.AlertDialog(
        title=ft.Text("Options", size=16, font_family=UI_FONT_STRONG, weight=ft.FontWeight.W_700),
        content=ft.Container(
            width=380,
            content=ft.Column(spacing=8, controls=[
                dlg_btn("Mode Texte", "pen-field", c,
                        lambda e: (page.pop_dialog(), callbacks["set_mode"](MODE_TEXT))),
                dlg_btn("Mode Calcul", "calculator-simple", c,
                        lambda e: (page.pop_dialog(), callbacks["set_mode"](MODE_CALC))),
                dlg_btn("Mode Lecture", "book-open-cover", c,
                        lambda e: (page.pop_dialog(), callbacks["set_mode"](MODE_READ))),
                ft.Divider(color=c(T.L_BORDER, T.D_BORDER)),
                # Toggle thème
                ft.Container(
                    padding=ft.Padding(16, 12, 16, 12), border_radius=8,
                    border=ft.Border.all(1, c(T.L_BORDER, T.D_BORDER)),
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Row(spacing=12, controls=[
                                svg_icon("moon-stars" if dark() else "brightness",
                                         size=ICON_MD, color=c(T.L_ACCENT, T.D_ACCENT)),
                                ft.Text("Thème sombre" if dark() else "Thème clair",
                                        size=14, color=c(T.L_PRIMARY, T.D_PRIMARY)),
                            ]),
                            ft.Switch(value=dark(), active_color=c(T.L_ACCENT, T.D_ACCENT),
                                      on_change=lambda e: (page.pop_dialog(), callbacks["toggle_theme"]())),
                        ],
                    ),
                ),
                # Toggle sauvegarde automatique
                ft.Container(
                    padding=ft.Padding(16, 12, 16, 12), border_radius=8,
                    border=ft.Border.all(1, c(T.L_BORDER, T.D_BORDER)),
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Row(spacing=12, controls=[
                                svg_icon("disk",
                                         size=ICON_MD, color=c(T.L_ACCENT, T.D_ACCENT)),
                                ft.Text("Sauvegarde auto",
                                        size=14, color=c(T.L_PRIMARY, T.D_PRIMARY)),
                            ]),
                            ft.Switch(value=callbacks["is_auto_save"](),
                                      active_color=c(T.L_ACCENT, T.D_ACCENT),
                                      on_change=lambda e: (page.pop_dialog(), callbacks["toggle_auto_save"]())),
                        ],
                    ),
                ),
                # Toggle autocompletion
                ft.Container(
                    padding=ft.Padding(16, 12, 16, 12), border_radius=8,
                    border=ft.Border.all(1, c(T.L_BORDER, T.D_BORDER)),
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Row(spacing=12, controls=[
                                svg_icon("text",
                                         size=ICON_MD, color=c(T.L_ACCENT, T.D_ACCENT)),
                                ft.Column(spacing=1, tight=True, controls=[
                                    ft.Text("Autocomplétion",
                                            size=14, color=c(T.L_PRIMARY, T.D_PRIMARY)),
                                    ft.Text("Suggestions de mots + prédiction IA",
                                            size=11, color=c(T.L_MUTED, T.D_MUTED),
                                            italic=True),
                                ]),
                            ]),
                            ft.Switch(value=callbacks["is_autocomplete"](),
                                      active_color=c(T.L_ACCENT, T.D_ACCENT),
                                      on_change=lambda e: (page.pop_dialog(), callbacks["toggle_autocomplete"]())),
                        ],
                    ),
                ),
                ft.Divider(color=c(T.L_BORDER, T.D_BORDER)),
                # Gestion des modeles IA
                dlg_btn("Modeles IA", "user-robot", c,
                        lambda e: (page.pop_dialog(), callbacks["show_model_manager"]())),
                ft.Divider(color=c(T.L_BORDER, T.D_BORDER)),
                dlg_btn("Confidentialité et données", "shield-trust", c,
                        lambda e: (page.pop_dialog(), callbacks["show_privacy"]())),
                dlg_btn("Rechercher une mise à jour", "cloud-download-alt", c,
                        lambda e: (page.pop_dialog(), callbacks["check_updates"]())),
                ft.Divider(color=c(T.L_BORDER, T.D_BORDER)),
                dlg_btn("Aide", "interrogation", c,
                        lambda e: (page.pop_dialog(), callbacks["show_help"]())),
                dlg_btn("Informations", "info", c,
                        lambda e: (page.pop_dialog(), callbacks["show_info"]())),
                dlg_btn("Crédits", "heart", c,
                        lambda e: (page.pop_dialog(), callbacks["show_credits"]())),
            ]),
        ),
        actions=[ft.TextButton("Fermer", on_click=lambda e: page.pop_dialog())],
    )
    page.show_dialog(dlg)
