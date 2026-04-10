"""
views/dialogs/options_dialog.py — Boîte d'options / préférences.
"""

import flet as ft

from constants import MODE_TEXT, MODE_CALC, MODE_READ
from theme import T
from views.dialogs._common import dlg_btn


def show_options(page, c, dark, callbacks):
    """
    Affiche la boîte d'options.

    callbacks attendus :
        set_mode(mode), toggle_theme(), toggle_auto_save(),
        is_auto_save(), show_help(), show_info(), show_credits()
    """
    dlg = ft.AlertDialog(
        title=ft.Text("Options", size=16, font_family="Nunito SemiBold", weight=ft.FontWeight.W_600),
        content=ft.Container(
            width=380,
            content=ft.Column(spacing=8, controls=[
                dlg_btn("Mode Texte", ft.Icons.EDIT_NOTE, c,
                        lambda e: (page.pop_dialog(), callbacks["set_mode"](MODE_TEXT))),
                dlg_btn("Mode Calcul", ft.Icons.CALCULATE_OUTLINED, c,
                        lambda e: (page.pop_dialog(), callbacks["set_mode"](MODE_CALC))),
                dlg_btn("Mode Lecture", ft.Icons.MENU_BOOK, c,
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
                                ft.Icon(ft.Icons.DARK_MODE if dark() else ft.Icons.LIGHT_MODE,
                                        size=20, color=c(T.L_ACCENT, T.D_ACCENT)),
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
                                ft.Icon(ft.Icons.SAVE_OUTLINED,
                                        size=20, color=c(T.L_ACCENT, T.D_ACCENT)),
                                ft.Text("Sauvegarde auto",
                                        size=14, color=c(T.L_PRIMARY, T.D_PRIMARY)),
                            ]),
                            ft.Switch(value=callbacks["is_auto_save"](),
                                      active_color=c(T.L_ACCENT, T.D_ACCENT),
                                      on_change=lambda e: (page.pop_dialog(), callbacks["toggle_auto_save"]())),
                        ],
                    ),
                ),
                ft.Divider(color=c(T.L_BORDER, T.D_BORDER)),
                # Gestion des modeles IA
                dlg_btn("Modeles IA", ft.Icons.SMART_TOY_OUTLINED, c,
                        lambda e: (page.pop_dialog(), callbacks["show_model_manager"]())),
                ft.Divider(color=c(T.L_BORDER, T.D_BORDER)),
                dlg_btn("Aide", ft.Icons.HELP_OUTLINE, c,
                        lambda e: (page.pop_dialog(), callbacks["show_help"]())),
                dlg_btn("Informations", ft.Icons.INFO_OUTLINE, c,
                        lambda e: (page.pop_dialog(), callbacks["show_info"]())),
                dlg_btn("Crédits", ft.Icons.FAVORITE_BORDER, c,
                        lambda e: (page.pop_dialog(), callbacks["show_credits"]())),
            ]),
        ),
        actions=[ft.TextButton("Fermer", on_click=lambda e: page.pop_dialog())],
    )
    page.show_dialog(dlg)
