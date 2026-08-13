"""
models/llm/manager.py — Facade unique pour tout ce qui touche a l'IA.

Le reste de l'application ne parle qu'a cet objet. Il porte :

  * la configuration (fournisseur actif, modeles, profil de qualite) ;
  * le **mode confidentiel**, qui force le traitement local ;
  * le repli automatique sur Ollama quand le cloud est indisponible ;
  * le suivi de consommation, pour afficher un cout a l'utilisateur.

La configuration vit dans `~/.glyph/llm.json`. Les cles API, elles, ne
transitent jamais par ce fichier (voir credentials.py).
"""

import json
import os
import threading
import time

from models.llm import credentials
from models.llm.base import (
    ChatResult, LLMError, Message, ModelInfo, NetworkError, QuotaError, Usage,
)
from models.llm.client import CancelToken, OpenAICompatClient
from models.llm.registry import DEFAULT_PROVIDER, PROVIDERS, is_local

_DATA_DIR = os.path.join(os.path.expanduser("~"), ".glyph")
_CONFIG_FILE = os.path.join(_DATA_DIR, "llm.json")
_MODELS_CACHE = os.path.join(_DATA_DIR, "llm_models.json")

#: Duree de validite du cache de la liste des modeles.
_MODELS_TTL = 24 * 3600

# --- Niveaux de modele -------------------------------------------------------
TIER_FAST = "fast"          # autocompletion, taches courtes et frequentes
TIER_STANDARD = "standard"  # correction, traduction, reformulation
TIER_BEST = "best"          # resume long, redaction exigeante

#: Indices textuels servant a deviner le niveau d'un modele inconnu.
_FAST_HINTS = ("nano", "mini", "lite", "flash", "haiku", "small", "1b", "1.5b", "3b")
_BEST_HINTS = ("opus", "pro", "-o1", "ultra", "large", "70b")

# --- Profils utilisateur -----------------------------------------------------
#: Ce que l'utilisateur choisit reellement : un compromis, pas un modele.
PROFILES = {
    "eco":       {"autocomplete": TIER_FAST, "edit": TIER_FAST,     "heavy": TIER_STANDARD},
    "balanced":  {"autocomplete": TIER_FAST, "edit": TIER_STANDARD, "heavy": TIER_STANDARD},
    "quality":   {"autocomplete": None,      "edit": TIER_STANDARD, "heavy": TIER_BEST},
}
PROFILE_LABELS = {
    "eco": "Rapide et économique",
    "balanced": "Équilibré",
    "quality": "Qualité maximale",
}
DEFAULT_PROFILE = "balanced"


def guess_tier(model_id: str) -> str:
    """Devine le niveau d'un modele a partir de son identifiant."""
    low = model_id.lower()
    if any(h in low for h in _BEST_HINTS):
        return TIER_BEST
    if any(h in low for h in _FAST_HINTS):
        return TIER_FAST
    return TIER_STANDARD


class LLMManager:
    """Point d'entree unique pour la generation de texte."""

    def __init__(self):
        self._lock = threading.Lock()
        self._models_cache: dict[str, tuple[float, list[str]]] = {}

        # --- Configuration persistee ---
        self.active_provider: str = DEFAULT_PROVIDER
        self.profile: str = DEFAULT_PROFILE
        #: Force le traitement local, quoi qu'il arrive (réglage global).
        self.privacy_mode: bool = False
        #: Idem, mais pour le document actuellement ouvert. Renseigné par
        #: AppController à chaque changement d'onglet. Permet de protéger un
        #: texte précis sans basculer toute l'application hors ligne.
        self.document_private: bool = False
        #: L'utilisateur a-t-il accepte que son texte parte vers un service distant ?
        self.cloud_consent: bool = False
        #: Repli automatique sur Ollama si le cloud echoue.
        self.fallback_local: bool = True
        #: Modele choisi par fournisseur et par niveau : {provider: {tier: id}}.
        self.models: dict[str, dict[str, str]] = {}
        #: Alerte de depense, en euros. 0 = desactivee.
        self.budget_alert: float = 5.0

        # --- Consommation de la session ---
        self.session_usage = Usage()
        self.session_cost: float = 0.0
        self.last_error: str = ""

        self._load()
        self._load_models_cache()

    # ------------------------------------------------------------------
    # Persistance
    # ------------------------------------------------------------------
    def _load(self):
        try:
            with open(_CONFIG_FILE, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError, ValueError):
            return
        if not isinstance(data, dict):
            return
        provider = data.get("active_provider")
        if provider in PROVIDERS:
            self.active_provider = provider
        if data.get("profile") in PROFILES:
            self.profile = data["profile"]
        self.privacy_mode = bool(data.get("privacy_mode", False))
        self.cloud_consent = bool(data.get("cloud_consent", False))
        self.fallback_local = bool(data.get("fallback_local", True))
        models = data.get("models")
        if isinstance(models, dict):
            self.models = {p: dict(t) for p, t in models.items()
                           if p in PROVIDERS and isinstance(t, dict)}
        try:
            self.budget_alert = max(0.0, float(data.get("budget_alert", 5.0)))
        except (TypeError, ValueError):
            pass

    def save(self):
        os.makedirs(_DATA_DIR, exist_ok=True)
        payload = {
            "active_provider": self.active_provider,
            "profile": self.profile,
            "privacy_mode": self.privacy_mode,
            "cloud_consent": self.cloud_consent,
            "fallback_local": self.fallback_local,
            "models": self.models,
            "budget_alert": self.budget_alert,
        }
        tmp = _CONFIG_FILE + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False, indent=2)
            os.replace(tmp, _CONFIG_FILE)
        except OSError:
            pass

    def _load_models_cache(self):
        try:
            with open(_MODELS_CACHE, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            for provider, entry in data.items():
                self._models_cache[provider] = (float(entry["ts"]), list(entry["ids"]))
        except (OSError, json.JSONDecodeError, ValueError, KeyError, TypeError):
            pass

    def _save_models_cache(self):
        os.makedirs(_DATA_DIR, exist_ok=True)
        payload = {p: {"ts": ts, "ids": ids}
                   for p, (ts, ids) in self._models_cache.items()}
        tmp = _MODELS_CACHE + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(payload, fh)
            os.replace(tmp, _MODELS_CACHE)
        except OSError:
            pass

    # ------------------------------------------------------------------
    # Cles et connexion
    # ------------------------------------------------------------------
    @staticmethod
    def get_key(provider: str) -> str:
        return credentials.get_key(provider)

    @staticmethod
    def masked_key(provider: str) -> str:
        return credentials.mask(credentials.get_key(provider))

    def set_key(self, provider: str, key: str):
        credentials.set_key(provider, key.strip())
        self._models_cache.pop(provider, None)

    def forget(self, provider: str):
        """Supprime la cle et la configuration d'un fournisseur."""
        credentials.delete_key(provider)
        self.models.pop(provider, None)
        self._models_cache.pop(provider, None)
        if self.active_provider == provider:
            remaining = self.configured_providers()
            self.active_provider = remaining[0] if remaining else DEFAULT_PROVIDER
        self.save()

    def client_for(self, provider: str) -> OpenAICompatClient:
        cfg = PROVIDERS[provider]
        return OpenAICompatClient(cfg, credentials.get_key(provider))

    def test_connection(self, provider: str, key: str = "") -> tuple[bool, str]:
        """Verifie une cle sans l'enregistrer."""
        cfg = PROVIDERS.get(provider)
        if not cfg:
            return False, "Fournisseur inconnu."
        try:
            client = OpenAICompatClient(cfg, key or credentials.get_key(provider))
            return client.validate()
        except Exception as exc:  # jamais de remontee brute : voir client.validate
            return False, f"Erreur inattendue pendant le test : {exc}"

    def configured_providers(self) -> list[str]:
        """Fournisseurs utilisables : cle enregistree, ou local et disponible."""
        result = [p for p in credentials.configured_providers() if p in PROVIDERS]
        if "ollama" not in result and self.is_ollama_running():
            result.append("ollama")
        return result

    def is_configured(self) -> bool:
        return bool(self.configured_providers())

    @staticmethod
    def is_ollama_running() -> bool:
        """Ping local tres court — n'appelle aucun serveur distant."""
        import socket
        try:
            with socket.create_connection(("127.0.0.1", 11434), timeout=0.35):
                return True
        except OSError:
            return False

    # ------------------------------------------------------------------
    # Modeles
    # ------------------------------------------------------------------
    def available_models(self, provider: str, force: bool = False) -> list[ModelInfo]:
        """Liste des modeles, avec cache de 24 h."""
        now = time.time()
        cached = self._models_cache.get(provider)
        if not force and cached and now - cached[0] < _MODELS_TTL:
            return [ModelInfo(id=m, provider=provider) for m in cached[1]]

        cfg = PROVIDERS.get(provider)
        if not cfg:
            return []
        try:
            models = self.client_for(provider).list_models()
        except LLMError:
            if cached:
                return [ModelInfo(id=m, provider=provider) for m in cached[1]]
            return [ModelInfo(id=m, provider=provider) for m in cfg.fallback_models]

        with self._lock:
            self._models_cache[provider] = (now, [m.id for m in models])
            self._save_models_cache()
        return models

    def set_model(self, provider: str, tier: str, model_id: str):
        self.models.setdefault(provider, {})[tier] = model_id
        self.save()

    def model_for(self, provider: str, tier: str) -> str:
        """Modele configure pour ce niveau, sinon choix automatique."""
        chosen = self.models.get(provider, {}).get(tier)
        if chosen:
            return chosen
        return self._auto_model(provider, tier)

    def _auto_model(self, provider: str, tier: str) -> str:
        """Selectionne un modele plausible parmi ceux disponibles."""
        models = self.available_models(provider)
        if not models:
            cfg = PROVIDERS.get(provider)
            return cfg.fallback_models[0] if cfg and cfg.fallback_models else ""

        by_tier: dict[str, list[str]] = {TIER_FAST: [], TIER_STANDARD: [], TIER_BEST: []}
        for m in models:
            by_tier[guess_tier(m.id)].append(m.id)

        # On descend d'un cran plutot que de rester sans modele.
        order = {TIER_FAST: (TIER_FAST, TIER_STANDARD, TIER_BEST),
                 TIER_STANDARD: (TIER_STANDARD, TIER_FAST, TIER_BEST),
                 TIER_BEST: (TIER_BEST, TIER_STANDARD, TIER_FAST)}[tier]
        for candidate_tier in order:
            if by_tier[candidate_tier]:
                return sorted(by_tier[candidate_tier])[0]
        return models[0].id

    # ------------------------------------------------------------------
    # Routage
    # ------------------------------------------------------------------
    def resolve(self, task: str) -> tuple[str, str]:
        """Retourne (fournisseur, modele) pour une tache donnee.

        `task` vaut "autocomplete", "edit" ou "heavy".
        """
        tier = PROFILES.get(self.profile, PROFILES[DEFAULT_PROFILE]).get(task)
        if tier is None:
            return "", ""              # la tache est desactivee dans ce profil

        provider = self.active_provider
        if self.privacy_mode or self.document_private:
            provider = "ollama"
        elif provider not in self.configured_providers():
            available = self.configured_providers()
            provider = available[0] if available else ""
        if not provider:
            return "", ""
        return provider, self.model_for(provider, tier)

    def requires_consent(self, task: str = "edit") -> bool:
        """True si l'action va envoyer du texte vers un service distant sans accord."""
        provider, _ = self.resolve(task)
        return bool(provider) and not is_local(provider) and not self.cloud_consent

    def is_task_enabled(self, task: str) -> bool:
        provider, model = self.resolve(task)
        return bool(provider and model)

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------
    def complete(self, messages: list[Message], *, task: str = "edit",
                 stream: bool = False, on_chunk=None,
                 json_schema: dict | None = None,
                 temperature: float = 0.2, max_tokens: int | None = None,
                 cancel: CancelToken | None = None,
                 read_timeout: int = 180) -> ChatResult:
        """Genere du texte, avec repli local si le cloud echoue."""
        provider, model = self.resolve(task)
        if not provider or not model:
            raise LLMError(
                "Aucune IA n'est configuree.\n"
                "Ouvrez Options ▸ Intelligence artificielle pour en connecter une."
            )

        try:
            result = self._run(provider, model, messages, stream, on_chunk,
                               json_schema, temperature, max_tokens, cancel,
                               read_timeout)
        except (NetworkError, QuotaError) as exc:
            # Le cloud est indisponible : on tente le local plutot que d'echouer.
            if (self.fallback_local and not is_local(provider)
                    and self.is_ollama_running()):
                self.last_error = f"{exc.user_message}\n→ Repli sur Ollama (local)."
                fallback_model = self.model_for("ollama", TIER_STANDARD)
                if fallback_model:
                    result = self._run("ollama", fallback_model, messages, stream,
                                       on_chunk, json_schema, temperature,
                                       max_tokens, cancel, read_timeout)
                    self._track(result)
                    return result
            raise

        self._track(result)
        return result

    def _run(self, provider, model, messages, stream, on_chunk, json_schema,
             temperature, max_tokens, cancel, read_timeout) -> ChatResult:
        client = self.client_for(provider)
        return client.chat(
            messages, model, stream=stream, on_chunk=on_chunk,
            json_schema=json_schema if PROVIDERS[provider].supports_json_schema or json_schema else None,
            temperature=temperature, max_tokens=max_tokens,
            cancel=cancel, read_timeout=read_timeout,
        )

    # ------------------------------------------------------------------
    # Consommation
    # ------------------------------------------------------------------
    def _track(self, result: ChatResult):
        with self._lock:
            self.session_usage = self.session_usage + result.usage
            self.session_cost += self.estimate_cost(result.provider, result.usage)

    @staticmethod
    def estimate_cost(provider: str, usage: Usage) -> float:
        """Cout indicatif en euros. Ordre de grandeur, pas une facture."""
        cfg = PROVIDERS.get(provider)
        if not cfg:
            return 0.0
        price_in, price_out = cfg.price_hint
        return (usage.prompt_tokens * price_in
                + usage.completion_tokens * price_out) / 1_000_000

    def status_label(self) -> str:
        """Texte compact pour la barre d'etat : « ChatGPT · 0,03 € »."""
        provider, model = self.resolve("edit")
        if not provider:
            return "IA non configurée"
        cfg = PROVIDERS[provider]
        if is_local(provider):
            if self.document_private and not self.privacy_mode:
                return f"{cfg.label} · document privé"
            return f"{cfg.label} · local"
        if self.session_cost >= 0.01:
            return f"{cfg.label} · {self.session_cost:.2f} €"
        return f"{cfg.label} · < 0,01 €"

    def over_budget(self) -> bool:
        return self.budget_alert > 0 and self.session_cost >= self.budget_alert

    def reset_usage(self):
        with self._lock:
            self.session_usage = Usage()
            self.session_cost = 0.0
