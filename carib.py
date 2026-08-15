"""
Carib — Éditeur de texte moderne
================================

Fonctionnalités :
  - Onglets multiples, session restaurée au lancement
  - Écriture atomique : encodage et fins de ligne préservés
  - Recherche et remplacement (regex, casse, mot entier)
  - Palette de commandes (Ctrl+Maj+P) et barre IA (Ctrl+K)
  - IA multi-fournisseurs : ChatGPT, Claude, Gemini, Ollama (local)
  - Revue des modifications IA en diff inline (Tab / Échap)
  - Mode confidentiel : traitement 100 % local
  - Autocomplétion locale + prédiction IA
  - Synthèse vocale et dictée Windows, emojis, mode calcul
  - Thèmes clair / sombre

Auteur  : Arnaud
Binaire : voir EULA.txt        Code source : PolyForm Noncommercial 1.0.0
Version : définie dans core/constants.py — source de vérité unique.
"""

import os
import sys

import flet as ft

# Volontairement les seuls imports au niveau module : tout le reste est chargé
# à la demande. Le temps entre le double-clic et la première image dépend
# directement de ce qui est importé ici.
#
# `startup_probe` est importé en premier pour fixer l'origine du chronomètre ;
# il n'importe que `os` et `time`, et ne fait rien sans variable d'environnement.
from models import startup_probe

startup_probe.mark("1_python_pret")     # interpréteur + import de flet terminés

# Le journal s'installe avant tout le reste : une exception levée pendant la
# construction de l'application doit laisser une trace, elle aussi. C'est du
# stdlib (`logging`), le coût au démarrage est négligeable.
from core.constants import APP_FULL_NAME, APP_VERSION  # noqa: E402
from core import logging_setup  # noqa: E402

logging_setup.install(APP_VERSION)

from models.ipc_server import send_to_existing_instance  # noqa: E402

# Windows passe toute une sélection en arguments quand on l'ouvre avec Carib
# ou qu'on la dépose sur son icône : on les accepte tous, pas seulement le
# premier.
_startup_paths = [p for p in sys.argv[1:] if p and not p.startswith("-")]

# Une instance est déjà ouverte : lui transmettre les chemins et sortir.
if _startup_paths and send_to_existing_instance(_startup_paths):
    sys.exit(0)


def _assets_dir() -> str:
    """Chemin absolu du dossier de ressources.

    Un chemin relatif ne fonctionne pas dans l'application empaquetée :
    Flet le résout depuis le répertoire courant, alors que PyInstaller
    place les ressources dans `_internal/` à côté de l'exécutable. Sans
    cela, ni les polices, ni les icônes, ni le dictionnaire ne sont
    trouvés — et l'application reste sur un écran vide.
    """
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "ressource")


async def main(page: ft.Page):
    # À ce point, le moteur Flutter tourne et la connexion est établie.
    startup_probe.mark("2_flutter_pret")
    from controllers.app_controller import AppController
    startup_probe.mark("3_modules_charges")
    AppController(page, startup_paths=_startup_paths)


async def boot_screen(page: ft.Page):
    """Peint immédiatement une transition Carib pendant les imports lourds.

    Le client de bureau est alors déjà connecté, mais l'orchestrateur et les
    modèles ne sont pas encore chargés. Cette vue évite un écran blanc ou un
    message générique pendant ce court intervalle.
    """
    dark = False
    try:
        import json
        session_file = os.path.join(os.path.expanduser("~"), ".carib", "session.json")
        with open(session_file, "r", encoding="utf-8") as stream:
            dark = json.load(stream).get("settings", {}).get("theme") == "dark"
    except (OSError, ValueError, TypeError, AttributeError):
        pass

    bg = "#17171C" if dark else "#FBFBFD"
    primary = "#ECECEF" if dark else "#17171D"
    muted = "#858590"
    accent = "#9A85FF" if dark else "#6A4DF5"
    track = "#29292F" if dark else "#ECECF1"

    page.title = APP_FULL_NAME
    page.theme_mode = ft.ThemeMode.DARK if dark else ft.ThemeMode.LIGHT
    page.padding = 0
    page.spacing = 0
    page.bgcolor = bg
    boot = ft.Container(
        expand=True, bgcolor=bg, alignment=ft.Alignment(0, 0), opacity=0.0,
        animate_opacity=ft.Animation(240, ft.AnimationCurve.EASE_OUT),
        content=ft.Column(
            tight=True, spacing=14,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Image(src="icon/icon.ico", width=44, height=44),
                ft.Text("Carib", size=15, weight=ft.FontWeight.W_600,
                        color=primary),
                ft.ProgressRing(width=18, height=18, stroke_width=2,
                                color=accent, bgcolor=track),
                ft.Text("Ouverture de votre espace…", size=11,
                        color=muted),
            ],
        ),
    )
    page.add(boot)
    page.update()
    boot.opacity = 1.0
    page.update()
    startup_probe.mark("1b_ecran_carib")


if __name__ == "__main__":
    ft.run(main, before_main=boot_screen, assets_dir=_assets_dir())
