"""
views/menu_bar.py -- Barre d'outils d'edition flottante.
"""

import flet as ft

from constants import svg_icon, svg_icon_btn
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
    ico_c = c(T.L_SECONDARY, T.D_SECONDARY)

    def tool_btn(tooltip, icon_name, on_click):
        return svg_icon_btn(icon_name, size=20, color=ico_c,
                            tooltip=tooltip, on_click=on_click, padding=6)

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
        content=svg_icon("language-exchange", size=20, color=ico_c),
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
        content=svg_icon("sparkles", size=20, color=ico_c),
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
                tool_btn("Correction IA  F7", "badge-check",
                         lambda e: callbacks["run_correction"]()),
                translate_menu,
                reformulate_menu,
                sep(),
                tool_btn("Emojis", "laugh-beam",
                         lambda e: callbacks["show_emoji_picker"]()),
                sep(),
                tool_btn("Voix", "circle-microphone-lines",
                         lambda e: callbacks["show_voice_menu"]()),
                sep(),
                tool_btn("Copier", "clone",
                         callbacks["copy_text_handler"]),
                tool_btn("Coller", "paste",
                         callbacks["paste_text_handler"]),
                tool_btn("Couper", "scissors",
                         callbacks["cut_text_handler"]),
                tool_btn("Effacer tout", "trash-xmark",
                         lambda e: callbacks["clear_text"]()),
                sep(),
                tool_btn("Annuler  Ctrl+Z", "rotate-left",
                         callbacks["undo"]),
                tool_btn("Retablir  Ctrl+Y", "turn-right",
                         callbacks["redo"]),
                sep(),
                tool_btn("Zoom arriere  Ctrl+Num-", "minus-circle",
                         lambda e: callbacks["zoom_out"]()),
                tool_btn("Zoom avant  Ctrl+Num+", "square-plus",
                         lambda e: callbacks["zoom_in"]()),
                sep(),
                tool_btn("Rechercher  Ctrl+F", "search",
                         lambda e: callbacks["toggle_search"]()),
                sep(),
                tool_btn("Mode Texte  Ctrl+1", "pen-field",
                         lambda e: callbacks["set_mode"]("text")),
                tool_btn("Mode Calcul  Ctrl+2", "calculator-simple",
                         lambda e: callbacks["set_mode"]("calc")),
                tool_btn("Mode Lecture  Ctrl+3", "book-open-cover",
                         lambda e: callbacks["set_mode"]("read")),
            ],
        ),
    )
    return ft.Row(
        alignment=ft.MainAxisAlignment.CENTER,
        controls=[ft.Container(content=menu, margin=10)],
    )
