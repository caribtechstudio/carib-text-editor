"""
models/ai_completer.py -- Prediction de phrases par IA (Ollama).

Appelle l'API Ollama en streaming pour predire la suite du texte.
Gere le debounce, l'annulation et le cache.
"""

import json
import threading
import time

try:
    import requests as _requests
except ImportError:
    _requests = None

from ai_checker import OLLAMA_API_URL


class AICompleter:
    """Predicteur IA via Ollama avec streaming, debounce et annulation."""

    DEBOUNCE_MS = 400          # delai apres derniere frappe
    CONTEXT_CHARS = 500        # nb de caracteres de contexte envoyes
    MAX_TOKENS = 40            # tokens max pour la prediction
    CACHE_SIZE = 32            # taille du cache LRU

    def __init__(self):
        self._cancel_event = threading.Event()
        self._debounce_timer: threading.Timer | None = None
        self._thread: threading.Thread | None = None
        self._cache: dict[str, str] = {}
        self._cache_order: list[str] = []
        self._lock = threading.Lock()

        # Callbacks (definis par le controller)
        self.on_prediction: callable = lambda text: None
        self.on_error: callable = lambda msg: None

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def cancel(self):
        """Annule toute requete en cours et le debounce."""
        if self._debounce_timer:
            self._debounce_timer.cancel()
            self._debounce_timer = None
        self._cancel_event.set()

    def request_completion(self, text: str, model_id: str):
        """Demande une prediction avec debounce."""
        # Annuler le debounce precedent
        if self._debounce_timer:
            self._debounce_timer.cancel()

        # Annuler la requete en cours
        self._cancel_event.set()

        if not text or not text.strip():
            return

        # Extraire le contexte (derniers N caracteres)
        context = text[-self.CONTEXT_CHARS:] if len(text) > self.CONTEXT_CHARS else text

        # Verifier le cache
        cache_key = context[-100:]  # cle basee sur les 100 derniers chars
        with self._lock:
            if cache_key in self._cache:
                self.on_prediction(self._cache[cache_key])
                return

        def _fire():
            self._cancel_event.clear()
            self._thread = threading.Thread(
                target=self._run, args=(context, model_id, cache_key),
                daemon=True,
            )
            self._thread.start()

        self._debounce_timer = threading.Timer(
            self.DEBOUNCE_MS / 1000.0, _fire,
        )
        self._debounce_timer.daemon = True
        self._debounce_timer.start()

    def _run(self, context: str, model_id: str, cache_key: str):
        """Thread d'appel a l'API Ollama en streaming."""
        if _requests is None:
            return

        # Construire le prompt de completion
        prompt = (
            "Continue le texte suivant naturellement. "
            "Ecris UNIQUEMENT la suite directe, sans repeter le texte existant. "
            "Maximum 1 phrase courte.\n\n"
            f"{context}"
        )

        payload = {
            "model": model_id,
            "prompt": prompt,
            "stream": True,
            "options": {
                "temperature": 0.7,
                "top_p": 0.9,
                "num_predict": self.MAX_TOKENS,
                "stop": ["\n\n", ".", "!", "?"],
            },
        }

        try:
            response = _requests.post(
                OLLAMA_API_URL, json=payload, timeout=15, stream=True,
            )
            response.raise_for_status()

            prediction = ""
            for line in response.iter_lines(decode_unicode=True):
                if self._cancel_event.is_set():
                    return
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    chunk = data.get("response", "")
                    prediction += chunk
                    if data.get("done", False):
                        break
                except json.JSONDecodeError:
                    continue

            if self._cancel_event.is_set():
                return

            # Nettoyer la prediction
            prediction = self._clean_prediction(prediction, context)

            if prediction:
                # Mettre en cache
                with self._lock:
                    self._cache[cache_key] = prediction
                    self._cache_order.append(cache_key)
                    if len(self._cache_order) > self.CACHE_SIZE:
                        old = self._cache_order.pop(0)
                        self._cache.pop(old, None)

                if not self._cancel_event.is_set():
                    self.on_prediction(prediction)

        except Exception:
            pass  # silencieux — l'autocompletion ne doit jamais bloquer

    @staticmethod
    def _clean_prediction(prediction: str, context: str) -> str:
        """Nettoie la prediction pour eviter les repetitions et artefacts."""
        prediction = prediction.strip()
        if not prediction:
            return ""

        # Supprimer si la prediction repete la fin du contexte
        ctx_end = context.strip()[-50:].lower() if context.strip() else ""
        if prediction.lower().startswith(ctx_end[:20]) and len(ctx_end) > 5:
            prediction = prediction[len(ctx_end):]

        # Ajouter la ponctuation finale si absente
        if prediction and prediction[-1] not in ".!?;:,":
            prediction += "."

        # Limiter a une phrase
        for i, ch in enumerate(prediction):
            if ch in ".!?" and i > 0:
                prediction = prediction[:i + 1]
                break

        return prediction.strip()

    def clear_cache(self):
        """Vide le cache de predictions."""
        with self._lock:
            self._cache.clear()
            self._cache_order.clear()
