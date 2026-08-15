"""Fenêtre de préférences, structurée comme un véritable panneau de réglages."""

import flet as ft

from core.constants import (ICON_MD, ICON_SM, MODE_CALC, MODE_READ, MODE_TEXT,
                            RADIUS_MD, TEXT_META, UI_FONT, UI_FONT_STRONG,
                            MOTION_FAST, hover_effect, svg_icon)
from core.theme import T
from views.dialogs._common import modern_dialog, primary_button, section_label


def show_options(page, c, dark, callbacks):
    current_mode = callbacks.get("current_mode", lambda: MODE_TEXT)()

    def choose_mode(mode):
        page.pop_dialog()
        callbacks["set_mode"](mode)

    def mode_card(label, icon, mode):
        active = current_mode == mode
        idle_bg = c(T.L_SURFACE, T.D_SURFACE) if active else ft.Colors.TRANSPARENT
        hover_bg = idle_bg if active else c(T.L_HOVER, T.D_HOVER)
        return ft.Container(
            expand=True, height=64, border_radius=RADIUS_MD, ink=True,
            alignment=ft.Alignment(0, 0),
            bgcolor=idle_bg,
            border=ft.Border.all(1, c(T.L_ACCENT, T.D_ACCENT)
                                 if active else ft.Colors.TRANSPARENT),
            on_click=lambda e: choose_mode(mode),
            scale=ft.Scale(scale=1.0),
            animate=ft.Animation(MOTION_FAST, ft.AnimationCurve.EASE_OUT),
            animate_scale=ft.Animation(MOTION_FAST, ft.AnimationCurve.EASE_OUT),
            on_hover=hover_effect(idle_bg, hover_bg, scale=1.015,
                                  hover_opacity=1.0),
            content=ft.Column(
                spacing=5, tight=True,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    svg_icon(icon, size=ICON_MD,
                             color=c(T.L_ACCENT, T.D_ACCENT) if active
                             else c(T.L_SECONDARY, T.D_SECONDARY)),
                    ft.Text(label, size=12.5, font_family=UI_FONT_STRONG,
                            color=c(T.L_ACCENT, T.D_ACCENT) if active
                            else c(T.L_SECONDARY, T.D_SECONDARY)),
                ],
            ),
        )

    def setting_row(label, icon, value, on_change, subtitle=""):
        labels = [ft.Text(label, size=13.5, font_family=UI_FONT,
                          color=c(T.L_PRIMARY, T.D_PRIMARY))]
        if subtitle:
            labels.append(ft.Text(subtitle, size=TEXT_META, font_family=UI_FONT,
                                  color=c(T.L_MUTED, T.D_MUTED)))
        return ft.Container(
            height=58 if subtitle else 48,
            border=ft.Border.only(bottom=ft.BorderSide(
                1, c(T.L_BORDER, T.D_BORDER))),
            content=ft.Row(spacing=12, controls=[
                svg_icon(icon, size=ICON_MD,
                         color=c(T.L_SECONDARY, T.D_SECONDARY)),
                ft.Column(spacing=1, tight=True, expand=True, controls=labels),
                ft.Switch(
                    value=value, active_color="#FFFFFF",
                    active_track_color=c(T.L_ACCENT, T.D_ACCENT),
                    inactive_thumb_color=c(T.L_SURFACE, T.D_PRIMARY),
                    inactive_track_color=c(T.L_BORDER, T.D_BORDER),
                    track_outline_width=0, on_change=on_change, width=42,
                ),
            ]),
        )

    def compact_action(label, icon, callback):
        return ft.Container(
            expand=True, height=42, border_radius=RADIUS_MD, ink=True,
            border=ft.Border.all(1, c(T.L_BORDER, T.D_BORDER)),
            on_click=lambda e: (page.pop_dialog(), callback()),
            bgcolor=ft.Colors.TRANSPARENT,
            scale=ft.Scale(scale=1.0),
            animate=ft.Animation(MOTION_FAST, ft.AnimationCurve.EASE_OUT),
            animate_scale=ft.Animation(MOTION_FAST, ft.AnimationCurve.EASE_OUT),
            on_hover=hover_effect(ft.Colors.TRANSPARENT,
                                  c(T.L_HOVER, T.D_HOVER),
                                  scale=1.015, hover_opacity=1.0),
            content=ft.Row(spacing=8, alignment=ft.MainAxisAlignment.CENTER,
                           controls=[
                               svg_icon(icon, size=ICON_SM,
                                        color=c(T.L_TERTIARY, T.D_TERTIARY)),
                               ft.Text(label, size=12, font_family=UI_FONT,
                                       color=c(T.L_SECONDARY, T.D_SECONDARY)),
                           ]),
        )

    model_label = callbacks.get("current_ai", lambda: "Configurer le fournisseur")()
    model_card = ft.Container(
        height=58, padding=ft.Padding(14, 0, 12, 0), border_radius=12,
        ink=True, bgcolor=c(T.L_ACCENT_LT, T.D_ACCENT_LT),
        on_click=lambda e: (page.pop_dialog(), callbacks["show_model_manager"]()),
        scale=ft.Scale(scale=1.0),
        animate_scale=ft.Animation(MOTION_FAST, ft.AnimationCurve.EASE_OUT),
        animate_opacity=ft.Animation(MOTION_FAST, ft.AnimationCurve.EASE_OUT),
        on_hover=hover_effect(scale=1.012, hover_opacity=0.90),
        content=ft.Row(spacing=12, controls=[
            svg_icon("user-robot", size=ICON_MD, color=c(T.L_ACCENT, T.D_ACCENT)),
            ft.Column(spacing=1, tight=True, expand=True, controls=[
                ft.Text("Modèles IA", size=13.5, font_family=UI_FONT_STRONG,
                        color=c(T.L_PRIMARY, T.D_PRIMARY)),
                ft.Text(model_label, size=TEXT_META, font_family=UI_FONT,
                        color=c(T.L_SECONDARY, T.D_SECONDARY),
                        overflow=ft.TextOverflow.ELLIPSIS),
            ]),
            svg_icon("angle-circle-right", size=ICON_SM,
                     color=c(T.L_ACCENT, T.D_ACCENT)),
        ]),
    )

    content = ft.Container(
        width=428,
        content=ft.Column(spacing=10, tight=True, controls=[
            section_label("Mode", c),
            ft.Container(
                padding=4, border_radius=12,
                bgcolor=c(T.L_EDITOR, T.D_EDITOR),
                border=ft.Border.all(1, c(T.L_BORDER, T.D_BORDER)),
                content=ft.Row(spacing=4, controls=[
                    mode_card("Texte", "pen-field", MODE_TEXT),
                    mode_card("Calcul", "calculator-simple", MODE_CALC),
                    mode_card("Lecture", "book-open-cover", MODE_READ),
                ]),
            ),
            ft.Container(height=4),
            section_label("Général", c),
            setting_row(
                "Thème sombre", "moon-stars" if dark() else "brightness",
                dark(), lambda e: (page.pop_dialog(), callbacks["toggle_theme"]())),
            setting_row(
                "Sauvegarde automatique", "disk", callbacks["is_auto_save"](),
                lambda e: callbacks["toggle_auto_save"]()),
            setting_row(
                "Autocomplétion", "text", callbacks["is_autocomplete"](),
                lambda e: callbacks["toggle_autocomplete"](),
                "Suggestions de mots et prédiction IA"),
            ft.Container(height=4),
            model_card,
            ft.Row(spacing=8, controls=[
                compact_action("Confidentialité", "shield-trust", callbacks["show_privacy"]),
                compact_action("Mise à jour", "cloud-download-alt", callbacks["check_updates"]),
            ]),
            ft.Row(spacing=8, controls=[
                compact_action("Aide", "interrogation", callbacks["show_help"]),
                compact_action("Informations", "info", callbacks["show_info"]),
                compact_action("Crédits", "heart", callbacks["show_credits"]),
            ]),
        ]),
    )

    page.show_dialog(modern_dialog(
        page, c, "Options", content, subtitle="Préférences de l’éditeur",
        actions=[primary_button("Terminé", c, lambda e: page.pop_dialog())],
    ))
