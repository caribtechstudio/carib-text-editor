"""
views/ghost_text.py — Suggestion affichée en gris directement dans le texte.

La popup en liste obligeait l'utilisateur à quitter son texte des yeux, à
lire des propositions, puis à viser avec les flèches. Le standard actuel
(Copilot, Cursor, Gmail) fait l'inverse : la suite probable apparaît **en
gris clair juste après le curseur**, dans le flux. On l'accepte d'une
touche, ou on continue de taper et elle disparaît.

Le rendu réutilise la couche de spans déjà employée pour la recherche, le
diff et la coloration : `TextField` transparent au-dessus d'un `ft.Text`
qui, lui, contient le texte réel **plus** la suggestion grisée.

Conséquence importante : la suggestion n'existe que dans la couche
d'affichage. Elle n'est jamais dans `TextField.value` ni dans le document,
donc elle ne peut pas être enregistrée par accident.
"""

import flet as ft

from constants import (EDITOR_FONT, UI_FONT,
                       UI_FONT_STRONG)

from theme import T


def build_ghost_spans(text: str, cursor: int, suggestion: str, c, size: int,
                      segments=None, dark: bool = False) -> list[ft.TextSpan]:
    """Spans de la couche « texte réel + suggestion grisée ».

    Args:
        segments: coloration syntaxique éventuelle, appliquée au texte réel.
    """
    base_style = ft.TextStyle(
        size=size, height=1.4, font_family=EDITOR_FONT, letter_spacing=0.2,
        color=c(T.L_PRIMARY, T.D_PRIMARY),
    )
    ghost_style = ft.TextStyle(
        size=size, height=1.4, font_family=EDITOR_FONT, letter_spacing=0.2,
        # Assez visible pour être lue, assez pâle pour ne pas être confondue
        # avec du texte réellement saisi.
        color=ft.Colors.with_opacity(0.42, c(T.L_PRIMARY, T.D_PRIMARY)),
        italic=True,
    )

    cursor = max(0, min(cursor, len(text)))
    before, after = text[:cursor], text[cursor:]

    spans: list[ft.TextSpan] = []
    if segments:
        # On réutilise le découpage coloré, tronqué à la position du curseur.
        spans.extend(_colored_spans(before, segments, c, size, dark, base_style))
    elif before:
        spans.append(ft.TextSpan(before, style=base_style))

    if suggestion:
        spans.append(ft.TextSpan(suggestion, style=ghost_style))

    if after:
        if segments:
            shifted = [(s - cursor, e - cursor, k) for s, e, k in segments
                       if s >= cursor]
            spans.extend(_colored_spans(after, shifted, c, size, dark, base_style))
        else:
            spans.append(ft.TextSpan(after, style=base_style))

    return spans


def build_ghost_text(text: str, cursor: int, suggestion: str, c, size: int,
                     segments=None, dark: bool = False):
    """Compose la couche « texte réel + suggestion grisée »."""
    return ft.Text(
        spans=build_ghost_spans(text, cursor, suggestion, c, size,
                                segments=segments, dark=dark),
        selectable=False)


def _colored_spans(fragment: str, segments, c, size: int, dark: bool, base_style):
    """Applique les segments de coloration à un fragment de texte."""
    from views.syntax_view import _token_style

    styles: dict[str, ft.TextStyle] = {}
    out: list[ft.TextSpan] = []
    pos = 0

    for start, end, kind in segments:
        start, end = max(0, start), min(end, len(fragment))
        if end <= pos or start >= len(fragment):
            continue
        if start > pos:
            out.append(ft.TextSpan(fragment[pos:start], style=base_style))
        if kind not in styles:
            styles[kind] = _token_style(kind, size, dark)
        out.append(ft.TextSpan(fragment[start:end], style=styles[kind]))
        pos = end

    if pos < len(fragment):
        out.append(ft.TextSpan(fragment[pos:], style=base_style))
    return out


def build_ghost_hint(c, suggestion: str):
    """Petit rappel de raccourci, affiché en bas de l'éditeur."""
    if not suggestion:
        return None

    def key(label):
        return ft.Container(
            padding=ft.Padding(6, 2, 6, 2), border_radius=4,
            bgcolor=c(T.L_HOVER, T.D_HOVER),
            content=ft.Text(label, size=10, font_family=UI_FONT_STRONG,
                            color=c(T.L_SECONDARY, T.D_SECONDARY)),
        )

    return ft.Container(
        alignment=ft.Alignment(1, 1),
        padding=ft.Padding(0, 0, 24, 16),
        content=ft.Container(
            padding=ft.Padding(10, 6, 10, 6), border_radius=8,
            bgcolor=c(T.L_SURFACE, T.D_SURFACE),
            border=ft.Border.all(1, c(T.L_BORDER, T.D_BORDER)),
            content=ft.Row(spacing=6, tight=True, controls=[
                key("Tab"),
                ft.Text("accepter", size=10, font_family=UI_FONT,
                        color=c(T.L_MUTED, T.D_MUTED)),
                key("Ctrl+→"),
                ft.Text("un mot", size=10, font_family=UI_FONT,
                        color=c(T.L_MUTED, T.D_MUTED)),
                key("Échap"),
                ft.Text("ignorer", size=10, font_family=UI_FONT,
                        color=c(T.L_MUTED, T.D_MUTED)),
            ]),
        ),
    )
