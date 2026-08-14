"""
models/llm/base.py — Types et erreurs partages par tous les fournisseurs.

Les erreurs portent un `user_message` redige en francais et actionnable :
l'interface ne doit jamais avoir a interpreter un code HTTP.
"""

from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Types de donnees
# ---------------------------------------------------------------------------

@dataclass
class Message:
    """Un tour de conversation."""

    role: str          # "system" | "user" | "assistant"
    content: str

    def to_dict(self) -> dict:
        return {"role": self.role, "content": self.content}


@dataclass
class Usage:
    """Consommation de jetons d'une requete."""

    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def __add__(self, other: "Usage") -> "Usage":
        return Usage(self.prompt_tokens + other.prompt_tokens,
                     self.completion_tokens + other.completion_tokens)


@dataclass
class ModelInfo:
    """Un modele propose par un fournisseur."""

    id: str
    label: str = ""
    provider: str = ""

    def __post_init__(self):
        if not self.label:
            self.label = self.id


@dataclass
class ChatResult:
    """Resultat complet d'un appel."""

    text: str = ""
    usage: Usage = field(default_factory=Usage)
    model: str = ""
    provider: str = ""
    elapsed: float = 0.0


# ---------------------------------------------------------------------------
# Erreurs
# ---------------------------------------------------------------------------

class LLMError(Exception):
    """Erreur de base. `user_message` est directement affichable."""

    def __init__(self, user_message: str, detail: str = ""):
        super().__init__(detail or user_message)
        self.user_message = user_message
        self.detail = detail


class AuthError(LLMError):
    """Clé absente, invalide ou révoquée."""


class RateLimitError(LLMError):
    """Trop de requêtes — réessayable après `retry_after` secondes."""

    def __init__(self, user_message: str, detail: str = "", retry_after: float = 0.0):
        super().__init__(user_message, detail)
        self.retry_after = retry_after


class QuotaError(LLMError):
    """Crédit épuisé ou plafond de facturation atteint."""


class NetworkError(LLMError):
    """Serveur injoignable, DNS, TLS, délai dépassé."""


class ModelError(LLMError):
    """Modèle inconnu, indisponible, ou requête refusée."""


class CancelledError(LLMError):
    """L'utilisateur a interrompu la generation."""

    def __init__(self):
        super().__init__("Génération interrompue.")
