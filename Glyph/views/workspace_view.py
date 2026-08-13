"""
views/workspace_view.py — Arborescence du dossier ouvert, dans la barre latérale.
"""

import os

import flet as ft

from constants import ICON_SM, ICON_XS, svg_icon, UI_FONT, UI_FONT, UI_FONT_STRONG
from models.workspace import build_tree, display_name
from theme import T

#: Icône choisie d'après l'extension — un repère visuel vaut mieux qu'un
#: alignement de documents identiques.
_ICON_BY_EXT = {
    ".md": "book", ".markdown": "book", ".rst": "book",
    ".json": "json-file", ".yaml": "settings-sliders", ".yml": "settings-sliders",
    ".toml": "settings-sliders", ".ini": "settings-sliders",
    ".cfg": "settings-sliders", ".conf": "settings-sliders", ".env": "settings-sliders",
    ".py": "it", ".js": "it", ".ts": "it", ".sql": "it", ".sh": "it", ".bat": "it",
    ".csv": "rectangle-list", ".tsv": "rectangle-list",
    ".log": "list",
}


def _file_icon(name: str) -> str:
    return _ICON_BY_EXT.get(os.path.splitext(name)[1].lower(), "document")


def build_workspace_panel(state, c, callbacks):
    """Construit le panneau d'arborescence.

    callbacks attendus :
        open_path(path), toggle_dir(path), close_workspace()
    """
    root = state.workspace_path
    if not root:
        return None

    expanded = getattr(state, "workspace_expanded_dirs", set())
    active_path = callbacks.get("active_path")

    header = ft.Container(
        padding=ft.Padding(12, 8, 6, 8),
        content=ft.Row(spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER,
                       controls=[
            svg_icon("folder-open", size=ICON_SM, color=c(T.L_ACCENT, T.D_ACCENT)),
            ft.Text(display_name(root).upper(), size=11, expand=True,
                    font_family=UI_FONT_STRONG, weight=ft.FontWeight.W_700,
                    color=c(T.L_SECONDARY, T.D_SECONDARY),
                    overflow=ft.TextOverflow.ELLIPSIS, tooltip=root),
            ft.Container(
                width=22, height=22, border_radius=4, ink=True,
                alignment=ft.Alignment(0, 0),
                tooltip="Fermer le dossier",
                on_click=lambda e: callbacks["close_workspace"](),
                content=svg_icon("clear-alt", size=ICON_XS,
                                 color=c(T.L_MUTED, T.D_MUTED))),
        ]),
    )

    rows: list[ft.Control] = []
    for entry in build_tree(root, expanded):
        indent = 10 + entry.depth * 12

        if entry.is_dir:
            is_open = os.path.normcase(entry.path) in expanded
            rows.append(ft.Container(
                padding=ft.Padding(indent, 4, 8, 4), border_radius=5, ink=True,
                on_click=lambda e, p=entry.path: callbacks["toggle_dir"](p),
                content=ft.Row(spacing=6, controls=[
                    svg_icon("angle-circle-down" if is_open else "angle-circle-right",
                             size=ICON_XS, color=c(T.L_MUTED, T.D_MUTED)),
                    svg_icon("folder-open" if is_open else "folder",
                             size=ICON_XS, color=c(T.L_TERTIARY, T.D_TERTIARY)),
                    ft.Text(entry.name, size=12, expand=True, font_family=UI_FONT,
                            color=c(T.L_SECONDARY, T.D_SECONDARY),
                            overflow=ft.TextOverflow.ELLIPSIS),
                ]),
            ))
        else:
            is_active = (active_path
                         and os.path.normcase(active_path) == os.path.normcase(entry.path))
            rows.append(ft.Container(
                padding=ft.Padding(indent + 18, 4, 8, 4), border_radius=5, ink=True,
                bgcolor=(c(T.L_SELECTED, T.D_SELECTED) if is_active
                         else ft.Colors.TRANSPARENT),
                tooltip=entry.path,
                on_click=lambda e, p=entry.path: callbacks["open_path"](p),
                content=ft.Row(spacing=6, controls=[
                    svg_icon(_file_icon(entry.name), size=ICON_XS,
                             color=c(T.L_ACCENT, T.D_ACCENT) if is_active
                             else c(T.L_MUTED, T.D_MUTED)),
                    ft.Text(entry.name, size=12, expand=True,
                            font_family=UI_FONT_STRONG if is_active else UI_FONT,
                            color=c(T.L_PRIMARY, T.D_PRIMARY) if is_active
                            else c(T.L_SECONDARY, T.D_SECONDARY),
                            overflow=ft.TextOverflow.ELLIPSIS),
                ]),
            ))

    if not rows:
        rows = [ft.Container(
            padding=ft.Padding(22, 6, 12, 6),
            content=ft.Text("Aucun fichier texte ici", size=11, italic=True,
                            font_family=UI_FONT, color=c(T.L_MUTED, T.D_MUTED)))]

    return ft.Container(
        expand=True,
        content=ft.Column(spacing=0, expand=True, controls=[
            header,
            ft.Container(
                expand=True,
                content=ft.Column(spacing=1, scroll=ft.ScrollMode.AUTO,
                                  controls=rows)),
        ]),
    )
