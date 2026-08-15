"""
views/sidebar.py — Barre latérale pliable (fichier + navigation).
"""

import os
import flet as ft

from core.constants import (ICON_MD, ICON_SM, ICON_XS, RADIUS_MD, TEXT_CAPTION,
                            TEXT_UI, MOTION_FAST, hover_effect, svg_icon,
                            UI_FONT, UI_FONT_STRONG)
from core.theme import T


def build_sidebar(state, c, callbacks):
    collapsed = state.sidebar_collapsed
    recent_files = getattr(state, "recent_files", [])
    recent_expanded = getattr(state, "recent_expanded", False)
    open_recent_fn = callbacks.get("open_recent")
    toggle_recent_fn = callbacks.get("toggle_recent_expanded")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def item(label, icon_name, key, on_click=None, tooltip_text=None):
        active = (state.sidebar_key == key)
        tip = tooltip_text or label
        ico_color = c(T.L_ACCENT, T.D_ACCENT) if active else c(T.L_PRIMARY, T.D_PRIMARY)
        idle_bg = c(T.L_SELECTED, T.D_SELECTED) if active else ft.Colors.TRANSPARENT
        hover_bg = c(T.L_SELECTED, T.D_SELECTED) if active else c(T.L_HOVER, T.D_HOVER)

        if collapsed:
            return ft.Container(
                width=36, height=36, border_radius=RADIUS_MD,
                bgcolor=idle_bg,
                alignment=ft.Alignment(0, 0),
                ink=True, on_click=on_click,
                scale=ft.Scale(scale=1.0),
                animate=ft.Animation(MOTION_FAST, ft.AnimationCurve.EASE_OUT),
                animate_scale=ft.Animation(MOTION_FAST, ft.AnimationCurve.EASE_OUT),
                on_hover=hover_effect(idle_bg, hover_bg, scale=1.04,
                                      hover_opacity=1.0),
                tooltip=tip,
                content=svg_icon(icon_name, size=ICON_MD, color=ico_color),
            )

        return ft.Container(
            height=38, padding=ft.Padding(10, 0, 10, 0), border_radius=RADIUS_MD,
            bgcolor=idle_bg,
            ink=True, on_click=on_click,
            scale=ft.Scale(scale=1.0),
            animate=ft.Animation(MOTION_FAST, ft.AnimationCurve.EASE_OUT),
            animate_scale=ft.Animation(MOTION_FAST, ft.AnimationCurve.EASE_OUT),
            on_hover=hover_effect(idle_bg, hover_bg, scale=1.01,
                                  hover_opacity=1.0),
            tooltip=tip,
            content=ft.Row(spacing=11, controls=[
                svg_icon(icon_name, size=ICON_MD, color=ico_color),
                ft.Text(label, size=13.5, expand=True,
                        font_family=UI_FONT_STRONG if active else UI_FONT,
                        weight=ft.FontWeight.W_700 if active else ft.FontWeight.W_500,
                        color=c(T.L_PRIMARY, T.D_PRIMARY) if active else c(T.L_SECONDARY, T.D_SECONDARY)),
            ]),
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

    # ------------------------------------------------------------------
    # Bouton "Ouvrir récent"
    # Mode étendu  → accordéon inline
    # Mode réduit  → PopupMenuButton avec icône seule
    # ------------------------------------------------------------------
    def _recent_accordion():
        """Bouton accordéon — utilise les objets persistants passés via callbacks."""
        ico_color = c(T.L_PRIMARY, T.D_PRIMARY)

        # Chevron persistant — sa propriété src est mise à jour directement par AppController
        chevron_widget = callbacks.get("recent_chevron") or svg_icon(
            "angle-circle-down" if recent_expanded else "angle-circle-right",
            size=ICON_XS, color=c(T.L_MUTED, T.D_MUTED),
        )

        header_btn = ft.Container(
            height=38, padding=ft.Padding(10, 0, 10, 0),
            border_radius=RADIUS_MD,
            bgcolor=ft.Colors.TRANSPARENT,
            ink=True,
            animate=ft.Animation(MOTION_FAST, ft.AnimationCurve.EASE_OUT),
            on_hover=hover_effect(ft.Colors.TRANSPARENT,
                                  c(T.L_HOVER, T.D_HOVER),
                                  scale=1.0, hover_opacity=1.0),
            tooltip="Ouvrir récent",
            on_click=lambda e: toggle_recent_fn() if toggle_recent_fn else None,
            content=ft.Row(spacing=11, controls=[
                svg_icon("alarm-clock", size=ICON_MD, color=ico_color),
                ft.Text("Ouvrir récent", size=13.5, expand=True,
                        font_family=UI_FONT,
                        color=c(T.L_SECONDARY, T.D_SECONDARY)),
                chevron_widget,
            ]),
        )

        # Conteneur animé persistant — height et opacity mis à jour directement
        expandable = callbacks.get("recent_expandable")

        return ft.Column(spacing=1, controls=[header_btn, expandable])

    def _recent_popup():
        """PopupMenuButton icône seule (mode réduit)."""
        if recent_files:
            popup_items = [
                ft.PopupMenuItem(
                    content=ft.Row(spacing=8, controls=[
                        svg_icon("document", size=ICON_SM, color=c(T.L_SECONDARY, T.D_SECONDARY)),
                        ft.Text(os.path.basename(p), size=13,
                                font_family=UI_FONT, color=c(T.L_PRIMARY, T.D_PRIMARY)),
                    ]),
                    on_click=lambda e, p=p: open_recent_fn(p) if open_recent_fn else None,
                )
                for p in recent_files
            ]
        else:
            popup_items = [
                ft.PopupMenuItem(
                    content=ft.Text("Aucun fichier récent", size=13,
                                    font_family=UI_FONT, italic=True,
                                    color=c(T.L_MUTED, T.D_MUTED)),
                    disabled=True,
                )
            ]

        return ft.PopupMenuButton(
            tooltip="",
            items=popup_items,
            content=ft.Container(
                width=36, height=36, border_radius=RADIUS_MD,
                alignment=ft.Alignment(0, 0),
                bgcolor=ft.Colors.TRANSPARENT,
                tooltip="Ouvrir récent",
                content=svg_icon("alarm-clock", size=ICON_MD, color=c(T.L_PRIMARY, T.D_PRIMARY)),
            ),
        )

    # ------------------------------------------------------------------
    # Header
    # ------------------------------------------------------------------
    menu_icon = "angle-double-small-left" if not collapsed else "menu-burger"
    menu_btn = ft.Container(
        width=28, height=28, border_radius=8,
        alignment=ft.Alignment(0, 0),
        ink=True,
        on_click=lambda e: callbacks["toggle_sidebar"](),
        scale=ft.Scale(scale=1.0),
        animate_scale=ft.Animation(MOTION_FAST, ft.AnimationCurve.EASE_OUT),
        animate_opacity=ft.Animation(MOTION_FAST, ft.AnimationCurve.EASE_OUT),
        on_hover=hover_effect(scale=1.08, hover_opacity=0.72),
        tooltip="Réduire le menu" if not collapsed else "Ouvrir le menu",
        content=svg_icon(menu_icon, size=ICON_MD, color=c(T.L_PRIMARY, T.D_PRIMARY)),
    )

    if collapsed:
        header = ft.Row(controls=[menu_btn], alignment=ft.MainAxisAlignment.CENTER)
    else:
        header = ft.Container(
            height=40, padding=ft.Padding(6, 0, 2, 10),
            content=ft.Row(
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Text("FICHIER", expand=True,
                            style=ft.TextStyle(size=TEXT_CAPTION,
                                               font_family=UI_FONT_STRONG,
                                               weight=ft.FontWeight.W_700,
                                               letter_spacing=0.9,
                                               color=c(T.L_MUTED, T.D_MUTED))),
                    menu_btn,
                ],
            ),
        )

    # ------------------------------------------------------------------
    # Nav items
    # ------------------------------------------------------------------
    recent_widget = _recent_popup() if collapsed else _recent_accordion()

    nav_items = ft.Column(
        spacing=1,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER if collapsed else ft.CrossAxisAlignment.START,
        controls=[
            item("Ouvrir", "folder-open", "open",
                 on_click=callbacks["open_file"], tooltip_text="Ouvrir  Ctrl+O"),
            item("Ouvrir un dossier", "folder", "folder",
                 on_click=callbacks["open_workspace"],
                 tooltip_text="Ouvrir un dossier comme espace de travail"),
            recent_widget,
            item("Nouveau", "add-document", "new",
                 on_click=lambda e: callbacks["add_tab"](), tooltip_text="Nouveau  Ctrl+N"),
            separator(),
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

    # ------------------------------------------------------------------
    # Bottom items
    # ------------------------------------------------------------------
    ai_card = None if collapsed else ft.Container(
        margin=ft.Margin(4, 0, 4, 8), padding=ft.Padding(12, 11, 12, 11),
        border_radius=12, ink=True, bgcolor=c(T.L_ACCENT_LT, T.D_ACCENT_LT),
        tooltip="Ouvrir l’assistant IA  Ctrl+K",
        on_click=lambda e: callbacks["open_command_bar"](),
        scale=ft.Scale(scale=1.0),
        animate_scale=ft.Animation(MOTION_FAST, ft.AnimationCurve.EASE_OUT),
        animate_opacity=ft.Animation(MOTION_FAST, ft.AnimationCurve.EASE_OUT),
        on_hover=hover_effect(scale=1.015, hover_opacity=0.90),
        content=ft.Column(spacing=4, controls=[
            ft.Row(spacing=7, controls=[
                svg_icon("sparkles", size=ICON_SM, color=c(T.L_ACCENT, T.D_ACCENT)),
                ft.Text("Assistant IA", size=12, font_family=UI_FONT_STRONG,
                        weight=ft.FontWeight.W_700, color=c(T.L_ACCENT, T.D_ACCENT)),
            ]),
            ft.Text("Corriger, traduire, réécrire", size=11.5,
                    font_family=UI_FONT, color=c(T.L_SECONDARY, T.D_SECONDARY),
                    overflow=ft.TextOverflow.ELLIPSIS),
        ]),
    )

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

    # ------------------------------------------------------------------
    # Arborescence du dossier ouvert (mode étendu uniquement)
    # ------------------------------------------------------------------
    middle: list[ft.Control] = []
    if not collapsed and getattr(state, "workspace_path", ""):
        from views.workspace_view import build_workspace_panel
        panel = build_workspace_panel(state, c, callbacks)
        if panel is not None:
            middle = [separator(), panel]

    # Sans dossier ouvert, un ressort pousse les entrées du bas vers le bas ;
    # avec un dossier, c'est l'arborescence qui occupe l'espace disponible.
    spacer = ft.Container(expand=True) if not middle else None

    controls = [header, nav_items]
    controls.extend(middle)
    if spacer is not None:
        controls.append(spacer)
    if ai_card is not None:
        controls.append(ai_card)
    controls.extend([bottom_items])

    return ft.Container(
        expand=True,
        bgcolor=c(T.L_SIDEBAR, T.D_SIDEBAR),
        border=ft.Border.only(right=ft.BorderSide(1, c(T.L_BORDER, T.D_BORDER))),
        padding=ft.Padding(8, 14, 8, 10) if collapsed else ft.Padding(12, 14, 12, 10),
        content=ft.Column(
            expand=True, spacing=0,
            horizontal_alignment=(ft.CrossAxisAlignment.CENTER if collapsed
                                  else ft.CrossAxisAlignment.START),
            controls=controls,
        ),
    )
