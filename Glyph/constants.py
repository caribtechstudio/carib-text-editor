"""
constants.py — Constantes globales de l'application Glyph.
"""

import os
import sys

import flet as ft

APP_NAME = "Glyph"
APP_VERSION = "0.13.1"

MODE_TEXT = "text"
MODE_CALC = "calc"
MODE_READ = "read"

# ---------------------------------------------------------------------------
# Typographie
#
# Deux familles, et la frontière entre elles est nette :
#
#   * `EDITOR_FONT` — le texte que l'utilisateur écrit, et toutes les couches
#     qui doivent s'aligner dessus au pixel près (coloration, surlignage de
#     recherche, diff, texte fantôme, gouttière). Un document se lit en
#     Regular : c'est ce que font VS Code, Notion et Google Docs.
#   * `UI_FONT` — l'application autour : barre latérale, onglets, barre
#     d'état, menus, dialogues. Google Workspace y emploie un Medium ; Nunito
#     ne fournissant pas de Medium, le SemiBold en tient lieu. Le contraste
#     avec le document s'en trouve renforcé, ce qui est précisément le but.
# ---------------------------------------------------------------------------
#: Ces trois noms servent aussi de **clés d'enregistrement** des fontes
#: (`AppController._configure_page`) : une vue ne peut donc pas réclamer une
#: famille qui n'aurait pas été chargée.
EDITOR_FONT = "Nunito"
UI_FONT = "Nunito SemiBold"
UI_FONT_STRONG = "Nunito Bold"

# ---------------------------------------------------------------------------
# Échelle d'icônes — alignée sur Material / Google Workspace
#
# Google utilise des icônes de 24 dp dans une cible cliquable de 40 dp
# (8 dp de marge de chaque côté). On reprend exactement cette métrique
# pour que la barre d'outils ait la même densité visuelle que Google Docs.
# ---------------------------------------------------------------------------
ICON_XS = 16   # chevrons, indicateurs inline
ICON_SM = 20   # icônes secondaires (barre de recherche, listes)
ICON_MD = 24   # standard — barre d'outils et sidebar
ICON_LG = 28   # accents (logo, en-têtes de dialogue)

ICON_BTN_PADDING = 8          # ICON_MD + 2*8 = 40 → cible Google
ICON_BTN_SIZE = ICON_MD + ICON_BTN_PADDING * 2   # 40

# Hauteur de la barre d'outils : bouton (40) + padding vertical (2*4)
# + marge du conteneur (2*10)
TOOLBAR_HEIGHT = ICON_BTN_SIZE + 8 + 20   # 68


def resource_path(rel: str) -> str:
    """Résout un chemin relatif vers les ressources (compatible PyInstaller)."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


def svg_icon(name: str, size: int = ICON_MD, color=None) -> ft.Image:
    """Crée une icône SVG depuis ressource/icon/."""
    return ft.Image(src=f"icon/{name}.svg", width=size, height=size, color=color)


def svg_icon_btn(name: str, size: int = ICON_MD, color=None, tooltip=None,
                 on_click=None, padding: int = ICON_BTN_PADDING,
                 hover_color=None) -> ft.Container:
    """Bouton cliquable avec icône SVG (remplace ft.IconButton)."""
    return ft.Container(
        width=size + padding * 2, height=size + padding * 2,
        border_radius=8, alignment=ft.Alignment(0, 0),
        ink=True, tooltip=tooltip, on_click=on_click,
        content=svg_icon(name, size=size, color=color),
    )
