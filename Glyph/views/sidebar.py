"""
views/sidebar.py — Barre latérale pliable (fichier + navigation).
"""

import flet as ft

from constants import APP_NAME, APP_VERSION, resource_path, svg_icon
from theme import T


def build_sidebar(state, c, callbacks):
    """
    Construit la barre latérale pliable.

    callbacks attendus :
        toggle_sidebar,
        open_file, save_file, save_file_as, add_tab, rename_file, print_file,
        show_help, show_options
    """
    collapsed = state.sidebar_collapsed

    def item(label, icon_name, key, on_click=None, tooltip_text=None):
        active = (state.sidebar_key == key)
        tip = tooltip_text or label
        ico_color = c(T.L_ACCENT, T.D_ACCENT) if active else c(T.L_TERTIARY, T.D_TERTIARY)

        if collapsed:
            return ft.Container(
                width=40, height=40, border_radius=8,
                bgcolor=c(T.L_SELECTED, T.D_SELECTED) if active else ft.Colors.TRANSPARENT,
                alignment=ft.Alignment(0, 0),
                ink=True, on_click=on_click,
                tooltip=tip,
                content=svg_icon(icon_name, size=22, color=ico_color),
            )

        ctrls = [
            svg_icon(icon_name, size=22, color=ico_color),
            ft.Text(label, size=13, expand=True,
                    font_family="Nunito SemiBold" if active else "Nunito",
                    weight=ft.FontWeight.W_600 if active else ft.FontWeight.W_400,
                    color=c(T.L_PRIMARY, T.D_PRIMARY) if active else c(T.L_SECONDARY, T.D_SECONDARY)),
        ]
        return ft.Container(
            padding=ft.Padding(12, 10, 12, 10), border_radius=8,
            bgcolor=c(T.L_SELECTED, T.D_SELECTED) if active else ft.Colors.TRANSPARENT,
            ink=True, on_click=on_click,
            tooltip=tip,
            content=ft.Row(controls=ctrls, spacing=12),
        )

    def separator():
        if collapsed:
            return ft.Container(
                width=32, height=1, bgcolor=c(T.L_BORDER, T.D_BORDER),
                margin=ft.Margin(0, 4, 0, 4),
            )
        return ft.Container(
            height=1, bgcolor=c(T.L_BORDER, T.D_BORDER),
            margin=ft.Margin(12, 4, 12, 4),
        )

    # Bouton menu toggle
    menu_icon = "angle-double-small-left" if not collapsed else "menu-burger"
    menu_btn = ft.Container(
        width=40, height=40, border_radius=8,
        alignment=ft.Alignment(0, 0),
        ink=True,
        on_click=lambda e: callbacks["toggle_sidebar"](),
        tooltip="Réduire le menu" if not collapsed else "Ouvrir le menu",
        content=svg_icon(menu_icon, size=22, color=c(T.L_SECONDARY, T.D_SECONDARY)),
    )

    # Header : logo + nom + version + toggle (même ligne, visible déplié uniquement)
    logo_img = ft.Image(
        src=resource_path("ressource/icon/icon.ico"),
        width=28, height=28,
    )
    if collapsed:
        header = ft.Row(
            controls=[menu_btn],
            alignment=ft.MainAxisAlignment.CENTER,
        )
    else:
        header = ft.Container(
            padding=ft.Padding(0, 0, 0, 8),
            content=ft.Row(
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    logo_img,
                    ft.Column(spacing=0, expand=True, controls=[
                        ft.Text(APP_NAME, size=14, weight=ft.FontWeight.W_600,
                                font_family="Nunito SemiBold",
                                color=c(T.L_PRIMARY, T.D_PRIMARY)),
                        ft.Text(f"v{APP_VERSION}", size=10, color=c(T.L_MUTED, T.D_MUTED)),
                    ]),
                    menu_btn,
                ],
            ),
        )

    # Items principaux
    nav_items = ft.Column(
        spacing=2,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER if collapsed else ft.CrossAxisAlignment.START,
        controls=[
            item("Ouvrir", "folder-open", "open",
                 on_click=callbacks["open_file"], tooltip_text="Ouvrir  Ctrl+O"),
            item("Nouveau", "add-document", "new",
                 on_click=lambda e: callbacks["add_tab"](), tooltip_text="Nouveau  Ctrl+N"),
            item("Enregistrer", "disk", "save",
                 on_click=callbacks["save_file"], tooltip_text="Enregistrer  Ctrl+S"),
            item("Enregistrer sous", "floppy-disk-pen", "saveas",
                 on_click=callbacks["save_file_as"], tooltip_text="Enregistrer sous  Ctrl+Shift+S"),
            item("Renommer", "edit", "rename",
                 on_click=lambda e: callbacks["rename_file"]()),
            item("Imprimer", "print", "print",
                 on_click=lambda e: callbacks["print_file"](), tooltip_text="Imprimer  Ctrl+P"),
        ],
    )

    # Items du bas
    bottom_items = ft.Column(
        spacing=2,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER if collapsed else ft.CrossAxisAlignment.START,
        controls=[
            item("Aide", "interrogation", "help",
                 on_click=lambda e: callbacks["show_help"]()),
            item("Options", "settings", "opts",
                 on_click=lambda e: callbacks["show_options"]()),
        ],
    )

    return ft.Container(
        expand=True,
        bgcolor=c(T.L_SIDEBAR, T.D_SIDEBAR),
        border=ft.Border.only(right=ft.BorderSide(1, c(T.L_BORDER, T.D_BORDER))),
        shadow=ft.BoxShadow(spread_radius=0, blur_radius=12,
                            color=ft.Colors.with_opacity(0.04, ft.Colors.BLACK),
                            offset=ft.Offset(2, 0)),
        padding=ft.Padding(8, 16, 8, 12) if collapsed else ft.Padding(12, 16, 12, 12),
        content=ft.Column(
            expand=True, spacing=0,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER if collapsed else ft.CrossAxisAlignment.START,
            controls=[
                header,
                nav_items,
                ft.Container(expand=True),
                separator(),
                bottom_items,
            ],
        ),
    )
