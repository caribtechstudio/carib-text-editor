"""
models/ai_completer.py -- Prediction de la suite du texte (« texte fantome »).

Passe par LLMManager, donc fonctionne indifferemment avec ChatGPT, Claude,
Gemini ou Ollama.

Trois garde-fous, parce que cette fonction se declenche pendant la frappe :

  * **Debounce** — rien ne part avant 600 ms de pause. Sans cela chaque
    touche declencherait un appel facture.
  * **Cache** — la cle inclut la position du curseur : deux endroits
    differents du meme paragraphe ne partagent plus la meme prediction,
    ce qui produisait auparavant des suggestions incoherentes.
  * **Annulation reelle** — la connexion HTTP est fermee, pas seulement
    marquee comme abandonnee.
"""

import threading

from models.llm.base import LLMError, Message
from models.llm.client import CancelToken
from models.scheduler import scheduler

#: Cle d'ordonnancement du debounce de prediction.
_DEBOUNCE_TASK = "ai_completer.debounce"

_SYSTEM_PROMPT = (
    "Tu completes le texte de l'utilisateur. Ecris UNIQUEMENT la suite "
    "directe, sans repeter ce qui precede, sans guillemets, sans commentaire. "
    "Une seule phrase courte, dans la meme langue et le meme ton que le texte."
)


class AICompleter:
    """Predicteur de phrase avec debounce, cache et annulation."""

    DEBOUNCE_MS = 600      # pause avant d'interroger le modele
    MAX_TOKENS = 40        # une phrase courte suffit
    CACHE_SIZE = 64

    def __init__(self, manager=None):
        self.manager = manager
        self._cancel = CancelToken()
        self._thread: threading.Thread | None = None
        self._cache: dict[tuple[str, int], str] = {}
        self._cache_order: list[tuple[str, int]] = []
        self._lock = threading.Lock()

        self.on_prediction = lambda text: None

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def cancel(self):
        """Annule le debounce et coupe la requete en cours."""
        scheduler.cancel(_DEBOUNCE_TASK)
        self._cancel.cancel()

    def request_completion(self, context: str, cursor: int = 0):
        """Demande une prediction pour `context` (texte jusqu'au curseur)."""
        scheduler.cancel(_DEBOUNCE_TASK)
        self._cancel.cancel()

        if not self.manager or not context.strip():
            return
        if not self.manager.is_task_enabled("autocomplete"):
            return
        # Le mode confidentiel n'interdit pas la prediction, mais un envoi
        # distant sans consentement explicite, si.
        if self.manager.requires_consent("autocomplete"):
            return

        # La position fait partie de la cle : c'est ce qui distingue deux
        # points d'edition ayant le meme voisinage textuel.
        key = (context[-120:], cursor)
        with self._lock:
            cached = self._cache.get(key)
        if cached is not None:
            self.on_prediction(cached)
            return

        def _fire():
            self._cancel.reset()
            self._thread = threading.Thread(
                target=self._run, args=(context, key), daemon=True,
            )
            self._thread.start()

        scheduler.schedule(_DEBOUNCE_TASK, self.DEBOUNCE_MS / 1000.0, _fire)

    def _run(self, context: str, key):
        try:
            result = self.manager.complete(
                [Message("system", _SYSTEM_PROMPT), Message("user", context)],
                task="autocomplete",
                stream=False,
                temperature=0.6,
                max_tokens=self.MAX_TOKENS,
                cancel=self._cancel,
                read_timeout=20,
            )
        except LLMError:
            return          # l'autocompletion ne doit jamais deranger l'utilisateur
        except Exception:
            return

        if self._cancel.cancelled:
            return

        prediction = self._clean(result.text, context)
        if not prediction:
            return

        with self._lock:
            self._cache[key] = prediction
            self._cache_order.append(key)
            if len(self._cache_order) > self.CACHE_SIZE:
                self._cache.pop(self._cache_order.pop(0), None)

        self.on_prediction(prediction)

    @staticmethod
    def _clean(prediction: str, context: str) -> str:
        """Nettoie la sortie du modele (repetitions, guillemets, verbiage)."""
        prediction = (prediction or "").strip().strip('"').strip("«»").strip()
        if not prediction:
            return ""

        # Certains modeles rejouent la fin du contexte : on la retire.
        tail = context[-60:].strip()
        if tail:
            lowered = prediction.lower()
            for size in range(min(len(tail), 40), 9, -1):
                if lowered.startswith(tail[-size:].lower()):
                    prediction = prediction[size:].lstrip()
                    break

        # Une seule phrase : on coupe apres la premiere ponctuation forte.
        for i, ch in enumerate(prediction):
            if ch in ".!?" and i > 0:
                prediction = prediction[:i + 1]
                break

        prediction = prediction.strip()
        # Garde-fou : une « prediction » de 300 caracteres est un modele
        # qui a ignore la consigne, mieux vaut ne rien proposer.
        if len(prediction) > 200:
            return ""
        return prediction

    def clear_cache(self):
        with self._lock:
            self._cache.clear()
            self._cache_order.clear()
