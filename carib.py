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
from core.constants import APP_VERSION  # noqa: E402
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


if __name__ == "__main__":
    ft.run(main, assets_dir=_assets_dir())
