"""Tests de la coloration syntaxique."""

import pytest

from models.syntax import (COMMENT, HEADING, KEY, KEYWORD, NUMBER, STRING,
                           detect_language, highlight, language_label)


def kinds(text, language):
    return [k for _, _, k in highlight(text, language)]


def slices(text, language):
    return [(text[s:e], k) for s, e, k in highlight(text, language)]


# ---------------------------------------------------------------------------
# Détection du langage
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name, expected", [
    ("script.py", "python"),
    ("data.json", "json"),
    ("notes.md", "markdown"),
    ("config.yaml", "config"),
    ("app.js", "clike"),
    ("query.sql", "sql"),
])
def test_detection_par_extension(name, expected):
    language = detect_language(name)
    assert language is not None and language.name == expected


def test_extension_inconnue_ou_absente():
    assert detect_language("notes.txt") is None
    assert detect_language(None) is None
    assert detect_language("") is None


def test_libelle_langage():
    assert language_label(None) == "Texte"
    assert language_label(detect_language("a.py")) == "Python"


# ---------------------------------------------------------------------------
# Invariant fondamental : les segments ne se chevauchent jamais
# ---------------------------------------------------------------------------

SAMPLES = {
    "a.py": '# commentaire\ndef salut(nom="monde"):\n    return len(nom) + 42\n',
    "a.json": '{"nom": "Arnaud", "age": 30, "actif": true, "note": null}',
    "a.md": "# Titre\n\nDu **gras**, de l'*italique*, du `code`.\n\n- item\n> citation\n",
    "a.yaml": "# config\nnom: Carib\nversion: 0.12\nactif: true\n[section]\n",
    "a.js": "// note\nfunction f(x) { return `v${x}`; }\n",
    "a.sql": "-- requête\nSELECT nom FROM users WHERE age > 30;",
}


@pytest.mark.parametrize("name, text", SAMPLES.items())
def test_segments_tries_et_sans_chevauchement(name, text):
    segments = highlight(text, detect_language(name))
    assert segments, f"aucun segment pour {name}"
    last = 0
    for start, end, _ in segments:
        assert 0 <= start < end <= len(text)
        assert start >= last, "chevauchement de segments"
        last = end


@pytest.mark.parametrize("name, text", SAMPLES.items())
def test_le_texte_est_reconstructible(name, text):
    """La vue parcourt les segments pour bâtir ses spans : la concaténation
    des zones colorées et non colorées doit redonner le texte exact."""
    segments = highlight(text, detect_language(name))
    out, cursor = [], 0
    for start, end, _ in segments:
        out.append(text[cursor:start])
        out.append(text[start:end])
        cursor = end
    out.append(text[cursor:])
    assert "".join(out) == text


# ---------------------------------------------------------------------------
# Priorités : chaînes et commentaires avant tout le reste
# ---------------------------------------------------------------------------

def test_mot_cle_dans_une_chaine_nest_pas_colore_comme_mot_cle():
    text = 'x = "def class return"'
    found = slices(text, detect_language("a.py"))
    assert ('"def class return"', STRING) in found
    assert not any(k == KEYWORD for _, k in found)


def test_mot_cle_dans_un_commentaire_nest_pas_colore():
    text = "# import return def\nx = 1"
    found = slices(text, detect_language("a.py"))
    assert ("# import return def", COMMENT) in found
    assert not any(k == KEYWORD for _, k in found)


def test_chaines_triples_python():
    text = 'a = """ligne 1\nligne 2"""\n'
    found = slices(text, detect_language("a.py"))
    assert any(k == STRING and t.startswith('"""') for t, k in found)


def test_cles_json_distinguees_des_valeurs():
    found = slices(SAMPLES["a.json"], detect_language("a.json"))
    assert ('"nom"', KEY) in found
    assert ('"Arnaud"', STRING) in found
    assert any(k == NUMBER for _, k in found)


def test_titres_markdown():
    found = slices("# Grand titre\ntexte\n## Sous-titre\n", detect_language("a.md"))
    assert any(k == HEADING and t.startswith("#") for t, k in found)


def test_bloc_de_code_markdown_prime_sur_le_reste():
    text = "```\n# ceci n'est pas un titre\n```\n"
    found = slices(text, detect_language("a.md"))
    assert found and found[0][1] == STRING
    assert not any(k == HEADING for _, k in found)


# ---------------------------------------------------------------------------
# Robustesse
# ---------------------------------------------------------------------------

def test_texte_vide_ou_sans_langage():
    assert highlight("", detect_language("a.py")) == []
    assert highlight("du texte", None) == []


def test_gros_fichier_tronque_mais_sans_erreur():
    import models.syntax as syn
    text = ('x = 1  # note\n' * 20_000)
    segments = highlight(text, detect_language("a.py"))
    assert segments
    assert segments[-1][1] <= syn.MAX_HIGHLIGHT_CHARS


def test_code_non_termine_ne_plante_pas():
    """Un fichier en cours de frappe est presque toujours syntaxiquement
    invalide : l'analyseur doit rester silencieux."""
    for text in ('def f(:\n  "chaine non fermee', "{'a': ", "```\nbloc ouvert",
                 "/* commentaire non ferme"):
        for name in ("a.py", "a.json", "a.md", "a.js"):
            highlight(text, detect_language(name))       # ne doit pas lever
