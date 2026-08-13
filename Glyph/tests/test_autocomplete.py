"""
Tests de l'autocomplétion en texte fantôme.

Le point critique : la suggestion ne doit **jamais** entrer dans le document
tant que l'utilisateur ne l'a pas acceptée. Un bug ici insérerait du texte
que personne n'a écrit dans un fichier que l'utilisateur va enregistrer.
"""

import pytest

from controllers.autocomplete_controller import (SOURCE_AI, SOURCE_WORD,
                                                 AutocompleteController)
from models.document import Document
from models.editor_state import EditorState


class FakeEditor:
    def __init__(self):
        self.value = ""
        self.selection = None

    def focus(self):
        pass


class FakePage:
    def run_thread(self, fn):
        fn()

    def run_task(self, fn, *args):
        pass

    def update(self):
        pass


@pytest.fixture
def ac():
    state = EditorState()
    doc = Document(content="")
    state.docs = [doc]
    editor = FakeEditor()
    controller = AutocompleteController(
        state, editor, lambda: doc, lambda: None, FakePage(),
        refresh_fn=lambda: None, llm_ready_fn=lambda: False,
    )
    controller.doc = doc
    return controller


def type_text(ac, text, cursor=None):
    ac.doc.content = text
    ac.editor.value = text
    ac.on_text_changed(cursor if cursor is not None else len(text))


# ---------------------------------------------------------------------------
# Complétion locale
# ---------------------------------------------------------------------------

def test_le_dictionnaire_local_complete_le_mot_courant(ac):
    ac.update_trie_now("anticonstitutionnellement est un mot")
    type_text(ac, "antic")
    assert ac.state.ac_ghost == "onstitutionnellement"
    assert ac.state.ac_source == SOURCE_WORD


def test_prefixe_trop_court_ne_suggere_rien(ac):
    ac.update_trie_now("bonjour")
    type_text(ac, "b")
    assert ac.state.ac_ghost == ""


def test_aucune_suggestion_sans_correspondance(ac):
    ac.update_trie_now("bonjour monde")
    type_text(ac, "xyzzy")
    assert ac.state.ac_ghost == ""


# ---------------------------------------------------------------------------
# La suggestion reste hors du document
# ---------------------------------------------------------------------------

def test_la_suggestion_nentre_pas_dans_le_document(ac):
    ac.update_trie_now("bonjour")
    type_text(ac, "bonj")

    assert ac.state.ac_ghost == "our"
    # Ni le document ni le champ ne contiennent la proposition.
    assert ac.doc.content == "bonj"
    assert ac.editor.value == "bonj"


def test_echap_abandonne_sans_rien_modifier(ac):
    ac.update_trie_now("bonjour")
    type_text(ac, "bonj")
    ac.dismiss()

    assert ac.state.ac_ghost == ""
    assert not ac.state.ac_visible
    assert ac.doc.content == "bonj"


# ---------------------------------------------------------------------------
# Acceptation
# ---------------------------------------------------------------------------

def test_tab_accepte_toute_la_suggestion(ac):
    ac.update_trie_now("bonjour")
    type_text(ac, "bonj")

    assert ac.accept() is True
    assert ac.doc.content == "bonjour"
    assert ac.editor.value == "bonjour"
    assert ac.state.ac_ghost == ""


def test_acceptation_au_milieu_du_texte(ac):
    """L'insertion se fait au curseur, pas à la fin du document."""
    ac.update_trie_now("chateau")
    ac.doc.content = "le chat dort"
    ac.editor.value = ac.doc.content
    ac.on_text_changed(7)                    # curseur après « chat »

    if ac.state.ac_ghost:
        ac.accept()
        assert ac.doc.content.endswith(" dort")
        assert not ac.doc.content.startswith("le chat dortchateau")


def test_ctrl_droite_naccepte_quun_mot(ac):
    ac.state.ac_ghost = " le monde entier."
    ac.state.ac_source = SOURCE_AI
    ac.state.ac_visible = True
    ac.doc.content = "Bonjour"
    ac.editor.value = "Bonjour"
    ac._cursor = 7

    assert ac.accept_word() is True
    assert ac.doc.content == "Bonjour le"
    # Le reste de la proposition demeure disponible.
    assert ac.state.ac_ghost == " monde entier."
    assert ac.state.ac_visible


def test_acceptations_successives_mot_a_mot(ac):
    ac.state.ac_ghost = " un deux trois"
    ac.state.ac_source = SOURCE_AI
    ac.doc.content = "Debut"
    ac.editor.value = "Debut"
    ac._cursor = 5

    while ac.state.ac_ghost:
        assert ac.accept_word() is True
    assert ac.doc.content == "Debut un deux trois"


def test_accepter_sans_suggestion_ne_fait_rien(ac):
    ac.doc.content = "texte"
    assert ac.accept() is False
    assert ac.accept_word() is False
    assert ac.doc.content == "texte"


def test_lacceptation_est_annulable(ac):
    ac.update_trie_now("bonjour")
    type_text(ac, "bonj")
    ac.accept()

    assert ac.doc.content == "bonjour"
    assert ac.doc.undo() == "bonj"


# ---------------------------------------------------------------------------
# Prédiction par le modèle
# ---------------------------------------------------------------------------

def test_pas_de_prediction_sans_moteur(ac):
    type_text(ac, "Une phrase complete ")
    assert ac.state.ac_ghost == ""


def test_prediction_ignoree_si_un_mot_est_en_cours(ac):
    """Proposer une suite de phrase au milieu d'un mot n'a aucun sens."""
    ac._cursor = 4
    ac.doc.content = "mots"
    ac._on_ai_prediction("suite de phrase.")
    assert ac.state.ac_ghost == ""


def test_prediction_acceptee_en_fin_de_mot(ac):
    ac.doc.content = "Bonjour "
    ac._cursor = 8
    ac._on_ai_prediction("comment allez-vous ?")
    assert ac.state.ac_ghost == "comment allez-vous ?"
    assert ac.state.ac_source == SOURCE_AI


def test_autocompletion_desactivee(ac):
    ac.state.ac_enabled = False
    ac.update_trie_now("bonjour")
    type_text(ac, "bonj")
    assert ac.state.ac_ghost == ""
