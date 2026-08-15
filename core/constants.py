"""
constants.py — Constantes globales de l'application Carib.
"""

import os
import sys

import flet as ft

#: Nom court, celui de la marque. C'est lui qui apparaît partout où la place
#: manque : logo de la barre latérale, notifications, zone de notification.
APP_NAME = "Carib"

#: Nom complet du produit — titre de fenêtre, boîte d'informations,
#: installeur, documents légaux. « Text Editor » est purement descriptif et
#: ne porte aucun droit : seul `APP_NAME` constitue le signe distinctif.
APP_FULL_NAME = "Carib Text Editor"

#: **Source de vérité unique du numéro de version.**
#:
#: `tools/sync_version.py` recopie cette valeur dans `pyproject.toml` et
#: `installer/setup.iss` ; `build.bat` l'appelle avant chaque compilation.
#: Ne modifiez la version qu'ici.
APP_VERSION = "0.15.0"

# ---------------------------------------------------------------------------
# Distribution
# ---------------------------------------------------------------------------
#: Dépôt GitHub interrogé pour les mises à jour, au format « owner/repo ».
#: Vide = recherche de mise à jour désactivée (voir models/updater.py).
GITHUB_REPO = "caribtechstudio/carib-text-editor"

APP_URL = f"https://github.com/{GITHUB_REPO}"
RELEASES_URL = f"{APP_URL}/releases"
ISSUES_URL = f"{APP_URL}/issues"

#: Adresse de contact affichée dans l'application et les documents légaux.
CONTACT_EMAIL = "contact@caribtechstudio.com"

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
ICON_XS = 14   # chevrons, indicateurs inline
ICON_SM = 16   # icônes secondaires (barre de recherche, listes)
ICON_MD = 18   # standard — barre d'outils et sidebar
ICON_LG = 24   # accents (logo, en-têtes de dialogue)

ICON_BTN_PADDING = 8          # 18 + 2*8 = 34 px, cible visuelle moderne
ICON_BTN_SIZE = ICON_MD + ICON_BTN_PADDING * 2   # 34

# Hauteur de la barre d'outils : bouton (40) + padding vertical (2*4)
# + marge du conteneur (2*10)
TOOLBAR_HEIGHT = ICON_BTN_SIZE + 12 + 12   # 58

MOTION_FAST = 120
MOTION_NORMAL = 180
MOTION_PANEL = 260

# Échelle commune de l'interface. Les noms rendent les choix explicites dans
# les vues et évitent la dérive progressive des tailles entre dialogues.
TEXT_CAPTION = 10.5
TEXT_META = 11.5
TEXT_UI = 13
TEXT_TITLE = 18
RADIUS_SM = 8
RADIUS_MD = 10
RADIUS_LG = 18


def app_root() -> str:
    """Racine des fichiers livrés avec l'application.

    Empaquetée, PyInstaller place les données dans `_internal/`, dont
    `sys._MEIPASS` donne le chemin. En développement, c'est la racine du
    dépôt — soit le **parent** du dossier `core/` qui contient ce fichier.
    Sans ce `dirname` supplémentaire, tous les chemins de ressources
    désignaient `core/ressource/`, qui n'existe pas : le dictionnaire
    d'orthographe était introuvable dès qu'on lançait Carib depuis les
    sources.
    """
    frozen = getattr(sys, "_MEIPASS", None)
    if frozen:
        return frozen
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resource_path(rel: str) -> str:
    """Résout un chemin relatif vers les ressources (compatible PyInstaller)."""
    return os.path.join(app_root(), rel)


def svg_icon(name: str, size: int = ICON_MD, color=None) -> ft.Image:
    """Crée une icône SVG depuis ressource/icon/."""
    return ft.Image(src=f"icon/{name}.svg", width=size, height=size, color=color)


def hover_effect(idle_bg=None, hover_bg=None, *, scale=1.02,
                 hover_opacity=0.92):
    """Gestionnaire de survol court, sans reconstruction de la vue."""
    def handle(e):
        hovered = e.data is True or str(e.data).lower() == "true"
        if hover_bg is not None:
            e.control.bgcolor = hover_bg if hovered else idle_bg
        e.control.scale = ft.Scale(scale=scale if hovered else 1.0)
        e.control.opacity = hover_opacity if hovered else 1.0
        try:
            e.control.update()
        except Exception:
            pass
    return handle


def svg_icon_btn(name: str, size: int = ICON_MD, color=None, tooltip=None,
                 on_click=None, padding: int = ICON_BTN_PADDING,
                 hover_color=None) -> ft.Container:
    """Bouton cliquable avec icône SVG (remplace ft.IconButton)."""
    return ft.Container(
        width=size + padding * 2, height=size + padding * 2,
        border_radius=RADIUS_SM, alignment=ft.Alignment(0, 0),
        ink=True, tooltip=tooltip, on_click=on_click,
        scale=ft.Scale(scale=1.0),
        animate_scale=ft.Animation(MOTION_FAST, ft.AnimationCurve.EASE_OUT),
        animate_opacity=ft.Animation(MOTION_FAST, ft.AnimationCurve.EASE_OUT),
        on_hover=hover_effect(None, hover_color, scale=1.05,
                              hover_opacity=0.86),
        content=svg_icon(name, size=size, color=color),
    )
