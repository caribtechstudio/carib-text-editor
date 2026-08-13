"""Tests de la couche LLM : parsing tolérant, routage, coût."""

import pytest

from models.llm.base import Usage
from models.llm.json_parse import extract_json
from models.llm.manager import TIER_BEST, TIER_FAST, TIER_STANDARD, guess_tier
from models.llm.registry import PROVIDER_ORDER, PROVIDERS, is_local
from models.llm.schemas import SCHEMAS, schema_for, task_for


# ---------------------------------------------------------------------------
# Parsing tolérant (indispensable pour les petits modèles locaux)
# ---------------------------------------------------------------------------

def test_json_propre():
    assert extract_json('{"a": 1}') == {"a": 1}


def test_json_dans_un_bloc_markdown():
    raw = 'Voici le résultat :\n```json\n{"score": 90}\n```\nVoilà.'
    assert extract_json(raw) == {"score": 90}


def test_accolade_dans_une_chaine_ne_fausse_pas_le_comptage():
    assert extract_json('{"texte": "un } piégeux", "ok": true}') == {
        "texte": "un } piégeux", "ok": True}


def test_guillemet_echappe():
    assert extract_json(r'{"citation": "il a dit \"oui\""}') == {
        "citation": 'il a dit "oui"'}


def test_virgule_terminale_reparee():
    assert extract_json('{"a": 1, "b": 2,}') == {"a": 1, "b": 2}


def test_retour_ligne_brut_dans_une_chaine_repare():
    result = extract_json('{"texte": "ligne 1\nligne 2"}')
    assert result is not None
    assert "ligne 1" in result["texte"]


def test_texte_sans_json_retourne_none():
    assert extract_json("désolé, je ne peux pas répondre") is None
    assert extract_json("") is None


def test_tableau_racine_rejete():
    """Le contrat est un objet ; un tableau n'est pas exploitable."""
    assert extract_json("[1, 2, 3]") is None


# ---------------------------------------------------------------------------
# Registre
# ---------------------------------------------------------------------------

def test_tous_les_fournisseurs_declarent_le_minimum():
    for key, cfg in PROVIDERS.items():
        assert cfg.key == key
        assert cfg.base_url.startswith("http")
        assert cfg.label


def test_ollama_est_le_seul_local():
    assert is_local("ollama")
    assert not is_local("openai")
    assert not is_local("anthropic")
    assert not is_local("gemini")


def test_ordre_daffichage_couvre_tous_les_fournisseurs():
    assert set(PROVIDER_ORDER) == set(PROVIDERS)


# ---------------------------------------------------------------------------
# Niveaux de modèle
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("model_id, expected", [
    ("gpt-4.1-nano", TIER_FAST),
    ("gpt-4.1-mini", TIER_FAST),
    ("claude-haiku-4-5", TIER_FAST),
    ("gemini-2.0-flash-lite", TIER_FAST),
    ("llama3.2:1b", TIER_FAST),
    ("gpt-4.1", TIER_STANDARD),
    ("claude-opus-4", TIER_BEST),
    ("gemini-2.5-pro", TIER_BEST),
])
def test_deduction_du_niveau(model_id, expected):
    assert guess_tier(model_id) == expected


# ---------------------------------------------------------------------------
# Schémas JSON stricts
# ---------------------------------------------------------------------------

def test_schemas_conformes_au_mode_strict():
    """OpenAI exige additionalProperties=false et required exhaustif."""
    def check(node):
        if not isinstance(node, dict):
            return
        if node.get("type") == "object":
            assert node.get("additionalProperties") is False
            assert set(node.get("required", [])) == set(node.get("properties", {}))
        for value in node.values():
            if isinstance(value, dict):
                check(value)
            elif isinstance(value, list):
                for item in value:
                    check(item)

    for name, schema in SCHEMAS.items():
        check(schema["schema"])


def test_chaque_mode_ia_a_un_schema_et_une_tache():
    modes = ["correction", "translate_fr_en", "translate_en_fr", "reformulate",
             "natural", "professional", "summarize", "keywords"]
    for mode in modes:
        assert schema_for(mode) is not None, mode
        assert task_for(mode) in ("edit", "heavy", "autocomplete"), mode


# ---------------------------------------------------------------------------
# Consommation
# ---------------------------------------------------------------------------

def test_addition_des_usages():
    total = Usage(10, 5) + Usage(3, 2)
    assert (total.prompt_tokens, total.completion_tokens) == (13, 7)
    assert total.total_tokens == 20


def test_ollama_est_gratuit():
    from models.llm.manager import LLMManager
    assert LLMManager.estimate_cost("ollama", Usage(1_000_000, 1_000_000)) == 0.0


def test_cout_cloud_positif_et_proportionnel():
    from models.llm.manager import LLMManager
    petit = LLMManager.estimate_cost("openai", Usage(1000, 1000))
    grand = LLMManager.estimate_cost("openai", Usage(10_000, 10_000))
    assert 0 < petit < grand
