"""
models/llm/json_parse.py — Extraction tolerante d'un objet JSON.

Avec un fournisseur supportant le mode strict (`json_schema`), ce module ne
sert jamais : la reponse est deja conforme. Il reste indispensable pour
Ollama et pour les petits modeles locaux, qui encadrent volontiers leur
JSON de texte explicatif ou de blocs Markdown.
"""

import json
import re

_FENCE_RE = re.compile(r"```(?:json)?", re.IGNORECASE)


def extract_json(text: str) -> dict | None:
    """Retourne le premier objet JSON valide trouve, ou None.

    Le parcours suit la profondeur des accolades en tenant compte des
    chaines et des echappements : une accolade a l'interieur d'une chaine
    ne fausse pas le comptage.
    """
    if not text:
        return None

    text = _FENCE_RE.sub("", text).replace("\r", "").strip()
    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escape_next = False

    for i in range(start, len(text)):
        ch = text[i]
        if escape_next:
            escape_next = False
            continue
        if ch == "\\":
            if in_string:
                escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                candidate = text[start:i + 1]
                parsed = _try_load(candidate)
                if parsed is not None:
                    return parsed
                # Un objet complet mais invalide : on continue a chercher
                # un autre bloc plus loin dans la reponse.
                start = text.find("{", i + 1)
                if start == -1:
                    return None
                depth = 0
    return None


def _try_load(candidate: str) -> dict | None:
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        parsed = _try_load_repaired(candidate)
    return parsed if isinstance(parsed, dict) else None


def _try_load_repaired(candidate: str) -> dict | None:
    """Repare les defauts les plus frequents des petits modeles."""
    # Retours a la ligne bruts a l'interieur d'une chaine JSON.
    repaired = re.sub(
        r'"(?:[^"\\]|\\.)*"',
        lambda m: m.group(0).replace("\n", "\\n").replace("\t", "\\t"),
        candidate,
        flags=re.DOTALL,
    )
    # Virgules terminales : {"a": 1,} ou [1, 2,]
    repaired = re.sub(r",\s*([}\]])", r"\1", repaired)
    try:
        parsed = json.loads(repaired)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None
