"""
views/dialogs/privacy_dialog.py — Confidentialité et données locales.

Un seul écran qui répond aux trois questions qu'un utilisateur se pose :
qu'est-ce qui sort de ma machine, qu'est-ce qui est gardé dessus, et
comment j'efface tout.
"""

import flet as ft

from core.constants import (
    ICON_MD, ICON_SM, UI_FONT, UI_FONT_STRONG, svg_icon,
)
from core.theme import T
from models import user_data


def show_privacy_center(page, c, callbacks):
    """Affiche le centre de confidentialité.

    callbacks attendus :
        privacy_mode() -> bool, toggle_privacy_mode(),
        cloud_consent() -> bool, revoke_consent(),
        updates_enabled() -> bool, toggle_updates(),
        show_policy(), erased()
    """
    def refresh():
        page.pop_dialog()
        show_privacy_center(page, c, callbacks)

    # --- Ce qui sort de la machine ------------------------------------
    consent = callbacks["cloud_consent"]()
    private = callbacks["privacy_mode"]()
    updates = callbacks["updates_enabled"]()

    outbound = [
        _row(c, "shield-trust", "Mode confidentiel",
             "Force le traitement local (Ollama). Aucun texte n'est envoyé en ligne.",
             ft.Switch(value=private, active_color=c(T.L_ACCENT, T.D_ACCENT),
                       on_change=lambda e: (callbacks["toggle_privacy_mode"](),
                                            refresh()))),
        _row(c, "cloud-upload-alt", "Consentement d'envoi à une IA en ligne",
             ("Accordé — les actions IA peuvent transmettre votre texte."
              if consent else
              "Non accordé — Carib demandera votre accord avant tout envoi."),
             ft.TextButton("Retirer", on_click=lambda e: (
                 callbacks["revoke_consent"](), refresh()))
             if consent else ft.Text("—", size=12,
                                     color=c(T.L_MUTED, T.D_MUTED))),
        _row(c, "cloud-download-alt", "Recherche de mise à jour",
             "Une requête par jour à GitHub. Aucune donnée personnelle transmise.",
             ft.Switch(value=updates, active_color=c(T.L_ACCENT, T.D_ACCENT),
                       on_change=lambda e: (callbacks["toggle_updates"](),
                                            refresh()))),
    ]

    # --- Ce qui reste sur la machine ----------------------------------
    entries = user_data.inventory()
    total = sum(size for _label, _path, size in entries)

    if entries:
        stored = [
            ft.Text(f"• {label}  —  {user_data.human_size(size)}", size=11,
                    font_family=UI_FONT, color=c(T.L_TERTIARY, T.D_TERTIARY))
            for label, _path, size in entries
        ]
    else:
        stored = [ft.Text("Aucune donnée enregistrée pour l'instant.", size=11,
                          italic=True, font_family=UI_FONT,
                          color=c(T.L_MUTED, T.D_MUTED))]

    def confirm_erase(e=None):
        page.pop_dialog()
        _confirm_erase(page, c, on_done=callbacks["erased"])

    dlg = ft.AlertDialog(
        title=ft.Text("Confidentialité", size=16, font_family=UI_FONT_STRONG,
                      weight=ft.FontWeight.W_700),
        content=ft.Container(width=560, height=500, content=ft.Column(
            spacing=16, scroll=ft.ScrollMode.AUTO, controls=[
                ft.Text("Carib n'a pas de serveur, ne crée aucun compte et ne "
                        "collecte aucune donnée. Voici les seules exceptions, "
                        "toutes sous votre contrôle.",
                        size=12, color=c(T.L_SECONDARY, T.D_SECONDARY)),

                _section(c, "Ce qui peut sortir de votre ordinateur"),
                *outbound,

                ft.Divider(color=c(T.L_BORDER, T.D_BORDER)),
                _section(c, f"Ce qui est gardé sur votre ordinateur "
                            f"({user_data.human_size(total)})"),
                ft.Text(user_data.data_dir(), size=10, selectable=True,
                        font_family=UI_FONT, color=c(T.L_MUTED, T.D_MUTED)),
                *stored,
                ft.Row(controls=[
                    ft.TextButton("Effacer mes données locales…",
                                  on_click=confirm_erase,
                                  style=ft.ButtonStyle(
                                      color=c(T.L_ERROR, T.D_ERROR))),
                ]),
            ])),
        actions=[
            ft.TextButton("Politique complète",
                          on_click=lambda e: (page.pop_dialog(),
                                              callbacks["show_policy"]())),
            ft.TextButton("Fermer", on_click=lambda e: page.pop_dialog()),
        ])
    page.show_dialog(dlg)


def _confirm_erase(page, c, on_done):
    """Confirmation explicite : l'effacement emporte les documents non
    enregistrés, qui ne vivent nulle part ailleurs."""
    keep_keys = ft.Checkbox(value=True, label="Conserver mes clés API",
                            active_color=c(T.L_ACCENT, T.D_ACCENT))

    def erase(e=None):
        removed, errors = user_data.erase(keep_credentials=bool(keep_keys.value))
        page.pop_dialog()
        on_done(removed, errors)

    page.show_dialog(ft.AlertDialog(
        modal=True,
        title=ft.Text("Effacer mes données locales ?", size=16,
                      font_family=UI_FONT_STRONG, weight=ft.FontWeight.W_700),
        content=ft.Container(width=460, content=ft.Column(
            spacing=12, tight=True, controls=[
                ft.Text("Seront supprimés : la session enregistrée, la liste "
                        "des fichiers récents, les réglages, le journal de "
                        "récupération et le journal technique.",
                        size=13, color=c(T.L_SECONDARY, T.D_SECONDARY)),
                ft.Row(spacing=8, controls=[
                    svg_icon("info", size=ICON_SM,
                             color=c(T.L_WARNING, T.D_WARNING)),
                    ft.Text("Vos fichiers enregistrés sur le disque ne sont "
                            "pas touchés. En revanche, les documents jamais "
                            "enregistrés seront définitivement perdus.",
                            size=11, expand=True, font_family=UI_FONT,
                            color=c(T.L_WARNING, T.D_WARNING)),
                ]),
                keep_keys,
            ])),
        actions=[
            ft.TextButton("Annuler", on_click=lambda e: page.pop_dialog()),
            ft.Button("Effacer", bgcolor=c(T.L_ERROR, T.D_ERROR),
                      color="#FFFFFF", on_click=erase),
        ],
        actions_alignment=ft.MainAxisAlignment.END))


# ---------------------------------------------------------------------------
# Petits composants
# ---------------------------------------------------------------------------

def _section(c, title):
    return ft.Text(title, size=11, font_family=UI_FONT_STRONG,
                   color=c(T.L_TERTIARY, T.D_TERTIARY))


def _row(c, icon, title, subtitle, trailing):
    return ft.Row(
        spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            svg_icon(icon, size=ICON_MD, color=c(T.L_ACCENT, T.D_ACCENT)),
            ft.Column(spacing=1, expand=True, tight=True, controls=[
                ft.Text(title, size=13, color=c(T.L_PRIMARY, T.D_PRIMARY)),
                ft.Text(subtitle, size=10, font_family=UI_FONT,
                        color=c(T.L_MUTED, T.D_MUTED)),
            ]),
            trailing,
        ])
