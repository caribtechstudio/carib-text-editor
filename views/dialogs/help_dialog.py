"""
views/dialogs/help_dialog.py — Aide et raccourcis clavier.
"""

import flet as ft

from core.constants import UI_FONT_STRONG

from core.theme import T

#: (groupe, [(libellé, raccourci), …])
SHORTCUTS = (
    ("Essentiel", [
        ("Palette de commandes — toutes les actions", "Ctrl+Maj+P"),
        ("Demander à l'IA (prompt libre)", "Ctrl+K"),
        ("Rechercher", "Ctrl+F"),
        ("Rechercher et remplacer", "Ctrl+H"),
        ("Aller à la ligne", "Ctrl+G"),
    ]),
    ("Fichier", [
        ("Nouveau", "Ctrl+N"),
        ("Ouvrir", "Ctrl+O"),
        ("Enregistrer", "Ctrl+S"),
        ("Enregistrer sous", "Ctrl+Maj+S"),
        ("Imprimer", "Ctrl+P"),
        ("Quitter", "Alt+F4"),
    ]),
    ("Onglets", [
        ("Fermer l'onglet", "Ctrl+W"),
        ("Onglet suivant", "Ctrl+Tab"),
        ("Onglet précédent", "Ctrl+Maj+Tab"),
    ]),
    ("Édition", [
        ("Annuler", "Ctrl+Z"),
        ("Rétablir", "Ctrl+Y"),
        ("Insérer un emoji", "Ctrl+E"),
        ("Accepter la suggestion", "Tab"),
        ("Fermer la surcouche courante", "Échap"),
    ]),
    ("Intelligence artificielle", [
        ("Correction", "F7"),
        ("Traduction FR → EN", "F8"),
        ("Reformulation", "F9"),
        ("Accepter la modification proposée", "Tab"),
        ("Refuser la modification proposée", "Échap"),
    ]),
    ("Affichage", [
        ("Barre d'outils", "Ctrl+T"),
        ("Zoom avant / arrière", "Ctrl + molette"),
        ("Zoom 100 %", "Ctrl+0"),
        ("Mode Texte / Calcul / Lecture", "Ctrl+1 / 2 / 3"),
    ]),
    ("Outils", [
        ("Aide", "F1"),
        ("Lire le texte à voix haute", "F3"),
        ("Dictée vocale (Windows)", "F4"),
        ("Orthographe (local)", "F6"),
    ]),
)


def show_help(page, c):
    """Affiche la boîte d'aide avec les raccourcis clavier."""

    def row(label, key):
        return ft.Container(
            padding=ft.Padding(8, 5, 8, 5),
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Text(label, size=13, expand=True,
                            color=c(T.L_SECONDARY, T.D_SECONDARY)),
                    ft.Container(
                        padding=ft.Padding(10, 4, 10, 4), border_radius=6,
                        bgcolor=c(T.L_HOVER, T.D_HOVER),
                        content=ft.Text(key, size=12, weight=ft.FontWeight.W_500,
                                        font_family=UI_FONT_STRONG,
                                        color=c(T.L_TERTIARY, T.D_TERTIARY)),
                    ),
                ],
            ),
        )

    def group(title):
        return ft.Container(
            padding=ft.Padding(8, 12, 8, 4),
            content=ft.Text(title, size=11, font_family=UI_FONT_STRONG,
                            weight=ft.FontWeight.W_700,
                            color=c(T.L_MUTED, T.D_MUTED)),
        )

    controls = []
    for title, entries in SHORTCUTS:
        controls.append(group(title.upper()))
        controls.extend(row(label, key) for label, key in entries)

    controls.append(ft.Divider(color=c(T.L_BORDER, T.D_BORDER)))
    controls.append(ft.Container(
        padding=ft.Padding(8, 8, 8, 0),
        content=ft.Text(
            "Astuce : tapez :code puis une espace pour insérer un emoji.\n"
            "Exemples : :coeur  :feu  :ok  :sourire  :drapeau_fr\n\n"
            "Tout ce que fait Carib est accessible depuis Ctrl+Maj+P.",
            size=13, color=c(T.L_TERTIARY, T.D_TERTIARY)),
    ))

    page.show_dialog(ft.AlertDialog(
        title=ft.Text("Raccourcis clavier", size=16,
                      font_family=UI_FONT_STRONG, weight=ft.FontWeight.W_700),
        content=ft.Container(
            width=460, height=420,
            content=ft.Column(scroll=ft.ScrollMode.AUTO, spacing=1,
                              controls=controls)),
        actions=[ft.TextButton("Fermer", on_click=lambda e: page.pop_dialog())],
    ))
