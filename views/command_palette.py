"""
views/command_palette.py — Palette de commandes (Ctrl+Maj+P).

Une seule liste filtrable qui expose toutes les actions de Glyph. C'est le
meilleur rapport valeur/effort en matière de découvrabilité : l'utilisateur
n'a plus à mémoriser huit boutons ni à fouiller les menus, et les
fonctionnalités rarement visibles (modes, options IA, remplacement)
deviennent atteignables au clavier.
"""

import flet as ft

from core.constants import ICON_SM, svg_icon, UI_FONT, UI_FONT, UI_FONT_STRONG
from core.theme import T

MAX_VISIBLE = 9


class Command:
    """Une action exposée dans la palette."""

    __slots__ = ("id", "label", "group", "hint", "action", "icon")

    def __init__(self, cid, label, action, group="", hint="", icon="bolt"):
        self.id = cid
        self.label = label
        self.action = action
        self.group = group
        self.hint = hint
        self.icon = icon

    @property
    def haystack(self) -> str:
        return f"{self.label} {self.group} {self.hint}".lower()


def fuzzy_filter(commands, query: str):
    """Filtre par sous-séquence, comme VS Code : « rmp » trouve « Remplacer »."""
    query = (query or "").strip().lower()
    if not query:
        return list(commands)

    scored = []
    for cmd in commands:
        target = cmd.haystack
        # Correspondance exacte d'abord : elle prime toujours.
        exact = target.find(query)
        if exact != -1:
            scored.append((0, exact, cmd))
            continue
        # Sinon, sous-séquence : tous les caractères dans l'ordre.
        pos = 0
        spread = 0
        ok = True
        for ch in query:
            found = target.find(ch, pos)
            if found == -1:
                ok = False
                break
            spread += found - pos
            pos = found + 1
        if ok:
            scored.append((1, spread, cmd))

    scored.sort(key=lambda item: (item[0], item[1], item[2].label))
    return [cmd for _, _, cmd in scored]


def build_command_palette(state, c, commands, callbacks):
    """Construit la palette.

    callbacks attendus : on_query_change, on_close, run(command)
    """
    results = fuzzy_filter(commands, state.palette_query)[:MAX_VISIBLE]
    selected = max(0, min(state.palette_selected, len(results) - 1)) if results else 0

    field = ft.TextField(
        value=state.palette_query,
        hint_text="Rechercher une commande…",
        hint_style=ft.TextStyle(size=14, font_family=UI_FONT,
                                color=c(T.L_MUTED, T.D_MUTED), italic=True),
        text_size=14,
        text_style=ft.TextStyle(size=14, font_family=UI_FONT,
                                color=c(T.L_PRIMARY, T.D_PRIMARY)),
        border=ft.InputBorder.NONE,
        content_padding=ft.Padding(4, 0, 4, 0),
        cursor_color=c(T.L_ACCENT, T.D_ACCENT),
        cursor_height=18, cursor_width=1.5,
        bgcolor=ft.Colors.TRANSPARENT,
        focused_bgcolor=ft.Colors.TRANSPARENT,
        hover_color=ft.Colors.TRANSPARENT,
        expand=True, autofocus=True,
        on_change=callbacks["on_query_change"],
        on_submit=lambda e: (callbacks["run"](results[selected])
                             if results else callbacks["on_close"]()),
    )

    def row(cmd, active):
        return ft.Container(
            padding=ft.Padding(12, 9, 12, 9), border_radius=6,
            bgcolor=c(T.L_SELECTED, T.D_SELECTED) if active else ft.Colors.TRANSPARENT,
            ink=True, on_click=lambda e, k=cmd: callbacks["run"](k),
            content=ft.Row(spacing=10, controls=[
                svg_icon(cmd.icon, size=ICON_SM,
                         color=c(T.L_ACCENT, T.D_ACCENT) if active
                         else c(T.L_TERTIARY, T.D_TERTIARY)),
                ft.Column(spacing=0, expand=True, controls=[
                    ft.Text(cmd.label, size=13,
                            font_family=UI_FONT_STRONG if active else UI_FONT,
                            color=c(T.L_PRIMARY, T.D_PRIMARY),
                            overflow=ft.TextOverflow.ELLIPSIS),
                    *([ft.Text(cmd.group, size=10, font_family=UI_FONT,
                               color=c(T.L_MUTED, T.D_MUTED))] if cmd.group else []),
                ]),
                *([ft.Text(cmd.hint, size=11, font_family=UI_FONT,
                           color=c(T.L_MUTED, T.D_MUTED))] if cmd.hint else []),
            ]),
        )

    if results:
        body = ft.Column(spacing=1, tight=True,
                         controls=[row(cmd, i == selected)
                                   for i, cmd in enumerate(results)])
    else:
        body = ft.Container(
            padding=ft.Padding(12, 16, 12, 16),
            content=ft.Text("Aucune commande correspondante.", size=12,
                            italic=True, font_family=UI_FONT,
                            color=c(T.L_MUTED, T.D_MUTED)),
        )

    inner = ft.Container(
        padding=ft.Padding(10, 10, 10, 10), border_radius=12,
        bgcolor=c(T.L_SURFACE, T.D_SURFACE),
        border=ft.Border.all(1, c(T.L_TB_BORDER, T.D_TB_BORDER)),
        shadow=ft.BoxShadow(spread_radius=0, blur_radius=28,
                            color=ft.Colors.with_opacity(0.20, ft.Colors.BLACK),
                            offset=ft.Offset(0, 10)),
        content=ft.Column(spacing=8, tight=True, controls=[
            ft.Row(spacing=8, controls=[
                svg_icon("search", size=ICON_SM, color=c(T.L_MUTED, T.D_MUTED)),
                field,
                ft.IconButton(
                    icon=ft.Icons.CLOSE, icon_size=ICON_SM,
                    icon_color=c(T.L_TERTIARY, T.D_TERTIARY),
                    tooltip="Fermer  Échap",
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=4), padding=2),
                    on_click=lambda e: callbacks["on_close"]()),
            ]),
            ft.Container(height=1, bgcolor=c(T.L_BORDER, T.D_BORDER)),
            body,
        ]),
    )

    return ft.Container(
        content=ft.Container(content=inner, width=560),
        alignment=ft.Alignment(0, -0.6),
        padding=ft.Padding(40, 0, 40, 0),
    )
