"""
models/scheduler.py — Ordonnanceur unique pour les tâches différées.

Le problème résolu
------------------
Glyph reposait sur `threading.Timer`, à seize endroits. Chaque appel crée un
**thread du système d'exploitation**, le démarre, le fait dormir, puis le
détruit. Or ces timers sont relancés à chaque frappe (instantané d'annulation,
sauvegarde auto, réindexation du dictionnaire, comptage des mots, debounce du
modèle) : taper cent caractères créait et détruisait plusieurs centaines de
threads.

Ici, **un seul** thread dort jusqu'à la prochaine échéance. Reprogrammer une
tâche revient à mettre à jour une entrée dans un dictionnaire — aucun thread
n'est créé.

Le second bénéfice est la fiabilité : les tâches sont nommées et idempotentes.
Replanifier « auto_save » remplace l'échéance précédente au lieu d'empiler un
timer de plus qu'il faudrait penser à annuler.
"""

import heapq
import itertools
import threading
import time


class Scheduler:
    """Exécute des fonctions après un délai, sur un unique thread."""

    def __init__(self, name: str = "glyph-scheduler"):
        self._lock = threading.Lock()
        self._wakeup = threading.Condition(self._lock)
        #: Tas de (échéance, numéro de séquence, clé).
        self._heap: list[tuple[float, int, str]] = []
        #: Dernière échéance retenue par clé — fait autorité sur le tas.
        self._tasks: dict[str, tuple[float, int, callable]] = {}
        self._counter = itertools.count()
        self._running = False
        self._name = name
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Cycle de vie
    # ------------------------------------------------------------------
    def start(self):
        with self._lock:
            if self._running:
                return
            self._running = True
            self._thread = threading.Thread(target=self._loop, name=self._name,
                                            daemon=True)
            self._thread.start()

    def stop(self):
        """Arrête l'ordonnanceur et abandonne les tâches en attente."""
        with self._wakeup:
            self._running = False
            self._heap.clear()
            self._tasks.clear()
            self._wakeup.notify_all()

    # ------------------------------------------------------------------
    # Programmation
    # ------------------------------------------------------------------
    def schedule(self, key: str, delay: float, callback):
        """Exécute `callback` dans `delay` secondes.

        Reprogrammer la même `key` **remplace** l'échéance précédente : c'est
        le comportement attendu d'un anti-rebond, et il devient impossible
        d'oublier d'annuler le timer précédent.
        """
        self.start()
        due = time.monotonic() + max(0.0, delay)
        with self._wakeup:
            seq = next(self._counter)
            self._tasks[key] = (due, seq, callback)
            heapq.heappush(self._heap, (due, seq, key))
            self._wakeup.notify()

    def cancel(self, key: str):
        """Annule une tâche en attente. Sans effet si elle n'existe pas."""
        with self._wakeup:
            self._tasks.pop(key, None)
            self._wakeup.notify()

    def cancel_all(self):
        with self._wakeup:
            self._tasks.clear()
            self._heap.clear()
            self._wakeup.notify()

    def flush(self, key: str):
        """Exécute immédiatement une tâche en attente, hors du thread.

        Sert lors de la fermeture : un instantané d'annulation ou une
        sauvegarde programmés ne doivent pas être perdus.
        """
        with self._wakeup:
            entry = self._tasks.pop(key, None)
        if entry is not None:
            self._run(entry[2])

    @property
    def pending(self) -> int:
        with self._lock:
            return len(self._tasks)

    def is_pending(self, key: str) -> bool:
        with self._lock:
            return key in self._tasks

    # ------------------------------------------------------------------
    # Boucle
    # ------------------------------------------------------------------
    def _loop(self):
        while True:
            with self._wakeup:
                if not self._running:
                    return

                # Purger les entrées périmées : une clé reprogrammée laisse
                # derrière elle une entrée obsolète dans le tas.
                while self._heap:
                    due, seq, key = self._heap[0]
                    current = self._tasks.get(key)
                    if current is None or current[1] != seq:
                        heapq.heappop(self._heap)
                        continue
                    break

                if not self._heap:
                    self._wakeup.wait()          # rien à faire : on dort
                    continue

                due, seq, key = self._heap[0]
                now = time.monotonic()
                if due > now:
                    self._wakeup.wait(due - now)
                    continue

                heapq.heappop(self._heap)
                entry = self._tasks.get(key)
                if entry is None or entry[1] != seq:
                    continue
                del self._tasks[key]
                callback = entry[2]

            self._run(callback)

    @staticmethod
    def _run(callback):
        # Une tâche qui échoue ne doit jamais tuer l'ordonnanceur : toutes les
        # autres (sauvegarde, journal de récupération) en dépendent.
        try:
            callback()
        except Exception:
            pass


#: Ordonnanceur partagé par l'application.
scheduler = Scheduler()
