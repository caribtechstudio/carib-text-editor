"""
views/dialogs/_common.py — Composants partagés entre dialogues.
"""

import flet as ft

from core.constants import (ICON_XS, ICON_SM, ICON_MD, RADIUS_LG, RADIUS_MD,
                            RADIUS_SM, TEXT_CAPTION, TEXT_META, TEXT_TITLE,
                            TEXT_UI, UI_FONT, UI_FONT_STRONG, MOTION_FAST,
                            hover_effect, svg_icon)
from core.theme import T


def dialog_title(page, c, title, subtitle="", on_close=None):
    """En-tête commun : titre, sous-titre et fermeture accessible."""
    labels = [
        ft.Text(title, size=TEXT_TITLE, font_family=UI_FONT_STRONG,
                weight=ft.FontWeight.W_700, color=c(T.L_PRIMARY, T.D_PRIMARY)),
    ]
    if subtitle:
        labels.append(ft.Text(subtitle, size=TEXT_META, font_family=UI_FONT,
                              color=c(T.L_MUTED, T.D_MUTED)))
    return ft.Row(
        vertical_alignment=ft.CrossAxisAlignment.START,
        controls=[
            ft.Column(spacing=2, expand=True, tight=True, controls=labels),
            ft.Container(
                width=30, height=30, border_radius=RADIUS_SM,
                alignment=ft.Alignment(0, 0), ink=True, tooltip="Fermer",
                on_click=on_close or (lambda e: page.pop_dialog()),
                scale=ft.Scale(scale=1.0),
                animate_scale=ft.Animation(MOTION_FAST, ft.AnimationCurve.EASE_OUT),
                animate_opacity=ft.Animation(MOTION_FAST, ft.AnimationCurve.EASE_OUT),
                on_hover=hover_effect(scale=1.06, hover_opacity=0.72),
                content=svg_icon("clear-alt", size=ICON_XS,
                                 color=c(T.L_MUTED, T.D_MUTED)),
            ),
        ],
    )


def section_label(label, c):
    return ft.Text(label.upper(), style=ft.TextStyle(
        size=TEXT_CAPTION, font_family=UI_FONT_STRONG,
        weight=ft.FontWeight.W_700, letter_spacing=0.8,
        color=c(T.L_MUTED, T.D_MUTED)))


def primary_button(label, c, on_click, icon=None):
    controls = []
    if icon:
        controls.append(svg_icon(icon, size=ICON_SM, color="#FFFFFF"))
    controls.append(ft.Text(label, size=TEXT_UI, font_family=UI_FONT_STRONG,
                            color="#FFFFFF"))
    return ft.Container(
        height=36, padding=ft.Padding(16, 0, 16, 0), border_radius=RADIUS_MD,
        alignment=ft.Alignment(0, 0), ink=True, on_click=on_click,
        bgcolor=c(T.L_ACCENT, T.D_ACCENT),
        scale=ft.Scale(scale=1.0),
        animate_scale=ft.Animation(MOTION_FAST, ft.AnimationCurve.EASE_OUT),
        animate_opacity=ft.Animation(MOTION_FAST, ft.AnimationCurve.EASE_OUT),
        on_hover=hover_effect(scale=1.025, hover_opacity=0.90),
        content=ft.Row(spacing=7, tight=True, controls=controls),
    )


def secondary_button(label, c, on_click, icon=None):
    controls = []
    if icon:
        controls.append(svg_icon(icon, size=ICON_SM,
                                 color=c(T.L_SECONDARY, T.D_SECONDARY)))
    controls.append(ft.Text(label, size=TEXT_UI, font_family=UI_FONT,
                            color=c(T.L_SECONDARY, T.D_SECONDARY)))
    return ft.Container(
        height=36, padding=ft.Padding(14, 0, 14, 0), border_radius=RADIUS_MD,
        alignment=ft.Alignment(0, 0), ink=True, on_click=on_click,
        border=ft.Border.all(1, c(T.L_BORDER, T.D_BORDER)),
        bgcolor=ft.Colors.TRANSPARENT,
        scale=ft.Scale(scale=1.0),
        animate=ft.Animation(MOTION_FAST, ft.AnimationCurve.EASE_OUT),
        animate_scale=ft.Animation(MOTION_FAST, ft.AnimationCurve.EASE_OUT),
        on_hover=hover_effect(ft.Colors.TRANSPARENT,
                              c(T.L_HOVER, T.D_HOVER),
                              scale=1.015, hover_opacity=1.0),
        content=ft.Row(spacing=7, tight=True, controls=controls),
    )


def danger_button(label, c, on_click, icon=None):
    controls = []
    if icon:
        controls.append(svg_icon(icon, size=ICON_SM, color="#FFFFFF"))
    controls.append(ft.Text(label, size=TEXT_UI, font_family=UI_FONT_STRONG,
                            color="#FFFFFF"))
    return ft.Container(
        height=36, padding=ft.Padding(16, 0, 16, 0), border_radius=RADIUS_MD,
        alignment=ft.Alignment(0, 0), ink=True, on_click=on_click,
        bgcolor=c(T.L_ERROR, T.D_ERROR),
        scale=ft.Scale(scale=1.0),
        animate_scale=ft.Animation(MOTION_FAST, ft.AnimationCurve.EASE_OUT),
        animate_opacity=ft.Animation(MOTION_FAST, ft.AnimationCurve.EASE_OUT),
        on_hover=hover_effect(scale=1.025, hover_opacity=0.88),
        content=ft.Row(spacing=7, tight=True, controls=controls),
    )


def modern_dialog(page, c, title, content, *, subtitle="", actions=None,
                  modal=False, on_close=None):
    """Fabrique un AlertDialog cohérent sur toutes les vues."""
    return ft.AlertDialog(
        modal=modal,
        title=dialog_title(page, c, title, subtitle, on_close=on_close),
        title_padding=ft.Padding(22, 20, 22, 12),
        content=content,
        content_padding=ft.Padding(22, 0, 22, 8),
        actions=actions or [],
        actions_padding=ft.Padding(22, 12, 22, 18),
        actions_alignment=ft.MainAxisAlignment.END,
        bgcolor=c(T.L_SURFACE, T.D_SURFACE),
        barrier_color=ft.Colors.with_opacity(
            0.62 if c(T.L_BG, T.D_BG) == T.D_BG else 0.38,
            ft.Colors.BLACK),
        shape=ft.RoundedRectangleBorder(radius=RADIUS_LG),
        shadow_color=ft.Colors.with_opacity(0.30, ft.Colors.BLACK),
        elevation=20,
    )


def dlg_btn(label, icon, c, on_click):
    """Bouton stylisé utilisé dans les dialogues."""
    if isinstance(icon, str):
        icon_ctrl = svg_icon(icon, size=ICON_MD, color=c(T.L_ACCENT, T.D_ACCENT))
    else:
        icon_ctrl = ft.Icon(icon, size=22, color=c(T.L_ACCENT, T.D_ACCENT))
    return ft.Container(
        height=44, padding=ft.Padding(14, 0, 14, 0), border_radius=RADIUS_MD, ink=True,
        on_click=on_click,
        border=ft.Border.all(1, c(T.L_BORDER, T.D_BORDER)),
        bgcolor=ft.Colors.TRANSPARENT,
        scale=ft.Scale(scale=1.0),
        animate=ft.Animation(MOTION_FAST, ft.AnimationCurve.EASE_OUT),
        animate_scale=ft.Animation(MOTION_FAST, ft.AnimationCurve.EASE_OUT),
        on_hover=hover_effect(ft.Colors.TRANSPARENT,
                              c(T.L_HOVER, T.D_HOVER),
                              scale=1.01, hover_opacity=1.0),
        content=ft.Row(spacing=12, controls=[
            icon_ctrl,
            ft.Text(label, size=TEXT_UI, font_family=UI_FONT,
                    color=c(T.L_PRIMARY, T.D_PRIMARY)),
        ]),
    )
