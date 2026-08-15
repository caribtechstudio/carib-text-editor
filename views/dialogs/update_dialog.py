"""
views/dialogs/update_dialog.py — Boîtes de dialogue de mise à jour.

Trois écrans, dans l'ordre où l'utilisateur les rencontre :

  1. `show_update_consent` — au premier lancement seulement. Carib demande
     l'autorisation d'interroger GitHub avant de le faire, jamais après.
  2. `show_update_available` — « Maintenant / Plus tard / Ignorer ».
  3. `show_update_progress` — téléchargement, annulable à tout moment.
"""

import flet as ft

from core.constants import (
    APP_NAME, ICON_MD, ICON_SM, UI_FONT, UI_FONT_STRONG, svg_icon,
)
from core.theme import T


def _title(text):
    return ft.Text(text, size=16, font_family=UI_FONT_STRONG,
                   weight=ft.FontWeight.W_700)


def _human_size(num_bytes: int) -> str:
    if not num_bytes:
        return ""
    mega = num_bytes / (1024 * 1024)
    return f"{mega:.0f} Mo" if mega >= 10 else f"{mega:.1f} Mo"


# ---------------------------------------------------------------------------
# 1. Consentement initial
# ---------------------------------------------------------------------------

def show_update_consent(page, c, on_choice):
    """Demande, une seule fois, l'autorisation de vérifier les mises à jour.

    `on_choice(accepte: bool)` est appelé avec la décision. Tant que ce
    dialogue n'a pas reçu de réponse, **aucune connexion n'a lieu**.
    """
    def choose(accepted):
        page.pop_dialog()
        on_choice(accepted)

    page.show_dialog(ft.AlertDialog(
        modal=True,
        title=_title("Vérifier les mises à jour ?"),
        content=ft.Container(width=460, content=ft.Column(
            spacing=12, tight=True, controls=[
                ft.Text(
                    f"{APP_NAME} peut vérifier une fois par jour si une "
                    "nouvelle version est publiée, et vous proposer de "
                    "l'installer.",
                    size=13, color=c(T.L_SECONDARY, T.D_SECONDARY)),
                ft.Row(spacing=8, controls=[
                    svg_icon("shield-check", size=ICON_SM,
                             color=c(T.L_MUTED, T.D_MUTED)),
                    ft.Text(
                        "La requête va chez GitHub et ne transmet aucune "
                        "donnée personnelle. Rien n'est jamais installé sans "
                        "votre accord. Modifiable dans les options.",
                        size=11, expand=True, font_family=UI_FONT,
                        color=c(T.L_MUTED, T.D_MUTED)),
                ]),
            ])),
        actions=[
            ft.TextButton("Non merci", on_click=lambda e: choose(False)),
            ft.Button("Oui, vérifier", bgcolor=c(T.L_ACCENT, T.D_ACCENT),
                      color="#FFFFFF", on_click=lambda e: choose(True)),
        ],
        actions_alignment=ft.MainAxisAlignment.END))


# ---------------------------------------------------------------------------
# 2. Mise à jour disponible
# ---------------------------------------------------------------------------

def show_update_available(page, c, info, *, current_version,
                          on_now, on_later, on_skip):
    """Propose la mise à jour. Aucun téléchargement n'a encore eu lieu."""
    notes = info.short_notes()

    body = [
        ft.Row(spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER,
               controls=[
                   svg_icon("cloud-download-alt", size=ICON_MD,
                            color=c(T.L_ACCENT, T.D_ACCENT)),
                   ft.Column(spacing=1, tight=True, expand=True, controls=[
                       ft.Text(f"{APP_NAME} {info.version}", size=14,
                               font_family=UI_FONT_STRONG,
                               color=c(T.L_PRIMARY, T.D_PRIMARY)),
                       ft.Text(f"Vous utilisez la version {current_version}."
                               + (f"  ·  {_human_size(info.asset_size)}"
                                  if info.asset_size else ""),
                               size=11, font_family=UI_FONT,
                               color=c(T.L_MUTED, T.D_MUTED)),
                   ]),
               ]),
    ]

    if notes:
        body.append(ft.Container(
            padding=ft.Padding(12, 10, 12, 10), border_radius=8,
            bgcolor=c(T.L_HOVER, T.D_HOVER),
            content=ft.Column(spacing=6, tight=True, controls=[
                ft.Text("Nouveautés", size=11, font_family=UI_FONT_STRONG,
                        color=c(T.L_TERTIARY, T.D_TERTIARY)),
                ft.Container(height=170, content=ft.Column(
                    scroll=ft.ScrollMode.AUTO, tight=True, controls=[
                        ft.Text(notes, size=12, selectable=True,
                                color=c(T.L_SECONDARY, T.D_SECONDARY))])),
            ])))

    if not info.can_download:
        # Release publiée sans installeur : on n'invente rien, on renvoie
        # vers la page plutôt que de proposer un bouton qui échouerait.
        body.append(ft.Row(spacing=8, controls=[
            svg_icon("info", size=ICON_SM, color=c(T.L_WARNING, T.D_WARNING)),
            ft.Text("Cette version ne fournit pas d'installeur téléchargeable.",
                    size=11, expand=True, font_family=UI_FONT,
                    color=c(T.L_MUTED, T.D_MUTED)),
        ]))
    elif not info.sha256:
        body.append(ft.Row(spacing=8, controls=[
            svg_icon("info", size=ICON_SM, color=c(T.L_MUTED, T.D_MUTED)),
            ft.Text("Aucune empreinte SHA-256 n'accompagne cette version : "
                    "la vérification se limitera à la taille et à la signature.",
                    size=10, expand=True, font_family=UI_FONT,
                    color=c(T.L_MUTED, T.D_MUTED)),
        ]))

    def act(callback):
        page.pop_dialog()
        callback()

    actions = [
        ft.TextButton("Ignorer cette version", on_click=lambda e: act(on_skip)),
        ft.TextButton("Plus tard", on_click=lambda e: act(on_later)),
    ]
    if info.can_download:
        actions.append(ft.Button(
            "Mettre à jour maintenant", bgcolor=c(T.L_ACCENT, T.D_ACCENT),
            color="#FFFFFF", on_click=lambda e: act(on_now)))
    elif info.page_url:
        actions.append(ft.Button(
            "Ouvrir la page", bgcolor=c(T.L_ACCENT, T.D_ACCENT),
            color="#FFFFFF", url=info.page_url,
            on_click=lambda e: act(on_later)))

    page.show_dialog(ft.AlertDialog(
        title=_title("Une nouvelle version est disponible"),
        content=ft.Container(width=520, content=ft.Column(
            spacing=14, tight=True, controls=body)),
        actions=actions,
        actions_alignment=ft.MainAxisAlignment.END))


# ---------------------------------------------------------------------------
# 3. Téléchargement
# ---------------------------------------------------------------------------

class UpdateProgressDialog:
    """Barre de progression du téléchargement.

    Les mises à jour d'état arrivent depuis un thread de travail : chaque
    méthode publique doit donc être appelée via `page.run_thread`, sauf
    `show()` qui l'est déjà depuis le thread d'interface.
    """

    def __init__(self, page, c, on_cancel):
        self._page = page
        self._c = c
        self._on_cancel = on_cancel
        self._closed = False

        self.bar = ft.ProgressBar(value=0, width=440, height=6,
                                  color=c(T.L_ACCENT, T.D_ACCENT),
                                  bgcolor=c(T.L_HOVER, T.D_HOVER))
        self.label = ft.Text("Connexion…", size=12, font_family=UI_FONT,
                             color=c(T.L_TERTIARY, T.D_TERTIARY))
        self._cancel_btn = ft.TextButton("Annuler", on_click=self._cancel)

        self.dialog = ft.AlertDialog(
            modal=True,
            title=_title("Téléchargement de la mise à jour"),
            content=ft.Container(width=470, content=ft.Column(
                spacing=12, tight=True, controls=[self.bar, self.label])),
            actions=[self._cancel_btn],
            actions_alignment=ft.MainAxisAlignment.END)

    def show(self):
        self._page.show_dialog(self.dialog)

    def _cancel(self, e=None):
        self._cancel_btn.disabled = True
        self.label.value = "Annulation…"
        self._safe_update()
        self._on_cancel()

    def progress(self, received: int, total: int):
        if self._closed:
            return
        if total:
            self.bar.value = min(1.0, received / total)
            self.label.value = (f"{_human_size(received)} sur "
                                f"{_human_size(total)}")
        else:
            self.bar.value = None            # indéterminée
            self.label.value = _human_size(received) or "Téléchargement…"
        self._safe_update()

    def verifying(self):
        if self._closed:
            return
        self.bar.value = None
        self.label.value = "Vérification de l'intégrité du fichier…"
        self._cancel_btn.disabled = True
        self._safe_update()

    def close(self):
        if self._closed:
            return
        self._closed = True
        try:
            self._page.pop_dialog()
        except Exception:
            pass

    def _safe_update(self):
        # Le dialogue peut avoir été fermé entre-temps : un échec de rendu ne
        # doit pas remonter dans le thread de téléchargement.
        try:
            self.dialog.update()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# 4. Prêt à installer
# ---------------------------------------------------------------------------

def show_ready_to_install(page, c, *, has_unsaved, on_install, on_cancel):
    """Dernière confirmation : Carib va se fermer pour laisser la main à
    l'installeur."""
    warning = []
    if has_unsaved:
        warning = [ft.Row(spacing=8, controls=[
            svg_icon("info", size=ICON_SM, color=c(T.L_WARNING, T.D_WARNING)),
            ft.Text("Des documents ne sont pas enregistrés. Ils seront "
                    "restaurés au prochain démarrage, mais mieux vaut les "
                    "enregistrer avant.",
                    size=11, expand=True, font_family=UI_FONT,
                    color=c(T.L_WARNING, T.D_WARNING)),
        ])]

    def act(callback):
        page.pop_dialog()
        callback()

    page.show_dialog(ft.AlertDialog(
        modal=True,
        title=_title("Installer maintenant ?"),
        content=ft.Container(width=460, content=ft.Column(
            spacing=12, tight=True, controls=[
                ft.Text(f"Le fichier a été téléchargé et vérifié.\n\n"
                        f"{APP_NAME} va se fermer et laisser l'installeur "
                        "prendre le relais. Votre session sera rouverte "
                        "telle quelle après la mise à jour.",
                        size=13, color=c(T.L_SECONDARY, T.D_SECONDARY)),
                *warning,
            ])),
        actions=[
            ft.TextButton("Plus tard", on_click=lambda e: act(on_cancel)),
            ft.Button("Fermer et installer", bgcolor=c(T.L_ACCENT, T.D_ACCENT),
                      color="#FFFFFF", on_click=lambda e: act(on_install)),
        ],
        actions_alignment=ft.MainAxisAlignment.END))
