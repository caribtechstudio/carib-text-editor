"""
models/llm — Couche d'abstraction des moteurs de langage.

Carib parle a ChatGPT, Claude, Gemini et Ollama a travers **un seul** client
HTTP. Les quatre exposent aujourd'hui un endpoint compatible avec le format
`/chat/completions` d'OpenAI : il suffit donc de changer l'URL de base et
l'en-tete d'authentification, sans embarquer quatre SDK (ce qui alourdirait
l'executable de plusieurs dizaines de megaoctets).

Point d'entree : `LLMManager` (models/llm/manager.py).
"""

from models.llm.base import (
    AuthError,
    CancelledError,
    LLMError,
    Message,
    ModelInfo,
    NetworkError,
    QuotaError,
    RateLimitError,
    Usage,
)
from models.llm.manager import LLMManager
from models.llm.registry import PROVIDERS, ProviderConfig

__all__ = [
    "AuthError", "CancelledError", "LLMError", "LLMManager", "Message",
    "ModelInfo", "NetworkError", "PROVIDERS", "ProviderConfig", "QuotaError",
    "RateLimitError", "Usage",
]
