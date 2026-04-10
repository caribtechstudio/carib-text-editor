"""
views/menu_bar.py -- Barre d'outils d'edition flottante.
"""

import flet as ft

from theme import T
from my_emoji import EMOJI_DICT


def build_menu_bar(c, callbacks):
    """
    Construit la barre d'outils d'edition.

    callbacks attendus :
        call_assistant, check_spelling,
        show_emoji_picker, show_voice_menu,
        copy_text_handler, paste_text_handler, cut_text_handler, clear_text,
        undo, redo, toggle_search, zoom_in, zoom_out,
        --- IA ---
        run_correction, run_translate, run_reformulate,
        show_model_manager
    """

    def tool_btn(label, icon, on_click, badge=None, tooltip=None):
        row_ctrls = [
            ft.Icon(icon, size=15, color=c(T.L_SECONDARY, T.D_SECONDARY)),
            ft.Text(label, size=13, font_family="Nunito SemiBold",
                    color=c(T.L_SECONDARY, T.D_SECONDARY)),
        ]
        if badge:
            row_ctrls.append(ft.Container(
                width=28, height=18, border_radius=9,
                bgcolor=c(T.L_ACCENT_LT, T.D_ACCENT_LT), alignment=ft.Alignment(0, 0),
                content=ft.Text(str(badge), size=10, color=c(T.L_ACCENT, T.D_ACCENT),
                                weight=ft.FontWeight.W_500),
            ))
        return ft.TextButton(
            content=ft.Row(spacing=6, tight=True, controls=row_ctrls),
            tooltip=tooltip or label,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=6),
                padding=ft.Padding(10, 6, 10, 6),
                overlay_color={ft.ControlState.HOVERED: c(T.L_HOVER, T.D_HOVER)},
            ),
            on_click=on_click,
        )

    def icon_btn(tooltip, icon, on_click):
        return ft.IconButton(
            icon=icon, icon_size=17,
            icon_color=c(T.L_SECONDARY, T.D_SECONDARY),
            tooltip=tooltip,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=6),
                padding=6,
                overlay_color={ft.ControlState.HOVERED: c(T.L_HOVER, T.D_HOVER)},
            ),
            on_click=on_click,
        )

    def sep():
        return ft.Container(width=1, height=20, bgcolor=c(T.L_BORDER, T.D_BORDER),
                            margin=ft.Margin(4, 0, 4, 0))

    # --- Sous-menu Traduction ---
    def _translate_menu_item(label, on_click):
        return ft.MenuItemButton(
            content=ft.Text(label, size=12),
            on_click=on_click,
        )

    translate_menu = ft.SubmenuButton(
        content=ft.Row(spacing=6, tight=True, controls=[
            ft.Icon(ft.Icons.TRANSLATE, size=15, color=c(T.L_SECONDARY, T.D_SECONDARY)),
            ft.Text("Traduction", size=13, font_family="Nunito SemiBold",
                    color=c(T.L_SECONDARY, T.D_SECONDARY)),
        ]),
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=6),
            padding=ft.Padding(10, 6, 10, 6),
            overlay_color={ft.ControlState.HOVERED: c(T.L_HOVER, T.D_HOVER)},
        ),
        controls=[
            _translate_menu_item("Francais -> Anglais",
                                 lambda e: callbacks["run_translate_fr_en"]()),
            _translate_menu_item("Anglais -> Francais",
                                 lambda e: callbacks["run_translate_en_fr"]()),
        ],
    )

    # --- Sous-menu Reformulation ---
    reformulate_menu = ft.SubmenuButton(
        content=ft.Row(spacing=6, tight=True, controls=[
            ft.Icon(ft.Icons.AUTO_FIX_HIGH, size=15, color=c(T.L_SECONDARY, T.D_SECONDARY)),
            ft.Text("Reformulation", size=13, font_family="Nunito SemiBold",
                    color=c(T.L_SECONDARY, T.D_SECONDARY)),
        ]),
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=6),
            padding=ft.Padding(10, 6, 10, 6),
            overlay_color={ft.ControlState.HOVERED: c(T.L_HOVER, T.D_HOVER)},
        ),
        controls=[
            _translate_menu_item("Reformuler",
                                 lambda e: callbacks["run_reformulate"]()),
            _translate_menu_item("Ton naturel",
                                 lambda e: callbacks["run_natural"]()),
            _translate_menu_item("Ton professionnel",
                                 lambda e: callbacks["run_professional"]()),
            ft.Divider(height=1),
            _translate_menu_item("Resumer",
                                 lambda e: callbacks["run_summarize"]()),
            _translate_menu_item("Mots-cles",
                                 lambda e: callbacks["run_keywords"]()),
        ],
    )

    menu = ft.Container(
        padding=ft.Padding(8, 4, 8, 4), border_radius=10,
        bgcolor=c(T.L_TOOLBAR, T.D_TOOLBAR),
        border=ft.Border.all(1, c(T.L_TB_BORDER, T.D_TB_BORDER)),
        shadow=ft.BoxShadow(spread_radius=0, blur_radius=8,
                            color=ft.Colors.with_opacity(0.06, ft.Colors.BLACK),
                            offset=ft.Offset(0, 2)),
        content=ft.MenuBar(
            expand=True,
            style=ft.MenuStyle(
                bgcolor=ft.Colors.TRANSPARENT,
                shadow_color=ft.Colors.TRANSPARENT,
                padding=0,
            ),
            controls=[
                # Assistant vocal
                tool_btn("Assistant", ft.Icons.SMART_TOY_OUTLINED,
                         lambda e: callbacks["call_assistant"]()),
                sep(),
                # --- 3 boutons IA ---
                tool_btn("Correction", ft.Icons.SPELLCHECK,
                         lambda e: callbacks["run_correction"](),
                         tooltip="Correction IA  F7"),
                translate_menu,
                reformulate_menu,
                sep(),
                # Orthographe classique
                tool_btn("Orthographe", ft.Icons.ABC,
                         lambda e: callbacks["check_spelling"](),
                         tooltip="Orthographe  F6"),
                tool_btn("Emojis", ft.Icons.EMOJI_EMOTIONS_OUTLINED,
                         lambda e: callbacks["show_emoji_picker"](),
                         badge=len(EMOJI_DICT)),
                sep(),
                tool_btn("Voix", ft.Icons.MIC_NONE,
                         lambda e: callbacks["show_voice_menu"]()),
                sep(),
                icon_btn("Copier", ft.Icons.CONTENT_COPY,
                         callbacks["copy_text_handler"]),
                icon_btn("Coller", ft.Icons.CONTENT_PASTE,
                         callbacks["paste_text_handler"]),
                icon_btn("Couper", ft.Icons.CONTENT_CUT,
                         callbacks["cut_text_handler"]),
                icon_btn("Effacer tout", ft.Icons.DELETE_OUTLINE,
                         lambda e: callbacks["clear_text"]()),
                sep(),
                icon_btn("Annuler  Ctrl+Z", ft.Icons.UNDO,
                         callbacks["undo"]),
                icon_btn("Retablir  Ctrl+Y", ft.Icons.REDO,
                         callbacks["redo"]),
                sep(),
                icon_btn("Zoom arriere  Ctrl+Num-", ft.Icons.REMOVE_CIRCLE_OUTLINE,
                         lambda e: callbacks["zoom_out"]()),
                icon_btn("Zoom avant  Ctrl+Num+", ft.Icons.ADD_CIRCLE_OUTLINE,
                         lambda e: callbacks["zoom_in"]()),
                sep(),
                icon_btn("Rechercher  Ctrl+F", ft.Icons.SEARCH,
                         lambda e: callbacks["toggle_search"]()),
            ],
        ),
    )
    return ft.Row(
        alignment=ft.MainAxisAlignment.CENTER,
        controls=[ft.Container(content=menu, margin=10)],
    )
