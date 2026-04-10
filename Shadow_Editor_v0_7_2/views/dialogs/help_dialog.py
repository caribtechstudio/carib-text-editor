"""
views/dialogs/help_dialog.py — Aide et raccourcis clavier.
"""

import flet as ft

from theme import T


def show_help(page, c):
    """Affiche la boîte d'aide avec les raccourcis clavier."""

    def row(label, key):
        return ft.Container(
            padding=ft.Padding(8, 6, 8, 6),
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Text(label, size=13, color=c(T.L_SECONDARY, T.D_SECONDARY)),
                    ft.Container(
                        padding=ft.Padding(10, 4, 10, 4), border_radius=6,
                        bgcolor=c(T.L_HOVER, T.D_HOVER),
                        content=ft.Text(key, size=12, weight=ft.FontWeight.W_500,
                                        color=c(T.L_TERTIARY, T.D_TERTIARY)),
                    ),
                ],
            ),
        )

    dlg = ft.AlertDialog(
        title=ft.Text("Raccourcis clavier", size=16, font_family="Nunito SemiBold", weight=ft.FontWeight.W_600),
        content=ft.Container(
            width=440, height=380,
            content=ft.Column(scroll=ft.ScrollMode.AUTO, spacing=2, controls=[
                row("Nouveau", "Ctrl+N"), row("Ouvrir", "Ctrl+O"),
                row("Enregistrer", "Ctrl+S"), row("Enregistrer sous", "Ctrl+Shift+S"),
                row("Imprimer", "Ctrl+P"),
                row("Annuler", "Ctrl+Z"), row("Rétablir", "Ctrl+Y"),
                row("Glyph Assistant", "F2"), row("Lire le texte", "F3"),
                row("Dictée Google", "F4"), row("Dictée Microsoft", "F5"),
                row("Orthographe", "F6"), row("Correcteur IA", "F7"),
                row("Émojis", "Ctrl+E"),
                row("Barre d'outils", "Ctrl+T"),
                row("Quitter", "Alt+F4"),
                ft.Divider(color=c(T.L_BORDER, T.D_BORDER)),
                ft.Container(
                    padding=ft.Padding(8, 8, 8, 0),
                    content=ft.Text(
                        "Tapez :code + espace pour insérer un emoji.\n"
                        "Ex: :coeur :feu :ok :sourire :drapeau_fr",
                        size=13, color=c(T.L_TERTIARY, T.D_TERTIARY),
                    ),
                ),
            ]),
        ),
        actions=[ft.TextButton("Fermer", on_click=lambda e: page.pop_dialog())],
    )
    page.show_dialog(dlg)
