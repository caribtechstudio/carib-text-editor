"""
views/sidebar.py — Barre latérale pliable (fichier + navigation).
"""

import flet as ft

from constants import APP_NAME, APP_VERSION, resource_path
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

    def item(label, icon, key, on_click=None, tooltip_text=None):
        active = (state.sidebar_key == key)
        tip = tooltip_text or label

        if collapsed:
            return ft.Container(
                width=40, height=40, border_radius=8,
                bgcolor=c(T.L_SELECTED, T.D_SELECTED) if active else ft.Colors.TRANSPARENT,
                alignment=ft.Alignment(0, 0),
                ink=True, on_click=on_click,
                tooltip=tip,
                content=ft.Icon(icon, size=20,
                                color=c(T.L_ACCENT, T.D_ACCENT) if active else c(T.L_TERTIARY, T.D_TERTIARY)),
            )

        ctrls = [
            ft.Icon(icon, size=20,
                    color=c(T.L_ACCENT, T.D_ACCENT) if active else c(T.L_TERTIARY, T.D_TERTIARY)),
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
    menu_btn = ft.Container(
        width=40, height=40, border_radius=8,
        alignment=ft.Alignment(0, 0),
        ink=True,
        on_click=lambda e: callbacks["toggle_sidebar"](),
        tooltip="Réduire le menu" if not collapsed else "Ouvrir le menu",
        content=ft.Icon(
            ft.Icons.MENU_OPEN if not collapsed else ft.Icons.MENU,
            size=22, color=c(T.L_SECONDARY, T.D_SECONDARY),
        ),
    )

    # Logo
    logo_img = ft.Image(
        src=resource_path("ressource/icon/logo.png"),
        width=32, height=32,
    )
    if collapsed:
        logo = ft.Container(
            padding=ft.Padding(0, 0, 0, 12),
            alignment=ft.Alignment(0, 0),
            content=logo_img,
        )
    else:
        logo = ft.Container(
            padding=ft.Padding(12, 0, 0, 12),
            content=ft.Row(spacing=10, controls=[
                logo_img,
                ft.Column(spacing=0, controls=[
                    ft.Text(APP_NAME, size=15, weight=ft.FontWeight.W_600,
                            font_family="Nunito SemiBold",
                            color=c(T.L_PRIMARY, T.D_PRIMARY)),
                    ft.Text(f"v{APP_VERSION}", size=11, color=c(T.L_MUTED, T.D_MUTED)),
                ]),
            ]),
        )

    # Items principaux
    nav_items = ft.Column(
        spacing=2,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER if collapsed else ft.CrossAxisAlignment.START,
        controls=[
            item("Documents", ft.Icons.DESCRIPTION_OUTLINED, "docs"),
            separator(),
            item("Ouvrir", ft.Icons.FOLDER_OPEN_OUTLINED, "open",
                 on_click=callbacks["open_file"], tooltip_text="Ouvrir  Ctrl+O"),
            item("Nouveau", ft.Icons.ADD_CIRCLE_OUTLINE, "new",
                 on_click=lambda e: callbacks["add_tab"](), tooltip_text="Nouveau  Ctrl+N"),
            item("Enregistrer", ft.Icons.SAVE_OUTLINED, "save",
                 on_click=callbacks["save_file"], tooltip_text="Enregistrer  Ctrl+S"),
            item("Enregistrer sous", ft.Icons.SAVE_AS_OUTLINED, "saveas",
                 on_click=callbacks["save_file_as"], tooltip_text="Enregistrer sous  Ctrl+Shift+S"),
            item("Renommer", ft.Icons.EDIT_OUTLINED, "rename",
                 on_click=lambda e: callbacks["rename_file"]()),
            item("Imprimer", ft.Icons.PRINT_OUTLINED, "print",
                 on_click=lambda e: callbacks["print_file"](), tooltip_text="Imprimer  Ctrl+P"),
        ],
    )

    # Items du bas
    bottom_items = ft.Column(
        spacing=2,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER if collapsed else ft.CrossAxisAlignment.START,
        controls=[
            item("Aide", ft.Icons.HELP_OUTLINE, "help",
                 on_click=lambda e: callbacks["show_help"]()),
            item("Options", ft.Icons.SETTINGS_OUTLINED, "opts",
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
                ft.Row(
                    controls=[menu_btn],
                    alignment=ft.MainAxisAlignment.CENTER if collapsed else ft.MainAxisAlignment.END,
                ),
                logo,
                nav_items,
                ft.Container(expand=True),
                separator(),
                bottom_items,
            ],
        ),
    )
