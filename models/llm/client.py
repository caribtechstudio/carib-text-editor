"""
models/llm/client.py — Client HTTP unique, compatible OpenAI.

Un seul client couvre ChatGPT, Claude, Gemini et Ollama : tous acceptent le
format `/chat/completions`. Les differences (URL, en-tetes, support du
schema JSON) viennent de `ProviderConfig`.

Ce module ne connait rien a l'interface : il leve des `LLMError` porteuses
d'un message deja redige pour l'utilisateur.
"""

import json
import threading
import time

from models.llm.base import (
    AuthError, CancelledError, ChatResult, LLMError, Message, ModelError,
    ModelInfo, NetworkError, QuotaError, RateLimitError, Usage,
)
from models.llm.registry import ProviderConfig

#: Delais par defaut. La generation longue (resume d'un gros texte) peut
#: prendre du temps ; le premier octet, lui, doit arriver vite.
CONNECT_TIMEOUT = 10
READ_TIMEOUT = 180

#: Nombre de nouvelles tentatives sur erreur transitoire (429, 5xx, reseau).
MAX_RETRIES = 2


class CancelToken:
    """Jeton d'annulation qui coupe reellement la connexion HTTP.

    L'ancienne implementation se contentait de lever un drapeau : la requete
    continuait a tourner en arriere-plan et a consommer des jetons. Ici on
    garde la reference de la reponse pour la fermer.
    """

    def __init__(self):
        self._event = threading.Event()
        self._response = None
        self._lock = threading.Lock()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def cancel(self):
        self._event.set()
        with self._lock:
            resp = self._response
        if resp is not None:
            try:
                resp.close()
            except Exception:
                pass

    def reset(self):
        self._event.clear()
        with self._lock:
            self._response = None

    def _attach(self, response):
        with self._lock:
            self._response = response
        if self._event.is_set():
            try:
                response.close()
            except Exception:
                pass

    def _check(self):
        if self._event.is_set():
            raise CancelledError()


class OpenAICompatClient:
    """Client pour un fournisseur compatible OpenAI."""

    def __init__(self, cfg: ProviderConfig, api_key: str = ""):
        self.cfg = cfg
        self.api_key = api_key or ""

    # ------------------------------------------------------------------
    # Infrastructure
    # ------------------------------------------------------------------
    @staticmethod
    def _requests():
        """Import differe — `requests` coute ~200 ms au demarrage."""
        try:
            import requests
            return requests
        except ImportError as exc:
            raise NetworkError(
                "Le module « requests » est absent.\nInstallez-le : pip install requests",
                str(exc),
            ) from exc

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.cfg.needs_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
            # Anthropic accepte l'en-tete natif en plus du Bearer.
            if self.cfg.key == "anthropic":
                headers["x-api-key"] = self.api_key
        headers.update(self.cfg.extra_headers)
        return headers

    def _url(self, path: str) -> str:
        return f"{self.cfg.base_url.rstrip('/')}/{path.lstrip('/')}"

    # ------------------------------------------------------------------
    # Traduction des erreurs
    # ------------------------------------------------------------------
    def _raise_for_status(self, response) -> None:
        if response.status_code < 400:
            return

        detail = ""
        try:
            body = response.json()
            err = body.get("error", body)
            if isinstance(err, dict):
                detail = str(err.get("message") or err.get("detail") or "")
            else:
                detail = str(err)
        except Exception:
            detail = (response.text or "")[:500]

        code = response.status_code
        name = self.cfg.label
        low = detail.lower()

        if code in (401, 403):
            raise AuthError(
                f"La clé API {name} est invalide ou révoquée.\n"
                f"Vérifiez-la dans Options ▸ Intelligence artificielle.",
                detail,
            )
        if code == 429:
            retry_after = 0.0
            try:
                retry_after = float(response.headers.get("Retry-After", 0))
            except (TypeError, ValueError):
                pass
            if "quota" in low or "billing" in low or "credit" in low:
                raise QuotaError(
                    f"Crédit {name} épuisé.\nRechargez votre compte ou "
                    f"basculez sur Ollama (local, gratuit).",
                    detail,
                )
            raise RateLimitError(
                f"{name} est momentanément saturé. Nouvel essai automatique…",
                detail, retry_after,
            )
        if code == 402 or "insufficient_quota" in low:
            raise QuotaError(
                f"Crédit {name} épuisé.\nRechargez votre compte ou "
                f"basculez sur Ollama (local, gratuit).",
                detail,
            )
        if code == 404:
            raise ModelError(
                f"Ce modèle n'existe pas ou n'est pas accessible avec votre "
                f"compte {name}.\nChoisissez-en un autre dans les options.",
                detail,
            )
        if code == 400:
            raise ModelError(
                f"{name} a refusé la requête.\n{detail[:200]}", detail,
            )
        if code >= 500:
            raise NetworkError(
                f"{name} rencontre un incident ({code}). Réessayez dans un instant.",
                detail,
            )
        raise LLMError(f"Erreur {name} ({code}).\n{detail[:200]}", detail)

    def _wrap_transport_error(self, exc) -> LLMError:
        """Traduit une exception de `requests` en erreur metier."""
        name = type(exc).__name__
        if "Timeout" in name:
            return NetworkError(
                f"{self.cfg.label} n'a pas répondu à temps.\n"
                "Essayez avec un texte plus court.", str(exc),
            )
        if "SSL" in name or "CERTIFICATE_VERIFY_FAILED" in str(exc):
            return NetworkError(
                f"La connexion sécurisée à {self.cfg.label} a été refusée.\n"
                "Un antivirus, un pare-feu ou un proxy d'entreprise intercepte "
                "probablement le trafic.", str(exc),
            )
        if "ConnectionError" in name or "ConnectTimeout" in name:
            if not self.cfg.needs_key:
                return NetworkError(
                    "Ollama ne répond pas sur localhost:11434.\n"
                    "Vérifiez qu'il est bien démarré.", str(exc),
                )
            return NetworkError(
                f"Impossible de joindre {self.cfg.label}.\n"
                "Vérifiez votre connexion internet.", str(exc),
            )
        return NetworkError(f"Erreur réseau : {exc}", str(exc))

    # ------------------------------------------------------------------
    # Modeles
    # ------------------------------------------------------------------
    def list_models(self, timeout: int = 15) -> list[ModelInfo]:
        """Liste les modeles reellement accessibles avec cette cle.

        C'est ce qui evite toute liste codee en dur : l'application ne
        perime jamais, meme quand le fournisseur renomme ses modeles.
        """
        requests = self._requests()
        try:
            resp = requests.get(self._url("models"), headers=self._headers(),
                                timeout=timeout)
            self._raise_for_status(resp)
            payload = resp.json()
        except LLMError:
            raise
        except Exception as exc:
            raise self._wrap_transport_error(exc) from exc

        # Le decoupage de la reponse reste dans un try : un fournisseur qui
        # renvoie une forme inattendue doit produire une erreur affichable,
        # pas une exception nue qui remonterait jusqu'au thread appelant.
        try:
            if isinstance(payload, dict):
                raw = payload.get("data") or payload.get("models") or []
            elif isinstance(payload, list):
                raw = payload
            else:
                raw = []

            models: list[ModelInfo] = []
            for item in raw:
                if isinstance(item, dict):
                    mid = item.get("id") or item.get("name") or ""
                else:
                    mid = str(item)
                if not mid:
                    continue
                low = mid.lower()
                if any(pat in low for pat in self.cfg.hide_patterns):
                    continue
                models.append(ModelInfo(id=mid, provider=self.cfg.key))
        except Exception as exc:
            raise LLMError(
                f"Réponse inattendue de {self.cfg.label} lors de la liste des modèles.",
                str(exc),
            ) from exc

        models.sort(key=lambda m: m.id)
        return models

    def validate(self) -> tuple[bool, str]:
        """Teste la configuration. Retourne (succes, message)."""
        if self.cfg.needs_key and not self.api_key:
            return False, "Aucune clé API renseignée."
        if self.cfg.key_prefix and not self.api_key.startswith(self.cfg.key_prefix):
            return False, (f"Cette clé ne ressemble pas à une clé {self.cfg.label} "
                           f"(elle devrait commencer par « {self.cfg.key_prefix} »).")
        try:
            models = self.list_models(timeout=15)
        except LLMError as exc:
            return False, exc.user_message
        except Exception as exc:
            # Filet de securite : `validate` est appele depuis un thread dont
            # l'echec silencieux laisserait l'interface bloquee sur « Test… ».
            return False, f"Erreur inattendue pendant le test : {exc}"
        if not models:
            return False, f"Connexion établie mais aucun modèle disponible sur {self.cfg.label}."
        return True, f"Connexion réussie — {len(models)} modèles disponibles."

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------
    def chat(self, messages: list[Message], model: str, *,
             stream: bool = False, on_chunk=None,
             json_schema: dict | None = None,
             temperature: float = 0.2, max_tokens: int | None = None,
             cancel: CancelToken | None = None,
             read_timeout: int = READ_TIMEOUT) -> ChatResult:
        """Appelle le modele. En streaming, `on_chunk(texte)` est appele au fil de l'eau."""
        cancel = cancel or CancelToken()
        payload: dict = {
            "model": model,
            "messages": [m.to_dict() for m in messages],
            "stream": stream,
            "temperature": temperature,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens

        if json_schema:
            if self.cfg.supports_json_schema:
                # Sortie garantie conforme : plus besoin de rattraper du JSON
                # approximatif a coups d'expressions regulieres.
                payload["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {"name": json_schema.get("name", "reponse"),
                                    "strict": True,
                                    "schema": json_schema["schema"]},
                }
            else:
                payload["response_format"] = {"type": "json_object"}

        last_error: LLMError | None = None
        for attempt in range(MAX_RETRIES + 1):
            cancel._check()
            try:
                return self._do_chat(payload, stream, on_chunk, cancel, read_timeout)
            except CancelledError:
                raise
            except (RateLimitError, NetworkError) as exc:
                last_error = exc
                if attempt >= MAX_RETRIES:
                    break
                delay = getattr(exc, "retry_after", 0) or (2 ** attempt)
                # Attente interruptible : annuler pendant un backoff doit
                # rendre la main immediatement.
                if cancel._event.wait(min(delay, 10)):
                    raise CancelledError() from exc
            except LLMError:
                raise

        raise last_error or NetworkError("Échec après plusieurs tentatives.")

    def _do_chat(self, payload, stream, on_chunk, cancel, read_timeout) -> ChatResult:
        requests = self._requests()
        started = time.perf_counter()

        try:
            resp = requests.post(
                self._url("chat/completions"),
                headers=self._headers(), json=payload,
                timeout=(CONNECT_TIMEOUT, read_timeout), stream=stream,
            )
        except Exception as exc:
            if cancel.cancelled:
                raise CancelledError() from exc
            raise self._wrap_transport_error(exc) from exc

        cancel._attach(resp)
        try:
            self._raise_for_status(resp)
            if stream:
                text, usage = self._read_stream(resp, on_chunk, cancel)
            else:
                text, usage = self._read_once(resp)
        except LLMError:
            raise
        except Exception as exc:
            if cancel.cancelled:
                raise CancelledError() from exc
            raise self._wrap_transport_error(exc) from exc
        finally:
            try:
                resp.close()
            except Exception:
                pass

        return ChatResult(text=text, usage=usage, model=payload["model"],
                          provider=self.cfg.key,
                          elapsed=round(time.perf_counter() - started, 2))

    @staticmethod
    def _read_once(resp) -> tuple[str, Usage]:
        body = resp.json()
        choices = body.get("choices") or []
        text = ""
        if choices:
            text = (choices[0].get("message") or {}).get("content") or ""
        raw_usage = body.get("usage") or {}
        usage = Usage(int(raw_usage.get("prompt_tokens", 0) or 0),
                      int(raw_usage.get("completion_tokens", 0) or 0))
        return text.strip(), usage

    @staticmethod
    def _read_stream(resp, on_chunk, cancel) -> tuple[str, Usage]:
        parts: list[str] = []
        usage = Usage()

        for line in resp.iter_lines(decode_unicode=True):
            cancel._check()
            if not line:
                continue
            if line.startswith("data:"):
                line = line[5:].strip()
            if not line or line == "[DONE]":
                if line == "[DONE]":
                    break
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue

            raw_usage = data.get("usage")
            if raw_usage:
                usage = Usage(int(raw_usage.get("prompt_tokens", 0) or 0),
                              int(raw_usage.get("completion_tokens", 0) or 0))

            for choice in data.get("choices") or []:
                delta = choice.get("delta") or {}
                piece = delta.get("content")
                if piece:
                    parts.append(piece)
                    if on_chunk:
                        on_chunk(piece)

        return "".join(parts).strip(), usage
