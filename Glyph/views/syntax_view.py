"""
views/syntax_view.py — Rendu de la coloration syntaxique et de la gouttière.

La coloration réutilise exactement le mécanisme déjà éprouvé pour la
recherche et le diff : un `ft.Text` composé de `TextSpan`, affiché **sous**
le `TextField` dont le texte est rendu transparent. Le champ conserve la
saisie, le curseur et la sélection ; la couche du dessous fournit les
couleurs.

Contrainte connue sur les numéros de ligne
------------------------------------------
Le `TextField` de Flet enroule toujours les lignes longues et n'expose
aucune information de mise en page. La gouttière compte donc les lignes
*logiques* : une ligne plus large que la fenêtre décale la numérotation des
lignes suivantes. C'est pourquoi la fonctionnalité est désactivée par défaut
et signalée comme telle dans les options.
"""

import flet as ft

from constants import EDITOR_FONT, UI_FONT, UI_FONT_STRONG
from theme import T


def _token_style(kind: str, size: int, dark: bool) -> ft.TextStyle:
    palette = T.SYNTAX_DARK if dark else T.SYNTAX_LIGHT
    return ft.TextStyle(
        size=size, height=1.4, font_family=(
            UI_FONT_STRONG if kind in T.SYNTAX_BOLD else EDITOR_FONT),
        letter_spacing=0.2,
        color=palette.get(kind),
        italic=kind in T.SYNTAX_ITALIC,
        weight=ft.FontWeight.W_600 if kind in T.SYNTAX_BOLD else None,
    )


def base_text_style(c, size: int) -> ft.TextStyle:
    """Style du texte non coloré — partagé par toutes les couches de spans."""
    return ft.TextStyle(
        size=size, height=1.4, font_family=EDITOR_FONT, letter_spacing=0.2,
        color=c(T.L_PRIMARY, T.D_PRIMARY),
    )


def build_syntax_spans(text: str, segments, c, size: int,
                       dark: bool) -> list[ft.TextSpan]:
    """Spans colorés du texte, prêts à être posés sur un `ft.Text` existant.

    Renvoyer des spans plutôt qu'un `ft.Text` permet à l'appelant de réutiliser
    le même contrôle d'un rendu à l'autre. C'est ce qui évite de détacher puis
    rattacher l'éditeur dans l'arbre Flutter à chaque frappe — opération qui
    lui faisait perdre le curseur.
    """
    base_style = base_text_style(c, size)

    if not segments:
        return [ft.TextSpan(text, style=base_style)] if text else []

    # Les styles sont mis en cache : un fichier Python de 2 000 lignes produit
    # des milliers de spans, mais seulement une dizaine de styles distincts.
    styles: dict[str, ft.TextStyle] = {}

    def style_for(kind: str) -> ft.TextStyle:
        if kind not in styles:
            styles[kind] = _token_style(kind, size, dark)
        return styles[kind]

    spans = []
    cursor = 0
    for start, end, kind in segments:
        if start > cursor:
            spans.append(ft.TextSpan(text[cursor:start], style=base_style))
        spans.append(ft.TextSpan(text[start:end], style=style_for(kind)))
        cursor = end

    if cursor < len(text):
        # Inclut la queue non colorée d'un très gros fichier (au-delà de
        # MAX_HIGHLIGHT_CHARS, le texte reste affiché, simplement sans couleur).
        spans.append(ft.TextSpan(text[cursor:], style=base_style))

    return spans


def build_syntax_text(text: str, segments, c, size: int, dark: bool):
    """Construit la couche colorée à partir des segments de `models.syntax`."""
    if not segments:
        return ft.Text(text, style=base_text_style(c, size), selectable=False)
    return ft.Text(spans=build_syntax_spans(text, segments, c, size, dark),
                   selectable=False)


def build_line_gutter(text: str, c, size: int, top_padding: int = 30,
                      current_line: int = 0):
    """Colonne de numéros de ligne, alignée sur les métriques de l'éditeur.

    Le rendu utilise un `ft.Text` unique avec la même taille et la même
    hauteur de ligne que l'éditeur : c'est ce qui garantit un alignement
    parfait tant qu'aucune ligne n'est enroulée.
    """
    total = text.count("\n") + 1
    width = max(38, 14 + len(str(total)) * (size * 0.62))

    muted = ft.TextStyle(size=size, height=1.4, font_family=EDITOR_FONT,
                         letter_spacing=0.2, color=c(T.L_MUTED, T.D_MUTED))
    active = ft.TextStyle(size=size, height=1.4, font_family=UI_FONT,
                          letter_spacing=0.2, color=c(T.L_ACCENT, T.D_ACCENT))

    # Un span par ligne coûtait un contrôle par ligne : sur un fichier de
    # 10 000 lignes, chaque frappe faisait comparer 10 000 objets au moteur de
    # rendu. Les numéros étant tous du même style sauf un, trois spans
    # suffisent — le rendu est identique au pixel près.
    def numbers(first: int, last: int) -> str:
        """Numéros de `first` à `last` inclus, un par ligne."""
        return "\n".join(str(n) for n in range(first, last + 1))

    spans = []
    if 1 <= current_line <= total:
        if current_line > 1:
            spans.append(ft.TextSpan(numbers(1, current_line - 1) + "\n",
                                     style=muted))
        spans.append(ft.TextSpan(
            str(current_line) + ("\n" if current_line < total else ""),
            style=active))
        if current_line < total:
            spans.append(ft.TextSpan(numbers(current_line + 1, total),
                                     style=muted))
    else:
        spans.append(ft.TextSpan(numbers(1, total), style=muted))

    return ft.Container(
        width=width,
        padding=ft.Padding(0, top_padding, 8, 0),
        bgcolor=c(T.L_SIDEBAR, T.D_SIDEBAR),
        border=ft.Border.only(right=ft.BorderSide(1, c(T.L_BORDER, T.D_BORDER))),
        alignment=ft.Alignment(1, -1),
        content=ft.Text(spans=spans, selectable=False,
                        text_align=ft.TextAlign.RIGHT, no_wrap=True),
    )
