"""
views/search_bar.py — Barre de recherche/remplacement et surlignage des résultats.
"""

import flet as ft

from constants import ICON_SM, svg_icon, svg_icon_btn, EDITOR_FONT, UI_FONT, UI_FONT_STRONG
from theme import T


# ------------------------------------------------------------------
# Surlignage — couche Text avec TextSpan colorés
# ------------------------------------------------------------------

def build_highlight_spans(text, matches, current_index, c,
                          size: int = 16) -> list[ft.TextSpan]:
    """Spans surlignés, un par occurrence trouvée.

    La taille suit le zoom de l'éditeur : sans cela, la couche de surlignage
    se décale du texte réel dès que l'utilisateur zoome.
    """
    if not text:
        return []

    def style(bg=None):
        return ft.TextStyle(
            size=size, height=1.4, font_family=EDITOR_FONT, letter_spacing=0.2,
            color=c(T.L_PRIMARY, T.D_PRIMARY), bgcolor=bg,
        )

    normal_style = style()
    current_style = style(ft.Colors.with_opacity(0.55, c(T.L_HL_CURRENT, T.D_HL_CURRENT)))
    other_style = style(ft.Colors.with_opacity(0.35, c(T.L_HL_OTHER, T.D_HL_OTHER)))

    spans = []
    last_end = 0
    for i, (start, end) in enumerate(matches):
        if start > last_end:
            spans.append(ft.TextSpan(text[last_end:start], style=normal_style))
        spans.append(ft.TextSpan(
            text[start:end],
            style=current_style if i == current_index else other_style,
        ))
        last_end = end

    if last_end < len(text):
        spans.append(ft.TextSpan(text[last_end:], style=normal_style))

    return spans


def build_highlight_text(text, matches, current_index, c, size: int = 16):
    """Construit un ft.Text avec des TextSpan surlignés pour chaque match."""
    if not text:
        return ft.Text("")
    return ft.Text(
        spans=build_highlight_spans(text, matches, current_index, c, size),
        selectable=False)


# ------------------------------------------------------------------
# Barre de recherche / remplacement
# ------------------------------------------------------------------

def _field(c, value, hint, on_change, on_submit=None, autofocus=False):
    """Champ de saisie compact, style barre d'outils."""
    return ft.TextField(
        value=value,
        hint_text=hint,
        hint_style=ft.TextStyle(size=13, font_family=UI_FONT,
                                color=c(T.L_MUTED, T.D_MUTED), italic=True),
        text_size=13,
        text_style=ft.TextStyle(size=13, font_family=UI_FONT,
                                color=c(T.L_PRIMARY, T.D_PRIMARY)),
        border=ft.InputBorder.NONE,
        content_padding=ft.Padding(10, 0, 10, 0),
        cursor_color=c(T.L_ACCENT, T.D_ACCENT),
        cursor_height=16, cursor_width=1.5,
        bgcolor=ft.Colors.TRANSPARENT,
        focused_bgcolor=ft.Colors.TRANSPARENT,
        hover_color=ft.Colors.TRANSPARENT,
        expand=True,
        on_change=on_change,
        on_submit=on_submit,
        autofocus=autofocus,
    )


def build_search_bar(c, search_state, callbacks):
    """Construit la barre de recherche, avec sa ligne de remplacement repliable.

    callbacks attendus :
        on_query_change, on_search, on_next, on_prev, on_close,
        toggle_case, toggle_whole_word, toggle_regex, toggle_replace,
        on_replacement_change, replace_current, replace_all
    """

    def toggle_btn(tooltip, label, active, on_click):
        return ft.Container(
            width=30, height=26, border_radius=4,
            alignment=ft.Alignment(0, 0),
            bgcolor=c(T.L_ACCENT_LT, T.D_ACCENT_LT) if active else ft.Colors.TRANSPARENT,
            border=ft.Border.all(
                1, c(T.L_ACCENT, T.D_ACCENT) if active else c(T.L_BORDER, T.D_BORDER)),
            tooltip=tooltip, on_click=on_click, ink=True,
            content=ft.Text(
                label, size=11, weight=ft.FontWeight.W_700,
                text_align=ft.TextAlign.CENTER, font_family=UI_FONT_STRONG,
                color=c(T.L_ACCENT, T.D_ACCENT) if active
                else c(T.L_TERTIARY, T.D_TERTIARY)),
        )

    def divider():
        return ft.Container(width=1, height=20, bgcolor=c(T.L_BORDER, T.D_BORDER))

    replace_open = search_state.replace_visible

    search_field = _field(c, search_state.query, "Rechercher…",
                          callbacks["on_query_change"], callbacks["on_search"],
                          autofocus=not replace_open)

    counter = ft.Text(
        search_state.label, size=11, font_family=UI_FONT_STRONG,
        color=c(T.L_ACCENT, T.D_ACCENT) if search_state.matches
        else c(T.L_MUTED, T.D_MUTED),
    )

    # Chevron d'ouverture du panneau de remplacement (à gauche, comme VS Code).
    expand_btn = ft.Container(
        width=22, height=52 if replace_open else 26,
        border_radius=4, alignment=ft.Alignment(0, 0), ink=True,
        tooltip="Remplacer  Ctrl+H",
        on_click=lambda e: callbacks["toggle_replace"](),
        content=svg_icon("angle-circle-down" if replace_open else "angle-circle-right",
                         size=ICON_SM, color=c(T.L_TERTIARY, T.D_TERTIARY)),
    )

    search_row = ft.Row(
        spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            svg_icon("search", size=ICON_SM, color=c(T.L_MUTED, T.D_MUTED)),
            search_field,
            counter,
            divider(),
            toggle_btn("Sensible à la casse", "Aa", search_state.case_sensitive,
                       lambda e: callbacks["toggle_case"]()),
            toggle_btn("Mot entier", "Ab", search_state.whole_word,
                       lambda e: callbacks["toggle_whole_word"]()),
            toggle_btn("Expression régulière", ".*", search_state.use_regex,
                       lambda e: callbacks["toggle_regex"]()),
            divider(),
            svg_icon_btn("angle-circle-up", size=ICON_SM,
                         color=c(T.L_SECONDARY, T.D_SECONDARY),
                         tooltip="Précédent  Maj+Entrée", padding=5,
                         on_click=lambda e: callbacks["on_prev"]()),
            svg_icon_btn("angle-circle-down", size=ICON_SM,
                         color=c(T.L_SECONDARY, T.D_SECONDARY),
                         tooltip="Suivant  Entrée", padding=5,
                         on_click=lambda e: callbacks["on_next"]()),
            ft.IconButton(
                icon=ft.Icons.CLOSE, icon_size=ICON_SM,
                icon_color=c(T.L_TERTIARY, T.D_TERTIARY),
                tooltip="Fermer  Échap",
                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=4),
                                     padding=2),
                on_click=lambda e: callbacks["on_close"]()),
        ],
    )

    rows = [search_row]
    replacement_field = None

    if replace_open:
        has_matches = bool(search_state.matches)
        replacement_field = _field(
            c, search_state.replacement, "Remplacer par…",
            callbacks["on_replacement_change"],
            lambda e: callbacks["replace_current"](),
            autofocus=True,
        )

        def action(label, tooltip, on_click, primary=False):
            return ft.Container(
                padding=ft.Padding(10, 5, 10, 5), border_radius=6,
                bgcolor=(c(T.L_ACCENT, T.D_ACCENT) if primary
                         else ft.Colors.TRANSPARENT),
                border=None if primary else ft.Border.all(
                    1, c(T.L_BORDER, T.D_BORDER)),
                ink=True, tooltip=tooltip,
                on_click=(lambda e: on_click()) if has_matches else None,
                opacity=1.0 if has_matches else 0.45,
                content=ft.Text(
                    label, size=11, font_family=UI_FONT_STRONG,
                    color="#FFFFFF" if primary else c(T.L_SECONDARY, T.D_SECONDARY)),
            )

        rows.append(ft.Row(
            spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                svg_icon("edit", size=ICON_SM, color=c(T.L_MUTED, T.D_MUTED)),
                replacement_field,
                action("Remplacer", "Remplacer cette occurrence  Entrée",
                       callbacks["replace_current"], primary=True),
                action("Tout remplacer",
                       f"Remplacer les {search_state.total} occurrence(s)",
                       callbacks["replace_all"]),
            ],
        ))

    inner = ft.Container(
        content=ft.Row(
            spacing=2, vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[expand_btn, ft.Column(spacing=6, expand=True, controls=rows)],
        ),
        padding=ft.Padding(8, 6, 8, 6), border_radius=8,
        bgcolor=c(T.L_SURFACE, T.D_SURFACE),
        border=ft.Border.all(1, c(T.L_TB_BORDER, T.D_TB_BORDER)),
        shadow=ft.BoxShadow(spread_radius=0, blur_radius=12,
                            color=ft.Colors.with_opacity(0.08, ft.Colors.BLACK),
                            offset=ft.Offset(0, 4)),
    )

    bar = ft.Container(
        content=inner, alignment=ft.Alignment(0, 0),
        padding=ft.Padding(40, 6, 40, 6),
        animate_opacity=ft.Animation(200, ft.AnimationCurve.EASE_OUT), opacity=1,
    )

    return bar, search_field, counter
