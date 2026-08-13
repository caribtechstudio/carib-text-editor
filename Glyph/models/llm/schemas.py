"""
models/llm/schemas.py — Schemas JSON stricts pour les modes IA.

Avec un fournisseur qui supporte `json_schema` en mode strict (OpenAI,
Gemini), la reponse est **garantie** conforme : plus de rattrapage a coups
d'expressions regulieres, plus de message « la reponse du modele n'est pas
valide ». Pour les autres (Ollama, Anthropic), le schema reste utile comme
documentation et le parseur tolerant prend le relais.

Contraintes du mode strict : chaque objet doit declarer `additionalProperties:
false` et lister **toutes** ses proprietes dans `required`.
"""


def _obj(properties: dict, required: list[str]) -> dict:
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


_STR = {"type": "string"}
_STR_LIST = {"type": "array", "items": {"type": "string"}}

_CORRECTION_ITEM = _obj(
    {
        "original": {**_STR, "description": "Extrait fautif, copie mot pour mot du texte source."},
        "correction": {**_STR, "description": "Version corrigee de cet extrait."},
        "type": {"type": "string",
                 "enum": ["orthographe", "grammaire", "conjugaison",
                          "accord", "ponctuation"]},
        "explication": {**_STR, "description": "Raison, 8 mots maximum."},
    },
    ["original", "correction", "type", "explication"],
)

_SUGGESTION_ITEM = _obj(
    {
        "original": _STR,
        "suggestion": _STR,
        "type": {"type": "string", "enum": ["synonyme", "reformulation"]},
        "explication": _STR,
    },
    ["original", "suggestion", "type", "explication"],
)

SCHEMAS: dict[str, dict] = {
    "correction": {
        "name": "correction",
        "schema": _obj(
            {
                "corrections": {"type": "array", "items": _CORRECTION_ITEM},
                "suggestions": {"type": "array", "items": _SUGGESTION_ITEM},
                "score": {"type": "integer", "minimum": 0, "maximum": 100},
            },
            ["corrections", "suggestions", "score"],
        ),
    },
    "translate_fr_en": {
        "name": "traduction",
        "schema": _obj({"translation": _STR, "notes": _STR_LIST},
                       ["translation", "notes"]),
    },
    "reformulate": {
        "name": "reformulation",
        "schema": _obj({"result": _STR, "changes": _STR_LIST},
                       ["result", "changes"]),
    },
    "summarize": {
        "name": "resume",
        "schema": _obj(
            {"result": _STR, "key_points": _STR_LIST, "reduction": _STR},
            ["result", "key_points", "reduction"],
        ),
    },
    "keywords": {
        "name": "mots_cles",
        "schema": _obj(
            {"theme": _STR, "primary_keywords": _STR_LIST,
             "secondary_keywords": _STR_LIST},
            ["theme", "primary_keywords", "secondary_keywords"],
        ),
    },
}

# Modes partageant la meme forme de reponse.
SCHEMAS["translate_en_fr"] = SCHEMAS["translate_fr_en"]
SCHEMAS["natural"] = SCHEMAS["reformulate"]
SCHEMAS["professional"] = SCHEMAS["reformulate"]

#: Niveau de modele adapte a chaque mode (voir manager.PROFILES).
MODE_TASKS: dict[str, str] = {
    "correction": "edit",
    "translate_fr_en": "edit",
    "translate_en_fr": "edit",
    "reformulate": "edit",
    "natural": "edit",
    "professional": "edit",
    "summarize": "heavy",
    "keywords": "edit",
}


def schema_for(mode: str) -> dict | None:
    return SCHEMAS.get(mode)


def task_for(mode: str) -> str:
    return MODE_TASKS.get(mode, "edit")
