"""
views/dialogs/info_dialog.py — Informations, crédits et documents légaux.

Les mentions de licence ne sont pas décoratives : la licence gratuite de
Flaticon impose une attribution visible dans l'application, et les licences
Apache 2.0, MPL 2.0, MIT et BSD des composants embarqués imposent que leur
texte soit fourni avec le binaire. `show_legal()` et `show_privacy()` sont
donc ce qui rend la distribution de Carib régulière — pas un supplément.
"""

import os
import sys

import flet as ft

from core.constants import (
    APP_FULL_NAME, APP_URL, APP_VERSION, CONTACT_EMAIL, ICON_SM, ISSUES_URL,
    UI_FONT, UI_FONT_STRONG, resource_path, svg_icon,
)
from core.theme import T
from views.dialogs._common import modern_dialog, primary_button, secondary_button


def _read_doc(filename: str) -> str:
    """Lit un document livré avec l'application."""
    try:
        with open(resource_path(filename), "r", encoding="utf-8") as fh:
            return fh.read()
    except OSError as exc:
        return (f"Le fichier « {filename} » est introuvable.\n\n"
                f"Il est également consultable en ligne :\n{APP_URL}\n\n({exc})")


def show_document(page, c, title: str, filename: str, *, intro: str = ""):
    """Affiche un document texte livré avec l'application, dans un panneau
    défilant. Sert aux mentions légales et à la politique de confidentialité."""
    body = _read_doc(filename)

    controls = []
    if intro:
        controls.append(ft.Text(intro, size=12, font_family=UI_FONT,
                                color=c(T.L_SECONDARY, T.D_SECONDARY)))
        controls.append(ft.Divider(color=c(T.L_BORDER, T.D_BORDER)))
    controls.append(
        ft.Text(body, size=11, selectable=True,
                color=c(T.L_SECONDARY, T.D_SECONDARY)))

    def open_folder(e):
        # `os.startfile` est le seul chemin fiable pour révéler un fichier
        # dans l'explorateur ; il n'existe que sous Windows.
        target = resource_path(filename)
        if sys.platform == "win32" and os.path.isfile(target):
            try:
                os.startfile(os.path.dirname(target))
            except OSError:
                pass

    content = ft.Container(
            width=620, height=460,
            content=ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO,
                              controls=controls),
    )
    page.show_dialog(modern_dialog(
        page, c, title, content, subtitle="Document fourni avec Carib",
        actions=[
            secondary_button("Ouvrir le dossier", c, open_folder, "folder-open"),
            primary_button("Fermer", c, lambda e: page.pop_dialog()),
        ],
    ))


def show_legal(page, c):
    """Mentions légales des composants tiers — obligation de licence."""
    show_document(
        page, c, "Mentions légales", "TIERS.txt",
        intro="Carib incorpore les composants ci-dessous. Chacun reste régi "
              "par sa propre licence, dont le texte intégral est reproduit "
              "dans ce document.")


def show_privacy(page, c):
    """Politique de confidentialité."""
    show_document(
        page, c, "Confidentialité", "CONFIDENTIALITE.md",
        intro="Carib n'a pas de serveur, ne crée aucun compte et ne collecte "
              "rien. Ce document détaille les trois seuls cas où l'application "
              "se connecte à internet.")


def show_eula(page, c):
    """Contrat de licence utilisateur final."""
    show_document(page, c, "Conditions d'utilisation", "EULA.txt")


def show_info(page, c):
    """Affiche la boîte d'informations."""
    content = ft.Container(width=420, content=ft.Column(spacing=8, tight=True, controls=[
            ft.Text(f"{APP_FULL_NAME} — v{APP_VERSION}", size=14, weight=ft.FontWeight.W_500),
            ft.Text("Éditeur de texte moderne, avec IA locale ou en ligne, au choix.",
                    size=13, color=c(T.L_TERTIARY, T.D_TERTIARY)),
            ft.Divider(color=c(T.L_BORDER, T.D_BORDER)),
            _link_row(c, "Site du projet", APP_URL),
            _link_row(c, "Signaler un problème", ISSUES_URL),
            _link_row(c, "Contact", f"mailto:{CONTACT_EMAIL}", shown=CONTACT_EMAIL),
            ft.Divider(color=c(T.L_BORDER, T.D_BORDER)),
            ft.Text("© 2026 Arnaud. Binaire distribué selon les conditions "
                    "d'utilisation ; code source sous PolyForm Noncommercial 1.0.0.",
                    size=10, font_family=UI_FONT, color=c(T.L_MUTED, T.D_MUTED)),
        ]))
    page.show_dialog(modern_dialog(
        page, c, "Informations", content, subtitle="À propos de l’application",
        actions=[
            secondary_button("Conditions", c,
                             lambda e: (page.pop_dialog(), show_eula(page, c))),
            primary_button("Fermer", c, lambda e: page.pop_dialog()),
        ],
    ))


def _link_row(c, label: str, url: str, *, shown: str = "") -> ft.Control:
    shown = shown or url
    return ft.Row(spacing=8, controls=[
        ft.Text(label, size=12, width=150, font_family=UI_FONT,
                color=c(T.L_TERTIARY, T.D_TERTIARY)),
        ft.TextButton(shown, url=url, style=ft.ButtonStyle(padding=0)),
    ])


def show_credits(page, c):
    """Affiche la boîte de crédits.

    L'attribution Flaticon qui figure ici n'est pas facultative : c'est la
    condition de la licence gratuite sous laquelle les icônes de l'interface
    sont utilisées.
    """
    def section(title):
        return ft.Text(title, size=11, font_family=UI_FONT_STRONG,
                       color=c(T.L_TERTIARY, T.D_TERTIARY))

    content = ft.Container(
            width=460,
            content=ft.Column(spacing=10, tight=True, scroll=ft.ScrollMode.AUTO, controls=[
                ft.Text("Développé par Arnaud", size=14, weight=ft.FontWeight.W_500,
                        color=c(T.L_PRIMARY, T.D_PRIMARY)),

                section("Logiciels"),
                ft.Text("• Flet — interface (Apache 2.0)\n"
                        "• Python — Python Software Foundation\n"
                        "• Requests — client HTTP (Apache 2.0)\n"
                        "• pyspellchecker — orthographe hors ligne (MIT)\n"
                        "• pyttsx3 — synthèse vocale (MPL 2.0)",
                        size=12, color=c(T.L_SECONDARY, T.D_SECONDARY)),

                section("Typographie"),
                ft.Text("• Nunito — SIL Open Font License 1.1",
                        size=12, color=c(T.L_SECONDARY, T.D_SECONDARY)),

                # --- Attribution requise par la licence Flaticon ---
                section("Icônes"),
                ft.Row(spacing=8, controls=[
                    svg_icon("heart", size=ICON_SM, color=c(T.L_ACCENT, T.D_ACCENT)),
                    ft.Text("Icônes par", size=12,
                            color=c(T.L_SECONDARY, T.D_SECONDARY)),
                    ft.TextButton("Flaticon", url="https://www.flaticon.com/uicons",
                                  style=ft.ButtonStyle(padding=0)),
                ]),

                section("Intelligence artificielle"),
                ft.Text("Aucun modèle n'est embarqué. Carib appelle, à votre "
                        "demande, OpenAI, Anthropic, Google ou un serveur "
                        "Ollama local.",
                        size=12, color=c(T.L_SECONDARY, T.D_SECONDARY)),

                ft.Divider(color=c(T.L_BORDER, T.D_BORDER)),
                ft.Text("Le détail des licences et les textes intégraux "
                        "figurent dans les mentions légales.",
                        size=10, font_family=UI_FONT,
                        color=c(T.L_MUTED, T.D_MUTED)),
            ]),
    )
    page.show_dialog(modern_dialog(
        page, c, "Crédits", content, subtitle="Logiciels et ressources utilisés",
        actions=[
            secondary_button("Mentions légales", c,
                             lambda e: (page.pop_dialog(), show_legal(page, c))),
            primary_button("Fermer", c, lambda e: page.pop_dialog()),
        ],
    ))
