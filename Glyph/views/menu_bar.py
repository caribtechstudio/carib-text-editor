"""
views/menu_bar.py -- Barre d'outils d'edition flottante.
"""

import flet as ft

from theme import T


def build_menu_bar(c, callbacks):
    """
    Construit la barre d'outils d'edition.

    callbacks attendus :
        show_emoji_picker, show_voice_menu,
        copy_text_handler, paste_text_handler, cut_text_handler, clear_text,
        undo, redo, toggle_search, zoom_in, zoom_out,
        --- IA ---
        run_correction, run_translate, run_reformulate,
        show_model_manager
    """

    def tool_btn(tooltip, icon, on_click):
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
        content=ft.Icon(ft.Icons.TRANSLATE, size=17,
                        color=c(T.L_SECONDARY, T.D_SECONDARY)),
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=6),
            padding=6,
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
        content=ft.Icon(ft.Icons.AUTO_FIX_HIGH, size=17,
                        color=c(T.L_SECONDARY, T.D_SECONDARY)),
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=6),
            padding=6,
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
                # --- 3 boutons IA ---
                tool_btn("Correction IA  F7", ft.Icons.SPELLCHECK,
                         lambda e: callbacks["run_correction"]()),
                translate_menu,
                reformulate_menu,
                sep(),
                tool_btn("Emojis", ft.Icons.EMOJI_EMOTIONS_OUTLINED,
                         lambda e: callbacks["show_emoji_picker"]()),
                sep(),
                tool_btn("Voix", ft.Icons.MIC_NONE,
                         lambda e: callbacks["show_voice_menu"]()),
                sep(),
                tool_btn("Copier", ft.Icons.CONTENT_COPY,
                         callbacks["copy_text_handler"]),
                tool_btn("Coller", ft.Icons.CONTENT_PASTE,
                         callbacks["paste_text_handler"]),
                tool_btn("Couper", ft.Icons.CONTENT_CUT,
                         callbacks["cut_text_handler"]),
                tool_btn("Effacer tout", ft.Icons.DELETE_OUTLINE,
                         lambda e: callbacks["clear_text"]()),
                sep(),
                tool_btn("Annuler  Ctrl+Z", ft.Icons.UNDO,
                         callbacks["undo"]),
                tool_btn("Retablir  Ctrl+Y", ft.Icons.REDO,
                         callbacks["redo"]),
                sep(),
                tool_btn("Zoom arriere  Ctrl+Num-", ft.Icons.REMOVE_CIRCLE_OUTLINE,
                         lambda e: callbacks["zoom_out"]()),
                tool_btn("Zoom avant  Ctrl+Num+", ft.Icons.ADD_CIRCLE_OUTLINE,
                         lambda e: callbacks["zoom_in"]()),
                sep(),
                tool_btn("Rechercher  Ctrl+F", ft.Icons.SEARCH,
                         lambda e: callbacks["toggle_search"]()),
                sep(),
                tool_btn("Mode Texte  Ctrl+1", ft.Icons.EDIT_NOTE,
                         lambda e: callbacks["set_mode"]("text")),
                tool_btn("Mode Calcul  Ctrl+2", ft.Icons.CALCULATE_OUTLINED,
                         lambda e: callbacks["set_mode"]("calc")),
                tool_btn("Mode Lecture  Ctrl+3", ft.Icons.MENU_BOOK,
                         lambda e: callbacks["set_mode"]("read")),
            ],
        ),
    )
    return ft.Row(
        alignment=ft.MainAxisAlignment.CENTER,
        controls=[ft.Container(content=menu, margin=10)],
    )
