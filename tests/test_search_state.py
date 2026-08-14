"""Tests de la recherche et du remplacement."""

import pytest

from models.search_state import SearchState


def make(query, **options):
    s = SearchState()
    s.query = query
    for key, value in options.items():
        setattr(s, key, value)
    return s


# ---------------------------------------------------------------------------
# Recherche
# ---------------------------------------------------------------------------

def test_recherche_litterale_insensible_a_la_casse():
    s = make("chat")
    s.search("Le Chat et le chat")
    assert len(s.matches) == 2


def test_recherche_sensible_a_la_casse():
    s = make("Chat", case_sensitive=True)
    s.search("Le Chat et le chat")
    assert len(s.matches) == 1


def test_mot_entier():
    s = make("chat", whole_word=True)
    s.search("chat chatons chat")
    assert len(s.matches) == 2


def test_caracteres_speciaux_echappes_hors_mode_regex():
    s = make("a.c")
    s.search("abc a.c")
    assert len(s.matches) == 1          # « abc » ne doit pas correspondre


def test_regex_invalide_ne_leve_pas():
    s = make("[unclosed", use_regex=True)
    s.search("peu importe")
    assert s.matches == []


def test_navigation_circulaire():
    s = make("a")
    s.search("aaa")
    assert s.current_index == 0
    s.go_next(); s.go_next(); s.go_next()
    assert s.current_index == 0
    s.go_prev()
    assert s.current_index == 2


# ---------------------------------------------------------------------------
# Remplacement
# ---------------------------------------------------------------------------

def test_remplacer_tout():
    s = make("chat")
    s.replacement = "chien"
    text, count = s.replace_all("le chat et le chat")
    assert text == "le chien et le chien"
    assert count == 2


def test_remplacer_tout_sans_correspondance():
    s = make("licorne")
    s.replacement = "cheval"
    text, count = s.replace_all("le chat")
    assert (text, count) == ("le chat", 0)


def test_remplacer_courant_avance_a_la_suivante():
    s = make("a")
    s.replacement = "b"
    text, replaced = s.replace_current("aaa")
    assert (text, replaced) == ("baa", True)
    # Le curseur logique doit être sur un « a » restant, pas sur le « b ».
    start, _ = s.matches[s.current_index]
    assert text[start] == "a"


def test_remplacement_repete_termine_le_travail():
    s = make("x")
    s.replacement = "y"
    text = "xxx"
    for _ in range(3):
        text, ok = s.replace_current(text)
        if not ok:
            break
    assert text == "yyy"


def test_references_arriere_en_mode_regex():
    s = make(r"(\w+)@(\w+)", use_regex=True)
    s.replacement = r"\2 chez \1"
    text, count = s.replace_all("alice@exemple")
    assert text == "exemple chez alice"
    assert count == 1


def test_backslash_litteral_hors_mode_regex():
    """Hors regex, « \\1 » tapé par l'utilisateur doit rester tel quel."""
    s = make("cible")
    s.replacement = r"\1"
    text, _ = s.replace_all("la cible")
    assert text == r"la \1"


def test_remplacement_par_chaine_plus_longue_ne_boucle_pas():
    """Piège classique : remplacer « a » par « aa » peut créer une boucle
    infinie si la recherche repart du même endroit."""
    s = make("a")
    s.replacement = "aa"
    text, count = s.replace_all("aaa")
    assert text == "aaaaaa"
    assert count == 3


def test_reset_ferme_aussi_le_panneau_de_remplacement():
    s = make("a", replace_visible=True)
    s.search("aaa")
    s.reset()
    assert not s.visible and not s.replace_visible and s.matches == []
