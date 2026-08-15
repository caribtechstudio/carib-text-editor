"""Aide filtrable et raccourcis clavier en deux colonnes."""

import flet as ft

from core.constants import (APP_VERSION, TEXT_CAPTION, TEXT_META, TEXT_UI,
                            UI_FONT, UI_FONT_STRONG)
from core.theme import T
from views.dialogs._common import modern_dialog, primary_button


SHORTCUTS = (
    ("Essentiel", [
        ("Palette de commandes", "Ctrl+Maj+P"),
        ("Demander à l'IA", "Ctrl+K"),
        ("Rechercher", "Ctrl+F"),
        ("Rechercher et remplacer", "Ctrl+H"),
        ("Aller à la ligne", "Ctrl+G"),
    ]),
    ("Fichier", [
        ("Nouveau", "Ctrl+N"), ("Ouvrir", "Ctrl+O"),
        ("Enregistrer", "Ctrl+S"), ("Enregistrer sous", "Ctrl+Maj+S"),
        ("Imprimer", "Ctrl+P"), ("Quitter", "Alt+F4"),
    ]),
    ("Onglets", [
        ("Fermer l'onglet", "Ctrl+W"), ("Onglet suivant", "Ctrl+Tab"),
        ("Onglet précédent", "Ctrl+Maj+Tab"),
    ]),
    ("Édition", [
        ("Annuler", "Ctrl+Z"), ("Rétablir", "Ctrl+Y"),
        ("Insérer un emoji", "Ctrl+E"), ("Accepter la suggestion", "Tab"),
        ("Fermer la surcouche", "Échap"),
    ]),
    ("Intelligence artificielle", [
        ("Correction", "F7"), ("Traduction FR → EN", "F8"),
        ("Reformulation", "F9"), ("Accepter la modification", "Tab"),
        ("Refuser la modification", "Échap"),
    ]),
    ("Affichage", [
        ("Barre d'outils", "Ctrl+T"), ("Zoom avant / arrière", "Ctrl+molette"),
        ("Zoom 100 %", "Ctrl+0"), ("Modes Texte / Calcul / Lecture", "Ctrl+1/2/3"),
    ]),
    ("Outils", [
        ("Aide", "F1"), ("Lire le texte", "F3"),
        ("Dictée vocale", "F4"), ("Orthographe locale", "F6"),
    ]),
)


def show_help(page, c):
    left = ft.Column(spacing=10, expand=True, scroll=ft.ScrollMode.AUTO)
    right = ft.Column(spacing=10, expand=True, scroll=ft.ScrollMode.AUTO)

    def keycap(label):
        return ft.Container(
            height=22, padding=ft.Padding(6, 0, 6, 0), border_radius=6,
            alignment=ft.Alignment(0, 0), bgcolor=c(T.L_EDITOR, T.D_EDITOR),
            border=ft.Border.all(1, c(T.L_BORDER, T.D_BORDER)),
            content=ft.Text(label, size=10.5, font_family=UI_FONT_STRONG,
                            color=c(T.L_SECONDARY, T.D_SECONDARY)),
        )

    def shortcut_row(label, shortcut):
        keys = shortcut.replace("+", " + ").split()
        return ft.Container(
            height=34, padding=ft.Padding(2, 4, 6, 4), border_radius=8,
            content=ft.Row(spacing=8, controls=[
                ft.Text(label, size=TEXT_UI, expand=True, font_family=UI_FONT,
                        color=c(T.L_PRIMARY, T.D_PRIMARY)),
                ft.Row(spacing=3, tight=True,
                       controls=[keycap(k) if k != "+" else ft.Text(
                           "+", size=10, color=c(T.L_MUTED, T.D_MUTED))
                           for k in keys]),
            ]),
        )

    def group_control(title, entries):
        return ft.Column(spacing=2, tight=True, controls=[
            ft.Row(spacing=8, controls=[
                ft.Text(title.upper(), style=ft.TextStyle(
                    size=TEXT_CAPTION, font_family=UI_FONT_STRONG,
                    weight=ft.FontWeight.W_700, letter_spacing=0.8,
                    color=c(T.L_ACCENT, T.D_ACCENT))),
                ft.Container(height=1, expand=True,
                             bgcolor=c(T.L_BORDER, T.D_BORDER)),
            ]),
            *[shortcut_row(label, key) for label, key in entries],
        ])

    def rebuild_groups(query=""):
        left.controls.clear()
        right.controls.clear()
        visible_groups = []
        needle = query.strip().lower()
        for title, entries in SHORTCUTS:
            filtered = [(label, key) for label, key in entries
                        if not needle or needle in label.lower()
                        or needle in key.lower() or needle in title.lower()]
            if filtered:
                visible_groups.append((title, filtered))
        midpoint = (len(visible_groups) + 1) // 2
        left.controls.extend(group_control(*group) for group in visible_groups[:midpoint])
        right.controls.extend(group_control(*group) for group in visible_groups[midpoint:])

    search = ft.TextField(
        hint_text="Filtrer les raccourcis…", prefix_icon=ft.Icons.SEARCH,
        height=38, text_size=13, dense=True, border_radius=11,
        bgcolor=c(T.L_EDITOR, T.D_EDITOR),
        border_color=c(T.L_BORDER, T.D_BORDER),
        focused_border_color=c(T.L_ACCENT, T.D_ACCENT),
        on_change=lambda e: (rebuild_groups(e.control.value or ""), page.update()),
    )
    rebuild_groups()

    content = ft.Container(
        width=690, height=450,
        content=ft.Column(spacing=14, controls=[
            search,
            ft.Row(spacing=28, expand=True,
                   vertical_alignment=ft.CrossAxisAlignment.START,
                   controls=[left, right]),
        ]),
    )
    footer = ft.Text(f"Carib v{APP_VERSION} · Tous les raccourcis sont locaux",
                     size=TEXT_META, font_family=UI_FONT,
                     color=c(T.L_MUTED, T.D_MUTED))
    dlg = modern_dialog(
        page, c, "Aide", content, subtitle="Raccourcis clavier",
        actions=[footer, primary_button("Fermer", c, lambda e: page.pop_dialog())],
    )
    dlg.actions_alignment = ft.MainAxisAlignment.SPACE_BETWEEN
    page.show_dialog(dlg)
