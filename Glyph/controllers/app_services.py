"""
controllers/app_services.py — Dépendances applicatives, déclarées explicitement.

Le problème résolu
------------------
Les contrôleurs recevaient une partie de leurs dépendances **après**
construction, par assignation d'attributs privés :

    self.file_ctrl._st_msg = self.st_msg
    self.file_ctrl._save_session = self._save_session
    self.editor_ctrl._auto_save_callback = self.file_ctrl.auto_save

Rien dans la signature de `FileController.__init__` ne laissait deviner que
l'objet était inutilisable sans ces quatre lignes. Un oubli ne produisait
aucune erreur à la construction : la panne surgissait plus tard, à
l'enregistrement, sous la forme d'un `None` appelé.

Chaque contrôleur reçoit désormais cet objet et y puise ce dont il a besoin.
La dépendance devient visible dans la signature, et un champ manquant se
voit immédiatement.

Pourquoi des fonctions et non l'`AppController` lui-même : les rappels sont
résolus **à l'appel**, ce qui permet à `EditorController` de référencer
`FileController.auto_save` alors que ce dernier n'existe pas encore au
moment de la construction du premier.
"""

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class AppServices:
    """Ce que l'application offre à ses contrôleurs."""

    # --- Rendu et retour utilisateur ---
    rebuild: Callable[[], None]
    update_status: Callable[[], None]
    show_snack: Callable[..., None]
    #: Message transitoire de la barre d'état. Évite aux contrôleurs de
    #: manipuler directement un widget de vue.
    set_status_message: Callable[..., None]
    refresh_tab_bar: Callable[[], None]
    #: Pousse au client **uniquement** les zones que la frappe modifie :
    #: la couche de texte et la barre d'état. `page.update()` compare l'arbre
    #: entier à chaque appel — barre latérale et arborescence comprises —, ce
    #: qui n'a aucun sens entre deux touches.
    flush_typing: Callable[[], None]

    # --- Position dans le document ---
    get_cursor: Callable[[], int]
    get_selection: Callable[[], "tuple[int, int] | None"]

    # --- Persistance ---
    save_session: Callable[[], None]
    push_recent: Callable[[str], None]
    #: Sauvegarde automatique — résolue à l'appel, car `FileController`
    #: n'existe pas encore quand `EditorController` est construit.
    auto_save: Callable[[], None]
