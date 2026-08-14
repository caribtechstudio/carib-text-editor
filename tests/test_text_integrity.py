"""
Intégrité du texte saisi — la garantie la plus importante de l'éditeur.

Le défaut à l'origine de ces tests : la base de comparaison de l'historique
d'annulation était un champ unique porté par `EditorController`, remis à
zéro à la main par chaque chemin de code changeant d'onglet. `add_tab()` ne
le faisait pas. Taper dans un onglet créé avec « + » puis annuler
remplaçait donc le texte tapé par celui de l'onglet précédent.

La base appartient désormais au document (`Document.undo_base`), et les
bornes de changement de document vivent dans `TabController` : aucun
appelant ne peut plus les contourner.
"""

import pytest

from controllers.editor_controller import EditorController
from controllers.tab_controller import TabController
from models.document import Document
from models.editor_state import EditorState
from models.scheduler import scheduler

_UNDO_TASK = "editor.undo_snapshot"


class FakeEditor:
    def __init__(self):
        self.value = ""
        self.selection = None
        self.read_only = False
        self.hint_text = ""

    def focus(self):
        pass


class FakePage:
    def update(self):
        pass

    def run_thread(self, fn):
        fn()

    def run_task(self, fn, *a):
        pass


class FakeServices:
    def __init__(self, state):
        self.rebuild = lambda: None
        self.update_status = lambda: None
        self.get_cursor = lambda: state.cursor
        self.save_session = lambda: None
        self.auto_save = lambda: None
        self.flush_typing = lambda: None


class FakePhrases:
    def get_random_phrase(self):
        return ""


class Harness:
    """Un éditeur complet, sans interface : état + onglets + saisie."""

    def __init__(self):
        self.state = EditorState()
        self.state.docs = [Document(title="A", content="")]
        self.state.idx = 0
        self.editor = FakeEditor()
        svc = FakeServices(self.state)

        self.tab = TabController(
            self.state, self.editor, FakePhrases(), svc,
            on_leave_document=self._leave, on_enter_document=self._enter)
        self.ed = EditorController(
            self.state, self.editor, self.tab.cur_doc, FakePage(), svc)
        self.entered = 0
        self.left = 0

    # Bornes équivalentes à celles d'AppController.
    def _leave(self):
        self.left += 1
        self.ed.force_snapshot()

    def _enter(self):
        self.entered += 1
        self.state.selection = None
        self.state.cursor = 0

    # ------------------------------------------------------------------
    def type(self, text):
        """Simule la frappe caractère par caractère, comme Flet le fait."""
        for i in range(1, len(text) + 1):
            self.editor.value = text[:i]
            self.state.cursor = i
            self.ed.on_text_changed(_Event(self.editor))

    def pause(self):
        """Laisse expirer le délai de regroupement de l'annulation."""
        scheduler.flush(_UNDO_TASK)

    def doc(self, idx):
        return self.state.docs[idx]


class _Event:
    def __init__(self, control):
        self.control = control


@pytest.fixture
def app():
    h = Harness()
    yield h
    scheduler.cancel(_UNDO_TASK)


# ---------------------------------------------------------------------------
# Le bug signalé
# ---------------------------------------------------------------------------

def test_undo_dans_un_onglet_neuf_nefface_pas_le_texte(app):
    """Ctrl+Z dans un onglet « + » ne doit jamais y coller le texte d'un autre."""
    app.type("Bonjour tout le monde")
    app.pause()

    app.tab.add_tab()
    app.type("Salut")
    app.pause()

    nouveau = app.doc(1)
    assert nouveau.content == "Salut"
    # L'annulation ramène au point de départ du nouvel onglet : vide.
    assert nouveau.undo() == ""
    # Et surtout : jamais le contenu de l'onglet précédent.
    assert nouveau.content != "Bonjour tout le monde"


def test_creer_un_onglet_preserve_le_texte_du_precedent(app):
    app.type("Texte important")
    app.tab.add_tab()
    assert app.doc(0).content == "Texte important"
    assert app.doc(1).content == ""
    assert app.editor.value == ""


def test_la_base_dannulation_est_par_document(app):
    app.type("AAA")
    app.tab.add_tab()
    # Le nouveau document démarre sans base héritée.
    assert app.doc(1).undo_base is None


# ---------------------------------------------------------------------------
# Les bornes ne peuvent plus être contournées
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("action", [
    lambda h: h.tab.add_tab(),
    lambda h: h.tab.next_tab(),
    lambda h: h.tab.prev_tab(),
    lambda h: h.tab.switch_tab(0),
])
def test_tout_changement_donglet_declenche_les_bornes(app, action):
    """add_tab, Ctrl+Tab et la barre d'onglets passent tous par _leave/_enter."""
    app.tab.add_tab()          # il faut deux onglets pour naviguer
    app.state.idx = 1
    before_enter, before_leave = app.entered, app.left

    action(app)

    assert app.entered > before_enter
    assert app.left > before_leave


def test_changer_donglet_fige_la_frappe_en_cours(app):
    """La dernière rafale tapée avant de changer d'onglet reste annulable."""
    app.type("Salut")          # pas de pause : la salve est encore ouverte
    app.tab.add_tab()          # quitte l'onglet A

    a = app.doc(0)
    assert a.undo_base is None, "la salve doit avoir été figée"
    assert a.can_undo
    assert a.undo() == ""


def test_curseur_et_selection_repartent_de_zero(app):
    app.type("Bonjour")
    app.state.selection = (2, 5)
    app.tab.add_tab()
    assert app.state.selection is None
    assert app.state.cursor == 0


def test_fermer_un_onglet_darriere_plan_ne_touche_pas_lactif(app):
    """Fermer un autre onglet ne doit pas déplacer le curseur du document écrit."""
    app.tab.add_tab()                    # onglet 1, devient actif
    app.type("Je suis en train d'ecrire")
    app.state.cursor = 5
    actif = app.tab.cur_doc()

    app.tab.close_tab(0)                 # ferme l'onglet d'arrière-plan

    assert app.tab.cur_doc() is actif
    assert actif.content == "Je suis en train d'ecrire"
    assert app.state.cursor == 5


# ---------------------------------------------------------------------------
# Historique : les réécritures programmatiques et la frappe cohabitent
# ---------------------------------------------------------------------------

def test_une_reecriture_ne_fond_pas_la_frappe_en_attente(app):
    """Coller après avoir tapé doit produire deux étapes d'annulation."""
    app.type("abc")                      # salve encore ouverte
    d = app.tab.cur_doc()
    d.apply_change("abcXYZ")             # collage programmatique

    assert d.undo() == "abc"             # 1er Ctrl+Z : annule le collage
    assert d.undo() == ""                # 2e : annule la frappe


def test_le_premier_caractere_est_annulable(app):
    """Le tout premier caractère d'un document doit pouvoir être annulé."""
    app.type("a")
    app.pause()
    d = app.tab.cur_doc()
    assert d.undo() == ""


def test_flush_pending_edit_est_idempotent(app):
    app.type("abc")
    d = app.tab.cur_doc()
    d.flush_pending_edit()
    n = len(d.undo_stack)
    d.flush_pending_edit()
    assert len(d.undo_stack) == n


# ---------------------------------------------------------------------------
# Sauvegarde de session : elle ne doit jamais réécrire un document
# ---------------------------------------------------------------------------

def test_build_session_necrase_jamais_un_document(app):
    """La sauvegarde s'exécute sur un thread : elle doit être en lecture seule.

    Scénario de la course corrigée : la valeur du widget est lue alors que
    l'onglet A est actif, l'utilisateur bascule sur B, puis l'écriture
    arrive — elle ne doit pas déposer le texte de A dans B.
    """
    from models.session_manager import build_session

    app.type("Texte de l'onglet A")
    app.tab.add_tab()
    app.type("Texte de l'onglet B")

    # `valeur_du_widget` est celle capturée AVANT la bascule d'onglet.
    build_session(app.state, "light", active_editor_content="Texte de l'onglet A")

    assert app.doc(1).content == "Texte de l'onglet B"
    assert app.doc(0).content == "Texte de l'onglet A"


def test_build_session_serialise_le_contenu_non_enregistre(app):
    from models.session_manager import build_session

    app.type("brouillon")
    data = build_session(app.state, "light", app.editor.value)
    assert data["tabs"][0]["content"] == "brouillon"
