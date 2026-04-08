"""
views/dialogs/rename_dialog.py — Dialogue de renommage de fichier.
"""

import flet as ft

from theme import T


def show_rename_dialog(page, c, document, callbacks):
    """
    Affiche le dialogue de renommage.

    callbacks attendus : do_rename(new_name)
    """
    base = document.title
    if base.lower().endswith(".txt"):
        base = base[:-4]

    name_field = ft.TextField(
        value=base, label="Nouveau nom", autofocus=True,
        border_radius=8, text_size=14,
        border_color=c(T.L_BORDER, T.D_BORDER),
        focused_border_color=c(T.L_ACCENT, T.D_ACCENT),
    )

    def _on_rename(ev):
        new_name = (name_field.value or "").strip()
        if not new_name:
            return
        if not new_name.endswith(".txt"):
            new_name += ".txt"
        page.pop_dialog()
        callbacks["do_rename"](new_name)

    dlg = ft.AlertDialog(
        modal=True,
        title=ft.Text("Renommer le fichier", size=16, font_family="Nunito SemiBold", weight=ft.FontWeight.W_600),
        content=ft.Container(width=360, content=name_field),
        actions=[
            ft.TextButton("Annuler", on_click=lambda ev: page.pop_dialog()),
            ft.FilledButton("Renommer", on_click=_on_rename),
        ],
    )
    page.show_dialog(dlg)
