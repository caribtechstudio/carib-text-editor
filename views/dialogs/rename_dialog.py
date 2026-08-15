"""
views/dialogs/rename_dialog.py — Dialogue de renommage de fichier.
"""

import flet as ft

from core.constants import UI_FONT

from core.theme import T
from views.dialogs._common import modern_dialog, primary_button, secondary_button


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

    page.show_dialog(modern_dialog(
        page, c, "Renommer le fichier", ft.Container(width=360, content=name_field),
        subtitle="Le contenu du document reste inchangé", modal=True,
        actions=[
            secondary_button("Annuler", c, lambda e: page.pop_dialog()),
            primary_button("Renommer", c, _on_rename, icon="edit"),
        ],
    ))
