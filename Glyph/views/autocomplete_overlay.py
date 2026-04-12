"""
views/autocomplete_overlay.py -- Popup flottante d'autocompletion.

Affiche les suggestions de mots et la prediction IA dans un menu
flottant elegant au-dessus de l'editeur.
"""

import flet as ft

from theme import T


def build_autocomplete_popup(state, c) -> ft.Container:
    """Construit le conteneur de la popup d'autocompletion.

    Args:
        state: EditorState avec les champs ac_*.
        c: helper couleur c(light, dark).

    Returns:
        ft.Container positionne en overlay dans un Stack.
    """
    if not state.ac_visible:
        return ft.Container(visible=False)

    items: list[ft.Control] = []

    # -- Suggestions de mots (locales) --
    for i, word in enumerate(state.ac_suggestions):
        is_selected = (i == state.ac_selected)
        items.append(
            ft.Container(
                padding=ft.Padding(12, 6, 12, 6),
                border_radius=6,
                bgcolor=(
                    c(T.L_SELECTED, T.D_SELECTED) if is_selected
                    else ft.Colors.TRANSPARENT
                ),
                content=ft.Row(
                    spacing=8,
                    controls=[
                        ft.Container(
                            width=20, height=20, border_radius=4,
                            bgcolor=c(T.L_ACCENT_LT, T.D_ACCENT_LT),
                            alignment=ft.Alignment(0, 0),
                            content=ft.Text(
                                "Aa", size=9,
                                color=c(T.L_ACCENT, T.D_ACCENT),
                                font_family="Nunito SemiBold",
                                weight=ft.FontWeight.W_600,
                                text_align=ft.TextAlign.CENTER,
                            ),
                        ),
                        ft.Text(
                            word, size=13,
                            font_family="Nunito",
                            color=c(T.L_PRIMARY, T.D_PRIMARY),
                            weight=(
                                ft.FontWeight.W_600 if is_selected
                                else ft.FontWeight.W_400
                            ),
                        ),
                    ],
                ),
            )
        )

    # -- Prediction IA (separee visuellement) --
    if state.ac_ai_suggestion:
        ai_idx = len(state.ac_suggestions)
        is_selected = (state.ac_selected == ai_idx)

        if items:
            items.append(
                ft.Container(
                    height=1, margin=ft.Margin(8, 2, 8, 2),
                    bgcolor=c(T.L_BORDER, T.D_BORDER),
                )
            )

        # Tronquer la prediction pour la popup
        ai_text = state.ac_ai_suggestion
        if len(ai_text) > 60:
            ai_text = ai_text[:57] + "..."

        items.append(
            ft.Container(
                padding=ft.Padding(12, 6, 12, 6),
                border_radius=6,
                bgcolor=(
                    c(T.L_SELECTED, T.D_SELECTED) if is_selected
                    else ft.Colors.TRANSPARENT
                ),
                content=ft.Row(
                    spacing=8,
                    controls=[
                        ft.Container(
                            width=20, height=20, border_radius=4,
                            bgcolor=ft.Colors.with_opacity(
                                0.12, c(T.L_SUCCESS, T.D_SUCCESS),
                            ),
                            alignment=ft.Alignment(0, 0),
                            content=ft.Text(
                                "IA", size=9,
                                color=c(T.L_SUCCESS, T.D_SUCCESS),
                                font_family="Nunito SemiBold",
                                weight=ft.FontWeight.W_600,
                                text_align=ft.TextAlign.CENTER,
                            ),
                        ),
                        ft.Text(
                            ai_text, size=13, italic=True,
                            font_family="Nunito",
                            color=(
                                c(T.L_PRIMARY, T.D_PRIMARY) if is_selected
                                else c(T.L_TERTIARY, T.D_TERTIARY)
                            ),
                            weight=(
                                ft.FontWeight.W_600 if is_selected
                                else ft.FontWeight.W_400
                            ),
                        ),
                    ],
                ),
            )
        )

    if not items:
        return ft.Container(visible=False)

    # -- Hint clavier en bas --
    items.append(
        ft.Container(
            padding=ft.Padding(12, 4, 12, 4),
            content=ft.Row(
                spacing=12,
                controls=[
                    _kbd_hint("Tab", "accepter", c),
                    _kbd_hint("\u2191\u2193", "naviguer", c),
                    _kbd_hint("Esc", "fermer", c),
                ],
            ),
        )
    )

    popup = ft.Container(
        width=340,
        bgcolor=c(T.L_SURFACE, T.D_SURFACE),
        border=ft.Border(
            top=ft.BorderSide(1, c(T.L_BORDER, T.D_BORDER)),
            right=ft.BorderSide(1, c(T.L_BORDER, T.D_BORDER)),
            bottom=ft.BorderSide(1, c(T.L_BORDER, T.D_BORDER)),
            left=ft.BorderSide(1, c(T.L_BORDER, T.D_BORDER)),
        ),
        border_radius=10,
        shadow=ft.BoxShadow(
            spread_radius=0, blur_radius=16, offset=ft.Offset(0, 4),
            color=ft.Colors.with_opacity(0.12, "#000000"),
        ),
        padding=ft.Padding(0, 6, 0, 4),
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        animate_opacity=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
        content=ft.Column(spacing=0, controls=items, tight=True),
    )

    # Positionner en bas a gauche de la zone editeur
    return ft.Container(
        content=popup,
        alignment=ft.Alignment(-0.85, 0.95),
    )


def _kbd_hint(key: str, label: str, c) -> ft.Row:
    """Petit badge clavier + label."""
    return ft.Row(
        spacing=4,
        controls=[
            ft.Container(
                padding=ft.Padding(5, 2, 5, 2),
                border_radius=4,
                bgcolor=c(T.L_HOVER, T.D_HOVER),
                border=ft.Border(
                    top=ft.BorderSide(1, c(T.L_BORDER, T.D_BORDER)),
                    right=ft.BorderSide(1, c(T.L_BORDER, T.D_BORDER)),
                    bottom=ft.BorderSide(1, c(T.L_BORDER, T.D_BORDER)),
                    left=ft.BorderSide(1, c(T.L_BORDER, T.D_BORDER)),
                ),
                content=ft.Text(
                    key, size=10,
                    font_family="Nunito SemiBold",
                    color=c(T.L_SECONDARY, T.D_SECONDARY),
                ),
            ),
            ft.Text(
                label, size=10,
                color=c(T.L_MUTED, T.D_MUTED),
                font_family="Nunito",
            ),
        ],
    )
