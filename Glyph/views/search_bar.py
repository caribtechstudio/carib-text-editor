"""
views/search_bar.py — Barre de recherche intégrée et surlignage des résultats.
"""

import flet as ft

from constants import svg_icon, svg_icon_btn
from theme import T


# ------------------------------------------------------------------
# Surlignage — couche Text avec TextSpan colorés
# ------------------------------------------------------------------

def build_highlight_text(text, matches, current_index, c):
    """
    Construit un ft.Text avec des TextSpan surlignés pour chaque match.

    - Match courant : fond ambre vif
    - Autres matches : fond jaune pâle
    - Texte normal : couleur primaire standard
    """
    if not text:
        return ft.Text("")

    normal_style = ft.TextStyle(
        size=16, height=1.4, font_family="Nunito", letter_spacing=0.2,
        color=c(T.L_PRIMARY, T.D_PRIMARY),
    )
    current_style = ft.TextStyle(
        size=16, height=1.4, font_family="Nunito", letter_spacing=0.2,
        color=c(T.L_PRIMARY, T.D_PRIMARY),
        bgcolor=ft.Colors.with_opacity(0.55, c(T.L_HL_CURRENT, T.D_HL_CURRENT)),
    )
    other_style = ft.TextStyle(
        size=16, height=1.4, font_family="Nunito", letter_spacing=0.2,
        color=c(T.L_PRIMARY, T.D_PRIMARY),
        bgcolor=ft.Colors.with_opacity(0.35, c(T.L_HL_OTHER, T.D_HL_OTHER)),
    )

    spans = []
    last_end = 0

    for i, (start, end) in enumerate(matches):
        # Texte normal avant le match
        if start > last_end:
            spans.append(ft.TextSpan(text[last_end:start], style=normal_style))
        # Match surligne
        style = current_style if i == current_index else other_style
        spans.append(ft.TextSpan(text[start:end], style=style))
        last_end = end

    # Texte restant après le dernier match
    if last_end < len(text):
        spans.append(ft.TextSpan(text[last_end:], style=normal_style))

    return ft.Text(spans=spans, selectable=False)


def build_search_bar(c, search_state, callbacks):
    """
    Construit la barre de recherche intégrée avec animation.

    callbacks attendus :
        on_query_change, on_search, on_next, on_prev, on_close,
        toggle_case, toggle_whole_word, toggle_regex
    """

    def _toggle_btn(tooltip, label, active, on_click):
        """Petit bouton toggle pour les options de recherche."""
        return ft.Container(
            width=30, height=26, border_radius=4,
            alignment=ft.Alignment(0, 0),
            bgcolor=c(T.L_ACCENT_LT, T.D_ACCENT_LT) if active else ft.Colors.TRANSPARENT,
            border=ft.Border.all(
                1,
                c(T.L_ACCENT, T.D_ACCENT) if active else c(T.L_BORDER, T.D_BORDER),
            ),
            tooltip=tooltip,
            on_click=on_click,
            ink=True,
            content=ft.Text(
                label, size=11, weight=ft.FontWeight.W_700,
                text_align=ft.TextAlign.CENTER,
                font_family="Nunito Bold",
                color=c(T.L_ACCENT, T.D_ACCENT) if active else c(T.L_TERTIARY, T.D_TERTIARY),
            ),
        )

    search_field = ft.TextField(
        value=search_state.query,
        hint_text="Rechercher...",
        hint_style=ft.TextStyle(
            size=13, font_family="Nunito", color=c(T.L_MUTED, T.D_MUTED), italic=True,
        ),
        text_size=13,
        text_style=ft.TextStyle(
            size=13, font_family="Nunito", color=c(T.L_PRIMARY, T.D_PRIMARY),
        ),
        border=ft.InputBorder.NONE,
        content_padding=ft.Padding(10, 0, 10, 0),
        cursor_color=c(T.L_ACCENT, T.D_ACCENT),
        cursor_height=16,
        cursor_width=1.5,
        bgcolor=ft.Colors.TRANSPARENT,
        focused_bgcolor=ft.Colors.TRANSPARENT,
        hover_color=ft.Colors.TRANSPARENT,
        expand=True,
        on_change=callbacks["on_query_change"],
        on_submit=callbacks["on_search"],
        autofocus=True,
    )

    counter = ft.Text(
        search_state.label,
        size=11, font_family="Nunito SemiBold",
        color=c(T.L_ACCENT, T.D_ACCENT) if search_state.matches else c(T.L_MUTED, T.D_MUTED),
    )

    nav_btn_style = ft.ButtonStyle(
        shape=ft.RoundedRectangleBorder(radius=4),
        padding=2,
        overlay_color={ft.ControlState.HOVERED: c(T.L_HOVER, T.D_HOVER)},
    )

    bar_content = ft.Row(
        spacing=4,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            svg_icon("search", size=18, color=c(T.L_MUTED, T.D_MUTED)),
            search_field,
            counter,
            ft.Container(width=1, height=20, bgcolor=c(T.L_BORDER, T.D_BORDER)),
            _toggle_btn("Sensible à la casse", "Aa", search_state.case_sensitive,
                        lambda e: callbacks["toggle_case"]()),
            _toggle_btn("Mot entier", "Ab", search_state.whole_word,
                        lambda e: callbacks["toggle_whole_word"]()),
            _toggle_btn("Expression régulière", ".*", search_state.use_regex,
                        lambda e: callbacks["toggle_regex"]()),
            ft.Container(width=1, height=20, bgcolor=c(T.L_BORDER, T.D_BORDER)),
            svg_icon_btn("angle-circle-up", size=20,
                         color=c(T.L_SECONDARY, T.D_SECONDARY),
                         tooltip="Précédent", padding=2,
                         on_click=lambda e: callbacks["on_prev"]()),
            svg_icon_btn("angle-circle-down", size=20,
                         color=c(T.L_SECONDARY, T.D_SECONDARY),
                         tooltip="Suivant  Enter", padding=2,
                         on_click=lambda e: callbacks["on_next"]()),
            ft.IconButton(
                icon=ft.Icons.CLOSE, icon_size=16,
                icon_color=c(T.L_TERTIARY, T.D_TERTIARY),
                tooltip="Fermer  Échap",
                style=nav_btn_style,
                on_click=lambda e: callbacks["on_close"](),
            ),
        ],
    )

    inner = ft.Container(
        content=bar_content,
        padding=ft.Padding(12, 6, 8, 6),
        border_radius=8,
        bgcolor=c(T.L_SURFACE, T.D_SURFACE),
        border=ft.Border.all(1, c(T.L_TB_BORDER, T.D_TB_BORDER)),
        shadow=ft.BoxShadow(
            spread_radius=0, blur_radius=12,
            color=ft.Colors.with_opacity(0.08, ft.Colors.BLACK),
            offset=ft.Offset(0, 4),
        ),
    )

    # Wrapper centré avec espacement aéré
    bar = ft.Container(
        content=inner,
        alignment=ft.Alignment(0, 0),
        padding=ft.Padding(40, 6, 40, 6),
        animate_opacity=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
        opacity=1,
    )

    return bar, search_field, counter
