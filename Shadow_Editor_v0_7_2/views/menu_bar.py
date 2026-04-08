"""
views/menu_bar.py — Barre d'outils d'édition flottante.
"""

import flet as ft

from theme import T
from my_emoji import EMOJI_DICT


def build_menu_bar(c, callbacks):
    """
    Construit la barre d'outils d'édition.

    callbacks attendus :
        call_assistant, run_ai_check, check_spelling,
        show_emoji_picker, show_voice_menu,
        copy_text_handler, paste_text_handler, cut_text_handler, clear_text
    """

    def tool_btn(label, icon, on_click, badge=None):
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
            tooltip=label,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=6),
                padding=ft.Padding(10, 6, 10, 6),
                overlay_color={ft.ControlState.HOVERED: c(T.L_HOVER, T.D_HOVER)},
            ),
            on_click=on_click,
        )

    def icon_btn(tooltip, icon, on_click):
        """Bouton icône seul avec tooltip."""
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

    menu = ft.Container(
        padding=ft.Padding(8, 4, 8, 4), border_radius=10,
        bgcolor=c(T.L_TOOLBAR, T.D_TOOLBAR),
        border=ft.Border.all(1, c(T.L_TB_BORDER, T.D_TB_BORDER)),
        shadow=ft.BoxShadow(spread_radius=0, blur_radius=8,
                            color=ft.Colors.with_opacity(0.06, ft.Colors.BLACK),
                            offset=ft.Offset(0, 2)),
        content=ft.Row(spacing=2, controls=[
            tool_btn("Assistant", ft.Icons.SMART_TOY_OUTLINED,
                     lambda e: callbacks["call_assistant"]()),
            tool_btn("Correcteur IA", ft.Icons.SPELLCHECK,
                     lambda e: callbacks["run_ai_check"]()),
            sep(),
            tool_btn("Orthographe", ft.Icons.ABC,
                     lambda e: callbacks["check_spelling"]()),
            tool_btn("Émojis", ft.Icons.EMOJI_EMOTIONS_OUTLINED,
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
            icon_btn("Rétablir  Ctrl+Y", ft.Icons.REDO,
                     callbacks["redo"]),
        ]),
    )
    return ft.Row(
        alignment=ft.MainAxisAlignment.CENTER,
        controls=[ft.Container(content=menu, margin=10)],
    )
