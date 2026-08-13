"""
controllers/dialog_guard.py — Un seul dialogue à l'écran à la fois.

`Page.show_dialog` empile : deux appels donnent deux fenêtres superposées.
Quand l'ouverture d'un dialogue tarde un peu (chargement d'icônes, appel
réseau du gestionnaire de modèles), l'utilisateur reclique — et se retrouve
avec cinq copies des options à refermer une par une.

On enveloppe donc `show_dialog` une fois pour toutes, au démarrage : tant
qu'un dialogue est ouvert, les demandes suivantes sont ignorées. Le garde
lit la pile réelle de Flet (`page._dialogs`) plutôt que de tenir son propre
compteur : un dialogue fermé au clavier ou en cliquant à côté ne passe pas
par `pop_dialog`, et un compteur maison resterait bloqué à « ouvert ».

Les `SnackBar` traversent le garde sans le déclencher : ce sont des
notifications transitoires, pas des fenêtres modales, et elles doivent
pouvoir s'afficher par-dessus un dialogue.
"""

import flet as ft


def _is_transient(dialog) -> bool:
    """Vrai pour les surfaces qui ne bloquent pas l'interface."""
    return isinstance(dialog, ft.SnackBar)


def _has_open_dialog(page) -> bool:
    """Un dialogue modal est-il déjà affiché ?

    `pop_dialog` passe `open` à False avant que le contrôle ne quitte la
    pile : filtrer sur `open` laisse donc passer l'enchaînement légitime
    « je ferme les options pour ouvrir l'aide ».
    """
    stack = getattr(page, "_dialogs", None)
    if stack is None:
        return False
    return any(getattr(d, "open", False) and not _is_transient(d)
               for d in stack.controls)


def install_dialog_guard(page) -> None:
    """Rend `page.show_dialog` idempotent tant qu'un dialogue est ouvert."""
    if getattr(page, "_glyph_dialog_guard", False):
        return
    page._glyph_dialog_guard = True

    show_dialog = page.show_dialog

    def guarded_show_dialog(dialog):
        if not _is_transient(dialog) and _has_open_dialog(page):
            return
        show_dialog(dialog)

    def guarded_pop_dialog():
        """Ferme le dialogue, jamais la notification posée par-dessus.

        `pop_dialog` ferme le contrôle ouvert le plus haut de la pile. Une
        `SnackBar` affichée pendant qu'un dialogue est ouvert prend cette
        place : « Fermer » ferait alors disparaître la notification en
        laissant le dialogue — et le garde, lui, refuserait tout nouveau
        dialogue tant que celui-ci n'est pas parti. On saute donc les
        surfaces transitoires.
        """
        stack = getattr(page, "_dialogs", None)
        if stack is None:
            return None
        dialog = next((d for d in reversed(stack.controls)
                       if getattr(d, "open", False) and not _is_transient(d)), None)
        if dialog is None:
            return None
        dialog.open = False
        dialog.update()
        return dialog

    page.show_dialog = guarded_show_dialog
    page.pop_dialog = guarded_pop_dialog
