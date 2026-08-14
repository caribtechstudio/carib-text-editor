"""
views/dialogs/_common.py — Composants partagés entre dialogues.
"""

import flet as ft

from core.constants import (ICON_XS, ICON_SM, ICON_MD, svg_icon)
from core.theme import T


def dlg_btn(label, icon, c, on_click):
    """Bouton stylisé utilisé dans les dialogues."""
    if isinstance(icon, str):
        icon_ctrl = svg_icon(icon, size=ICON_MD, color=c(T.L_ACCENT, T.D_ACCENT))
    else:
        icon_ctrl = ft.Icon(icon, size=22, color=c(T.L_ACCENT, T.D_ACCENT))
    return ft.Container(
        padding=ft.Padding(16, 12, 16, 12), border_radius=8, ink=True,
        on_click=on_click,
        border=ft.Border.all(1, c(T.L_BORDER, T.D_BORDER)),
        content=ft.Row(spacing=12, controls=[
            icon_ctrl,
            ft.Text(label, size=14, color=c(T.L_PRIMARY, T.D_PRIMARY)),
        ]),
    )
