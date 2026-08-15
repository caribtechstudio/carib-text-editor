"""Sélecteur d’émojis compact, filtrable et organisé par catégories."""

import flet as ft

from core.constants import MOTION_FAST, TEXT_META, UI_FONT, hover_effect
from core.my_emoji import EMOJI_CATEGORIES, EMOJI_DICT
from core.theme import T
from views.dialogs._common import modern_dialog, primary_button, section_label


_CATEGORY_ICONS = ("😊", "👋", "🌿", "🍎", "💡", "✅", "🏳️", "🔣")


def show_emoji_picker(page, c, callbacks):
    search = ft.TextField(
        hint_text="Rechercher un émoji…", prefix_icon=ft.Icons.SEARCH,
        border_radius=11, text_size=13, height=40, dense=True,
        border_color=c(T.L_BORDER, T.D_BORDER),
        focused_border_color=c(T.L_ACCENT, T.D_ACCENT),
        bgcolor=c(T.L_EDITOR, T.D_EDITOR),
        content_padding=ft.Padding(10, 0, 10, 0),
    )
    result_grid = ft.GridView(max_extent=46, spacing=2, run_spacing=2,
                              padding=4, expand=True, visible=False)

    cat_list = list(EMOJI_CATEGORIES.items())
    cat_grids = []
    cat_buttons = ft.Row(spacing=4, controls=[])
    current_title = section_label(cat_list[0][0] if cat_list else "Émojis", c)
    count = ft.Text(f"{len(EMOJI_DICT)} émojis", size=TEXT_META,
                    font_family=UI_FONT, color=c(T.L_MUTED, T.D_MUTED))

    def insert(char):
        page.pop_dialog()
        callbacks["insert_emoji"](char)

    def emoji_btn(char, code):
        return ft.Container(
            width=44, height=44, border_radius=10, alignment=ft.Alignment(0, 0),
            ink=True, tooltip=code, on_click=lambda e, ch=char: insert(ch),
            bgcolor=ft.Colors.TRANSPARENT,
            scale=ft.Scale(scale=1.0),
            animate=ft.Animation(MOTION_FAST, ft.AnimationCurve.EASE_OUT),
            animate_scale=ft.Animation(MOTION_FAST, ft.AnimationCurve.EASE_OUT),
            on_hover=hover_effect(ft.Colors.TRANSPARENT,
                                  c(T.L_ACCENT_LT, T.D_ACCENT_LT),
                                  scale=1.06, hover_opacity=1.0),
            content=ft.Text(char, size=23, text_align=ft.TextAlign.CENTER),
        )

    def switch_category(idx):
        for i, grid in enumerate(cat_grids):
            grid.visible = i == idx
        for i, button in enumerate(cat_buttons.controls):
            button.bgcolor = (c(T.L_ACCENT_LT, T.D_ACCENT_LT) if i == idx
                              else ft.Colors.TRANSPARENT)
            button.border = (ft.Border.all(1, c(T.L_ACCENT, T.D_ACCENT))
                             if i == idx else None)
        current_title.value = cat_list[idx][0].upper()
        count.value = f"{len(cat_list[idx][1])} émojis"
        page.update()

    for idx, (cat_name, cat_dict) in enumerate(cat_list):
        grid = ft.GridView(expand=True, max_extent=46, spacing=2, run_spacing=2,
                           padding=4, visible=idx == 0)
        grid.controls.extend(emoji_btn(char, code)
                             for code, char in cat_dict.items())
        cat_grids.append(grid)
        cat_buttons.controls.append(ft.Container(
            width=38, height=34, border_radius=10, ink=True,
            alignment=ft.Alignment(0, 0), tooltip=cat_name,
            bgcolor=c(T.L_ACCENT_LT, T.D_ACCENT_LT) if idx == 0
            else ft.Colors.TRANSPARENT,
            border=ft.Border.all(1, c(T.L_ACCENT, T.D_ACCENT)) if idx == 0
            else None,
            on_click=lambda e, i=idx: switch_category(i),
            scale=ft.Scale(scale=1.0),
            animate_scale=ft.Animation(MOTION_FAST, ft.AnimationCurve.EASE_OUT),
            animate_opacity=ft.Animation(MOTION_FAST, ft.AnimationCurve.EASE_OUT),
            on_hover=hover_effect(scale=1.07, hover_opacity=0.78),
            content=ft.Text(_CATEGORY_ICONS[idx % len(_CATEGORY_ICONS)], size=17),
        ))

    grids = ft.Stack(expand=True, controls=cat_grids)

    def on_search(e):
        query = (e.control.value or "").strip().lower()
        searching = bool(query)
        result_grid.visible = searching
        cat_buttons.visible = not searching
        grids.visible = not searching
        result_grid.controls.clear()
        if searching:
            matches = [(code, char) for code, char in EMOJI_DICT.items()
                       if query in code.strip(":").lower()]
            result_grid.controls.extend(emoji_btn(char, code)
                                        for code, char in matches)
            current_title.value = "RÉSULTATS"
            count.value = f"{len(matches)} résultat(s)"
        else:
            current_title.value = cat_list[0][0].upper() if cat_list else "ÉMOJIS"
            count.value = f"{len(cat_list[0][1]) if cat_list else 0} émojis"
        page.update()

    search.on_change = on_search
    content = ft.Container(
        width=496, height=420,
        content=ft.Column(spacing=10, controls=[
            search,
            cat_buttons,
            ft.Row(spacing=8, controls=[
                current_title,
                ft.Container(height=1, expand=True,
                             bgcolor=c(T.L_BORDER, T.D_BORDER)),
            ]),
            result_grid,
            grids,
        ]),
    )
    dlg = modern_dialog(
        page, c, "Émojis", content,
        actions=[count, primary_button("Fermer", c, lambda e: page.pop_dialog())],
    )
    dlg.actions_alignment = ft.MainAxisAlignment.SPACE_BETWEEN
    page.show_dialog(dlg)
