"""
models/llm/registry.py — Catalogue des fournisseurs.

Ajouter un fournisseur = ajouter une entree ici. Aucune autre partie du code
ne connait les specificites d'OpenAI, d'Anthropic, de Google ou d'Ollama.

Note importante sur les modeles : la liste `fallback_models` n'est qu'un
filet de securite hors ligne. En fonctionnement normal, Glyph interroge
`GET {base_url}/models` et affiche ce que le compte de l'utilisateur peut
reellement utiliser. C'est ce qui evite qu'une liste codee en dur ne
perime — le defaut de l'ancien catalogue Ollama de Glyph.
"""

from dataclasses import dataclass, field


@dataclass
class ProviderConfig:
    """Tout ce qui distingue un fournisseur d'un autre."""

    key: str
    label: str
    base_url: str
    #: Le fournisseur exige-t-il une cle API ?
    needs_key: bool = True
    #: Supporte `response_format={"type": "json_schema"}` en mode strict.
    supports_json_schema: bool = False
    #: Icone SVG (fichier de ressource/icon/, sans extension).
    icon: str = "user-robot"
    #: Phrase affichee dans le dialogue de connexion.
    tagline: str = ""
    #: Page ou l'utilisateur obtient sa cle.
    key_url: str = ""
    #: A quoi ressemble une cle valide (verification locale, avant tout appel).
    key_prefix: str = ""
    #: En-tetes supplementaires propres au fournisseur.
    extra_headers: dict = field(default_factory=dict)
    #: Utilise si l'appel a /models echoue.
    fallback_models: tuple = ()
    #: Modeles a masquer (embeddings, audio, images — inutiles ici).
    hide_patterns: tuple = ()
    #: Cout indicatif en euros par million de jetons (entree, sortie).
    #: Sert uniquement a afficher un ordre de grandeur a l'utilisateur.
    price_hint: tuple = (0.0, 0.0)


PROVIDERS: dict[str, ProviderConfig] = {
    "openai": ProviderConfig(
        key="openai",
        label="ChatGPT",
        base_url="https://api.openai.com/v1",
        supports_json_schema=True,
        icon="sparkles",
        tagline="Le plus polyvalent. Excellent en francais.",
        key_url="https://platform.openai.com/api-keys",
        key_prefix="sk-",
        fallback_models=("gpt-4.1-mini", "gpt-4.1-nano", "gpt-4.1", "gpt-4o-mini"),
        hide_patterns=("embedding", "whisper", "tts", "dall-e", "audio",
                       "moderation", "realtime", "image"),
        price_hint=(0.35, 1.40),
    ),
    "anthropic": ProviderConfig(
        key="anthropic",
        label="Claude",
        base_url="https://api.anthropic.com/v1",
        supports_json_schema=False,
        icon="badge-check",
        tagline="Tres bon redacteur, nuances du francais.",
        key_url="https://console.anthropic.com/settings/keys",
        key_prefix="sk-ant-",
        # L'endpoint compatible OpenAI d'Anthropic accepte « Authorization:
        # Bearer », mais l'API native exige ces deux en-tetes : les envoyer
        # systematiquement rend les deux chemins fonctionnels.
        extra_headers={"anthropic-version": "2023-06-01"},
        fallback_models=("claude-haiku-4-5-20251001",),
        hide_patterns=(),
        price_hint=(0.80, 4.00),
    ),
    "gemini": ProviderConfig(
        key="gemini",
        label="Gemini",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        supports_json_schema=True,
        icon="bolt",
        tagline="Palier gratuit genereux.",
        key_url="https://aistudio.google.com/apikey",
        key_prefix="",
        fallback_models=("gemini-2.0-flash", "gemini-2.0-flash-lite"),
        hide_patterns=("embedding", "aqa", "imagen", "veo", "tts"),
        price_hint=(0.10, 0.40),
    ),
    "ollama": ProviderConfig(
        key="ollama",
        label="Ollama (local)",
        base_url="http://localhost:11434/v1",
        needs_key=False,
        supports_json_schema=False,
        icon="shield-check",
        tagline="100 % hors ligne. Aucune donnee ne quitte votre ordinateur.",
        key_url="https://ollama.com/download",
        fallback_models=(),
        price_hint=(0.0, 0.0),
    ),
}

#: Ordre d'affichage dans le dialogue de connexion.
PROVIDER_ORDER = ("openai", "anthropic", "gemini", "ollama")

DEFAULT_PROVIDER = "openai"


def get_provider(key: str) -> ProviderConfig | None:
    return PROVIDERS.get(key)


def is_local(provider_key: str) -> bool:
    """Un fournisseur local ne fait sortir aucune donnee de la machine."""
    cfg = PROVIDERS.get(provider_key)
    return bool(cfg and not cfg.needs_key)
