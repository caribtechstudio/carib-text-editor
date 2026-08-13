"""
controllers/notifier.py — Notifications transitoires (le bandeau du bas).

Le problème résolu
------------------
Chaque appel à `show_snack` créait une `SnackBar` neuve et la remettait à
`page.show_dialog`, qui l'**empile** dans `page._dialogs`. Rien ne l'en
retirait : Flet ne dépile que sur `on_dismiss`, et une notification qui
s'efface toute seule au bout de trois secondes ne déclenche pas toujours cet
événement. Deux conséquences, exactement celles observées :

  1. **La pile grossit sans fin.** Après une session de travail elle contient
     des dizaines de bandeaux « morts ». Chaque `page.update()` les compare
     tous, et le garde de dialogues les parcourt à chaque ouverture de fenêtre.
  2. **Les notifications ne s'affichent plus.** Côté Flutter, le
     `ScaffoldMessenger` met les `SnackBar` **en file** : il n'en montre qu'une
     à la fois et fait patienter les suivantes. Une notification demandée
     pendant qu'une autre est visible n'apparaissait donc que trois secondes
     plus tard — ou jamais, noyée dans la file accumulée.

La règle retenue est celle de tous les éditeurs sérieux : **une seule
notification vivante à la fois**. La précédente est fermée et retirée de la
pile avant que la suivante ne soit posée, et un minuteur la retire de toute
façon à l'expiration. La file de Flutter ne peut donc jamais se former.

Les messages identiques rapprochés sont fusionnés : enregistrer deux fois de
suite ne doit pas faire clignoter deux fois le même bandeau.
"""

import time

import flet as ft

from constants import UI_FONT_STRONG

from models.scheduler import scheduler

#: Clé d'ordonnancement du retrait automatique.
_EXPIRE_TASK = "notifier.expire"

#: Durée d'affichage par défaut.
DEFAULT_DURATION_MS = 3000

#: Deux messages identiques séparés de moins de ça ne comptent que pour un.
_DEDUP_WINDOW = 0.6


class Notifier:
    """Affiche les notifications transitoires, une à la fois."""

    def __init__(self, page, color_fn):
        self._page = page
        #: `c(clair, sombre)` — la couleur par défaut suit le thème courant.
        self._c = color_fn
        self._current: ft.SnackBar | None = None
        self._last_message = ""
        self._last_time = 0.0

    # ------------------------------------------------------------------
    # Affichage
    # ------------------------------------------------------------------
    def show(self, message: str, color=None, duration_ms: int = DEFAULT_DURATION_MS):
        """Affiche `message`, en remplaçant la notification en cours."""
        message = str(message or "")
        if not message:
            return

        now = time.monotonic()
        if (message == self._last_message
                and now - self._last_time < _DEDUP_WINDOW):
            return
        self._last_message, self._last_time = message, now

        self._dismiss_current()

        bar = ft.SnackBar(
            content=ft.Text(message, color="#FFFFFF", size=13,
                            font_family=UI_FONT_STRONG,
                            weight=ft.FontWeight.W_700),
            bgcolor=color or self._default_color(),
            duration=ft.Duration(milliseconds=duration_ms),
            behavior=ft.SnackBarBehavior.FLOATING,
            margin=ft.Margin(24, 0, 24, 24),
            dismiss_direction=ft.DismissDirection.DOWN,
        )

        try:
            self._page.show_dialog(bar)
        except Exception:
            # Une notification qui échoue ne doit jamais interrompre l'action
            # qu'elle accompagnait (enregistrement, ouverture de fichier…).
            return

        self._current = bar
        # Filet : Flutter efface le bandeau tout seul, mais rien ne garantit
        # qu'il nous le dise. On le retire de la pile quoi qu'il arrive.
        scheduler.schedule(_EXPIRE_TASK, duration_ms / 1000.0 + 0.5,
                           lambda: self._expire(bar))

    # ------------------------------------------------------------------
    # Retrait
    # ------------------------------------------------------------------
    def _default_color(self):
        from theme import T
        return self._c(T.L_PRIMARY, T.D_SURFACE)

    def _dismiss_current(self):
        """Ferme et dépile la notification visible, s'il y en a une."""
        scheduler.cancel(_EXPIRE_TASK)
        bar, self._current = self._current, None
        if bar is not None:
            self._remove(bar)

    def _expire(self, bar):
        """Appelé depuis l'ordonnanceur : repasse par le thread d'interface."""
        try:
            self._page.run_thread(lambda: self._on_expired(bar))
        except Exception:
            pass

    def _on_expired(self, bar):
        if self._current is bar:
            self._current = None
        self._remove(bar)

    def _remove(self, bar):
        """Retire `bar` de la pile de dialogues de la page."""
        stack = getattr(self._page, "_dialogs", None)
        if stack is None:
            return
        try:
            bar.open = False
            if bar in stack.controls:
                stack.controls.remove(bar)
                stack.update()
        except Exception:
            pass

    # ------------------------------------------------------------------
    def shutdown(self):
        """Fermeture de l'application : plus rien à afficher ni à minuter."""
        scheduler.cancel(_EXPIRE_TASK)
        self._current = None

    def prune(self):
        """Retire de la pile toutes les notifications oubliées.

        Utile après une restauration de session ou une rafale d'erreurs : la
        pile doit revenir à l'état « seuls les vrais dialogues comptent ».
        """
        stack = getattr(self._page, "_dialogs", None)
        if stack is None:
            return
        stale = [d for d in stack.controls
                 if isinstance(d, ft.SnackBar) and d is not self._current]
        if not stale:
            return
        for d in stale:
            d.open = False
            stack.controls.remove(d)
        try:
            stack.update()
        except Exception:
            pass
