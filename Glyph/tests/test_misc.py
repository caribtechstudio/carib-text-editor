"""Tests du diff, de la palette, du dictionnaire local et de la calculatrice."""

import pytest

from models.calculator import eval_safe
from models.word_completer import WordCompleter
from views.command_palette import Command, fuzzy_filter
from views.diff_view import compute_diff, diff_stats


# ---------------------------------------------------------------------------
# Diff inline
# ---------------------------------------------------------------------------

def rebuild(original, segments):
    """Reconstruit le texte proposé à partir des segments du diff."""
    return "".join(t for k, t in segments if k in ("=", "+"))


def restore(original, segments):
    """Reconstruit le texte d'origine à partir des segments du diff."""
    return "".join(t for k, t in segments if k in ("=", "-"))


@pytest.mark.parametrize("before, after", [
    ("bonjour le monde", "bonsoir le monde"),
    ("", "du texte tout neuf"),
    ("du texte à supprimer", ""),
    ("identique", "identique"),
    ("Le chat mange.", "Le chien mange lentement."),
    ("a" * 3000, "a" * 2999 + "b"),          # bascule en diff par mots
])
def test_le_diff_est_reversible(before, after):
    """Propriété fondamentale : les segments doivent permettre de
    reconstruire exactement les deux versions."""
    segments = compute_diff(before, after)
    assert restore(before, segments) == before
    assert rebuild(before, segments) == after


def test_segments_consecutifs_fusionnes():
    segments = compute_diff("abc", "xyz")
    kinds = [k for k, _ in segments]
    assert kinds == list(dict.fromkeys(kinds)) or all(
        kinds[i] != kinds[i + 1] for i in range(len(kinds) - 1))


def test_statistiques_du_diff():
    segments = compute_diff("abc", "abcdef")
    added, removed = diff_stats(segments)
    assert (added, removed) == (3, 0)


def test_texte_identique_ne_produit_aucun_changement():
    added, removed = diff_stats(compute_diff("pareil", "pareil"))
    assert (added, removed) == (0, 0)


# ---------------------------------------------------------------------------
# Palette de commandes
# ---------------------------------------------------------------------------

def commands():
    return [
        Command("a", "Enregistrer", lambda: None, "Fichier", "Ctrl+S"),
        Command("b", "Enregistrer sous", lambda: None, "Fichier", "Ctrl+Maj+S"),
        Command("c", "Rechercher et remplacer", lambda: None, "Édition", "Ctrl+H"),
        Command("d", "Mode Lecture", lambda: None, "Affichage", "Ctrl+3"),
    ]


def test_requete_vide_retourne_tout():
    assert len(fuzzy_filter(commands(), "")) == 4


def test_correspondance_exacte_prioritaire():
    results = fuzzy_filter(commands(), "remplacer")
    assert results[0].id == "c"


def test_recherche_par_sous_sequence():
    """« rmp » doit trouver « Rechercher et reMPlacer »."""
    results = fuzzy_filter(commands(), "rmp")
    assert any(cmd.id == "c" for cmd in results)


def test_recherche_dans_le_groupe():
    results = fuzzy_filter(commands(), "fichier")
    assert {cmd.id for cmd in results} == {"a", "b"}


def test_requete_sans_correspondance():
    assert fuzzy_filter(commands(), "zzzzqqqq") == []


# ---------------------------------------------------------------------------
# Dictionnaire local
# ---------------------------------------------------------------------------

def test_completion_apprend_les_mots_du_document():
    wc = WordCompleter()
    wc.update_from_text("anticonstitutionnellement est un mot long")
    assert "anticonstitutionnellement" in wc.complete("anticons")


def test_completion_exclut_le_prefixe_exact():
    wc = WordCompleter()
    wc.update_from_text("bonjour bonjours")
    assert "bonjour" not in wc.complete("bonjour")


def test_completion_triee_par_frequence():
    wc = WordCompleter()
    wc.update_from_text("test " * 10 + "testament " + "tessiture")
    assert wc.complete("tes")[0] == "test"


def test_prefixe_trop_court_ne_propose_rien():
    wc = WordCompleter()
    wc.update_from_text("beaucoup de mots ici")
    assert wc.complete("b") == []


def test_reindexation_identique_est_ignoree():
    """Le dictionnaire est reconstruit toutes les 2 s ; refaire le travail
    pour un texte inchangé serait du CPU gaspillé pendant la frappe."""
    wc = WordCompleter()
    text = "du contenu stable"
    wc.update_from_text(text)
    signature = wc._last_signature
    wc.update_from_text(text)
    assert wc._last_signature is signature or wc._last_signature == signature


# ---------------------------------------------------------------------------
# Calculatrice
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("expression", [
    "__import__('os').system('echo nope')",
    "open('/etc/passwd')",
    "().__class__.__bases__",
    "eval('1+1')",
])
def test_la_calculatrice_refuse_le_code_arbitraire(expression):
    """Le parser AST ne doit jamais exécuter autre chose que de l'arithmétique."""
    result = eval_safe(expression)
    assert "Erreur" in result or result == "" or "erreur" in result.lower()


@pytest.mark.parametrize("expression, expected", [
    ("2+2", "4"),
    ("10/4", "2.5"),
    ("2*3+1", "7"),
])
def test_arithmetique_de_base(expression, expected):
    assert expected in eval_safe(expression)
