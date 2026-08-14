"""
Tests des primitives centrées sur le curseur.

Ces fonctions corrigent le bug le plus visible de l'application : l'ancienne
implémentation cherchait « le dernier mot du document » au lieu du mot situé
sous le curseur, ce qui cassait l'autocomplétion, le remplacement d'emoji et
le mode calcul dès qu'on écrivait ailleurs qu'à la fin du fichier.
"""

from models.text_utils import (clamp_cursor, count_words, line_bounds_at_cursor,
                               line_col_at_cursor, replace_word_at_cursor,
                               word_before_cursor, word_bounds_at_cursor)


# ---------------------------------------------------------------------------
# Mot courant
# ---------------------------------------------------------------------------

def test_mot_avant_curseur_au_milieu_du_document():
    text = "bonjour le monde entier"
    #                  ^ curseur après « mon »
    assert word_before_cursor(text, 14) == "mon"


def test_mot_avant_curseur_ignore_la_fin_du_document():
    """Le cœur du bug : écrire au milieu ne doit pas proposer le dernier mot."""
    text = "premier mot ici et beaucoup de texte apres"
    assert word_before_cursor(text, 7) == "premier"
    assert word_before_cursor(text, 7) != "apres"


def test_mot_avant_curseur_vide_apres_une_espace():
    assert word_before_cursor("bonjour ", 8) == ""


def test_mot_avant_curseur_au_debut():
    assert word_before_cursor("abc", 0) == ""


def test_accents_et_apostrophes_font_partie_du_mot():
    assert word_before_cursor("aujourd'hui", 11) == "aujourd'hui"
    assert word_before_cursor("éléphant", 8) == "éléphant"


def test_bornes_du_mot_englobent_la_fin():
    text = "le chateau fort"
    # Curseur au milieu de « chateau »
    assert word_bounds_at_cursor(text, 6) == (3, 10)


def test_remplacement_au_curseur_remplace_le_mot_entier():
    text = "le chateu fort"
    new_text, cursor = replace_word_at_cursor(text, 6, "chateau")
    assert new_text == "le chateau fort"
    assert new_text[:cursor] == "le chateau"


def test_remplacement_nafffecte_pas_la_fin_du_document():
    text = "corrig ici, et corrig la-bas"
    new_text, _ = replace_word_at_cursor(text, 6, "corrige")
    assert new_text.startswith("corrige ici")
    assert new_text.endswith("corrig la-bas")      # l'autre occurrence intacte


# ---------------------------------------------------------------------------
# Lignes et colonnes
# ---------------------------------------------------------------------------

def test_ligne_colonne():
    text = "abc\ndefgh\nij"
    assert line_col_at_cursor(text, 0) == (1, 1)
    assert line_col_at_cursor(text, 3) == (1, 4)
    assert line_col_at_cursor(text, 4) == (2, 1)
    assert line_col_at_cursor(text, 7) == (2, 4)
    assert line_col_at_cursor(text, 10) == (3, 1)


def test_bornes_de_ligne():
    text = "abc\ndef\nghi"
    assert line_bounds_at_cursor(text, 5) == (4, 7)
    assert line_bounds_at_cursor(text, 0) == (0, 3)
    assert line_bounds_at_cursor(text, 10) == (8, 11)


def test_curseur_borne_dans_le_texte():
    assert clamp_cursor("abc", 99) == 3
    assert clamp_cursor("abc", -5) == 0
    assert clamp_cursor("abc", None) == 3


# ---------------------------------------------------------------------------
# Comptage
# ---------------------------------------------------------------------------

def test_comptage_de_mots():
    assert count_words("") == 0
    assert count_words("   ") == 0
    assert count_words("un deux trois") == 3
    assert count_words("aujourd'hui c'est bien") == 3
    assert count_words("ponctuation, ici ! oui ?") == 3
