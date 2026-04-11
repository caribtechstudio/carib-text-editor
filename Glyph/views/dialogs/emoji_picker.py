"""
views/dialogs/emoji_picker.py — Sélecteur visuel d'émojis.
"""

import flet as ft

from theme import T
from my_emoji import EMOJI_DICT, EMOJI_CATEGORIES


def show_emoji_picker(page, c, callbacks):
    """
    Affiche le sélecteur d'émojis.

    callbacks attendus : insert_emoji(char)
    """
    search = ft.TextField(
        hint_text="Rechercher…", prefix_icon=ft.Icons.SEARCH,
        border_radius=8, text_size=14, height=44,
        border_color=c(T.L_BORDER, T.D_BORDER),
        focused_border_color=c(T.L_ACCENT, T.D_ACCENT),
    )
    result_grid = ft.GridView(max_extent=52, spacing=4, run_spacing=4, padding=8,
                              expand=True, visible=False)

    cat_list = list(EMOJI_CATEGORIES.items())
    cat_grids = []
    cat_buttons_row = ft.Row(spacing=4, scroll=ft.ScrollMode.AUTO, controls=[])
    cat_buttons_wrap = ft.Container(content=cat_buttons_row,
                                    margin=ft.Margin(0, 0, 0, 8))

    def make_emoji_btn(char, code):
        return ft.Container(
            width=48, height=48, border_radius=8, alignment=ft.Alignment(0, 0),
            ink=True, tooltip=code,
            on_click=lambda e, ch=char: _do_insert(ch),
            content=ft.Text(char, size=24),
        )

    for i, (cat_name, cat_dict) in enumerate(cat_list):
        short = cat_name.split("&")[0].strip().split(" ")[0]
        grid = ft.GridView(expand=True, max_extent=52, spacing=4, run_spacing=4,
                           padding=8, visible=(i == 0))
        for code, char in cat_dict.items():
            grid.controls.append(make_emoji_btn(char, code))
        cat_grids.append(grid)
        cat_buttons_row.controls.append(ft.Container(
            padding=ft.Padding(10, 6, 10, 6), border_radius=6, ink=True,
            bgcolor=c(T.L_SELECTED, T.D_SELECTED) if i == 0 else ft.Colors.TRANSPARENT,
            on_click=lambda e, idx=i: _switch_cat(idx),
            content=ft.Text(short, size=12, weight=ft.FontWeight.W_500,
                            color=c(T.L_ACCENT, T.D_ACCENT) if i == 0
                            else c(T.L_TERTIARY, T.D_TERTIARY)),
        ))

    grids_stack = ft.Stack(expand=True, controls=cat_grids)

    def _switch_cat(idx):
        for i, g in enumerate(cat_grids):
            g.visible = (i == idx)
        for i, btn in enumerate(cat_buttons_row.controls):
            btn.bgcolor = c(T.L_SELECTED, T.D_SELECTED) if i == idx else ft.Colors.TRANSPARENT
            btn.content.color = c(T.L_ACCENT, T.D_ACCENT) if i == idx \
                else c(T.L_TERTIARY, T.D_TERTIARY)
        page.update()

    def on_search(e):
        q = (e.control.value or "").strip().lower()
        if not q:
            result_grid.visible = False
            cat_buttons_row.visible = True
            grids_stack.visible = True
            page.update()
            return
        result_grid.visible = True
        cat_buttons_row.visible = False
        grids_stack.visible = False
        result_grid.controls.clear()
        for code, char in EMOJI_DICT.items():
            if q in code.strip(":"):
                result_grid.controls.append(make_emoji_btn(char, code))
        page.update()

    search.on_change = on_search

    def _do_insert(ch):
        page.pop_dialog()
        callbacks["insert_emoji"](ch)

    dlg = ft.AlertDialog(
        title=ft.Text("Émojis", size=16, font_family="Nunito SemiBold", weight=ft.FontWeight.W_600),
        content=ft.Container(
            width=520, height=420,
            content=ft.Column(spacing=10, controls=[
                search, cat_buttons_wrap, result_grid, grids_stack,
            ]),
        ),
        actions=[
            ft.Text(f"{len(EMOJI_DICT)} émojis", size=12, color=c(T.L_MUTED, T.D_MUTED)),
            ft.TextButton("Fermer", on_click=lambda e: page.pop_dialog()),
        ],
    )
    page.show_dialog(dlg)
