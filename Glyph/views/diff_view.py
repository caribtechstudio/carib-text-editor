"""
views/diff_view.py — Aperçu des modifications IA directement dans le texte.

Plutôt que de lire une liste de corrections dans un panneau latéral et de
les appliquer une par une, l'utilisateur voit le résultat **à sa place dans
le document** : suppressions barrées en rouge, ajouts soulignés en vert.
Tab accepte, Échap refuse.

La technique est la même que celle déjà employée pour le surlignage de
recherche : un `ft.Text` composé de `TextSpan` colorés, affiché sous le
`TextField` rendu transparent. Aucune dépendance externe — `difflib` fait
partie de la bibliothèque standard.
"""

import difflib

import flet as ft

from core.constants import (EDITOR_FONT, UI_FONT,
                       UI_FONT_STRONG)

from core.theme import T

#: Au-delà, on compare par mots plutôt que par caractères : un diff
#: caractère par caractère sur un long texte est illisible et coûteux.
_CHAR_DIFF_LIMIT = 4000


def _tokenize(text: str) -> list[str]:
    """Découpe en mots + séparateurs, pour un diff lisible par un humain."""
    tokens: list[str] = []
    buf = []
    for ch in text:
        if ch.isalnum() or ch in "àâäéèêëïîôöùûüÿçÀÂÄÉÈÊËÏÎÔÖÙÛÜŸÇ'’-":
            buf.append(ch)
        else:
            if buf:
                tokens.append("".join(buf))
                buf = []
            tokens.append(ch)
    if buf:
        tokens.append("".join(buf))
    return tokens


def compute_diff(original: str, proposed: str) -> list[tuple[str, str]]:
    """Retourne une liste de (type, texte) où type vaut "=", "-" ou "+"."""
    if len(original) + len(proposed) <= _CHAR_DIFF_LIMIT:
        a, b = list(original), list(proposed)
        join = "".join
    else:
        a, b = _tokenize(original), _tokenize(proposed)
        join = "".join

    matcher = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    result: list[tuple[str, str]] = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            result.append(("=", join(a[i1:i2])))
        elif tag == "delete":
            result.append(("-", join(a[i1:i2])))
        elif tag == "insert":
            result.append(("+", join(b[j1:j2])))
        else:                       # replace
            result.append(("-", join(a[i1:i2])))
            result.append(("+", join(b[j1:j2])))

    # Fusionner les segments consécutifs de même nature : moins de spans,
    # donc un rendu nettement plus rapide côté Flutter.
    merged: list[tuple[str, str]] = []
    for kind, chunk in result:
        if not chunk:
            continue
        if merged and merged[-1][0] == kind:
            merged[-1] = (kind, merged[-1][1] + chunk)
        else:
            merged.append((kind, chunk))
    return merged


def diff_stats(segments) -> tuple[int, int]:
    """Retourne (caractères ajoutés, caractères supprimés)."""
    added = sum(len(t) for k, t in segments if k == "+")
    removed = sum(len(t) for k, t in segments if k == "-")
    return added, removed


def build_diff_spans(prefix: str, segments, suffix: str, c,
                     size: int = 16) -> list[ft.TextSpan]:
    """Spans de la couche annotée affichée sous l'éditeur."""
    def style(color=None, bg=None, deco=None):
        return ft.TextStyle(
            size=size, height=1.4, font_family=EDITOR_FONT, letter_spacing=0.2,
            color=color or c(T.L_PRIMARY, T.D_PRIMARY),
            bgcolor=bg, decoration=deco,
        )

    context_style = ft.TextStyle(
        size=size, height=1.4, font_family=EDITOR_FONT, letter_spacing=0.2,
        color=ft.Colors.with_opacity(0.45, c(T.L_PRIMARY, T.D_PRIMARY)),
    )
    removed_style = style(
        color=c(T.L_ERROR, T.D_ERROR),
        bg=ft.Colors.with_opacity(0.14, c(T.L_ERROR, T.D_ERROR)),
        deco=ft.TextDecoration.LINE_THROUGH,
    )
    added_style = style(
        color=c(T.L_SUCCESS, T.D_SUCCESS),
        bg=ft.Colors.with_opacity(0.16, c(T.L_SUCCESS, T.D_SUCCESS)),
    )

    spans = []
    if prefix:
        spans.append(ft.TextSpan(prefix, style=context_style))

    for kind, chunk in segments:
        if kind == "=":
            spans.append(ft.TextSpan(chunk, style=style()))
        elif kind == "-":
            spans.append(ft.TextSpan(chunk, style=removed_style))
        else:
            spans.append(ft.TextSpan(chunk, style=added_style))

    if suffix:
        spans.append(ft.TextSpan(suffix, style=context_style))

    return spans


def build_diff_text(prefix: str, segments, suffix: str, c, size: int = 16):
    """Construit la couche de texte annotée affichée sous l'éditeur."""
    return ft.Text(spans=build_diff_spans(prefix, segments, suffix, c, size),
                   selectable=False)


def build_diff_actions(c, added: int, removed: int, callbacks):
    """Barre d'action flottante : accepter / refuser la proposition."""
    def button(label, hint, on_click, primary=False):
        return ft.Container(
            padding=ft.Padding(14, 8, 14, 8), border_radius=8,
            bgcolor=c(T.L_ACCENT, T.D_ACCENT) if primary else c(T.L_HOVER, T.D_HOVER),
            ink=True, on_click=lambda e: on_click(),
            content=ft.Row(spacing=8, tight=True, controls=[
                ft.Text(label, size=12, font_family=UI_FONT_STRONG,
                        color="#FFFFFF" if primary else c(T.L_SECONDARY, T.D_SECONDARY)),
                ft.Text(hint, size=10, font_family=UI_FONT,
                        color=ft.Colors.with_opacity(
                            0.75, "#FFFFFF" if primary else c(T.L_MUTED, T.D_MUTED))),
            ]),
        )

    summary = ft.Row(spacing=10, tight=True, controls=[
        ft.Text(f"+{added}", size=12, font_family=UI_FONT_STRONG,
                color=c(T.L_SUCCESS, T.D_SUCCESS)),
        ft.Text(f"−{removed}", size=12, font_family=UI_FONT_STRONG,
                color=c(T.L_ERROR, T.D_ERROR)),
        ft.Text("caractères", size=11, font_family=UI_FONT,
                color=c(T.L_MUTED, T.D_MUTED)),
    ])

    bar = ft.Container(
        padding=ft.Padding(14, 8, 14, 8), border_radius=10,
        bgcolor=c(T.L_SURFACE, T.D_SURFACE),
        border=ft.Border.all(1, c(T.L_TB_BORDER, T.D_TB_BORDER)),
        shadow=ft.BoxShadow(spread_radius=0, blur_radius=20,
                            color=ft.Colors.with_opacity(0.14, ft.Colors.BLACK),
                            offset=ft.Offset(0, 6)),
        content=ft.Row(spacing=12, tight=True, controls=[
            summary,
            ft.Container(width=1, height=22, bgcolor=c(T.L_BORDER, T.D_BORDER)),
            button("Refuser", "Échap", callbacks["reject"]),
            button("Accepter", "Tab", callbacks["accept"], primary=True),
        ]),
    )

    return ft.Container(content=bar, alignment=ft.Alignment(0, 0.88))
