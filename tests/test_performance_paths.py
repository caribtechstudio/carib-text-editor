"""
Tests des chemins critiques pour la réactivité.

Ces tests ne mesurent pas des durées — une mesure de temps dans une suite de
tests est instable et ne dit rien d'utile. Ils vérifient la **propriété** qui
rend l'application rapide : que le travail coûteux n'est pas fait là où il ne
doit pas l'être.

Trois propriétés, qui correspondent chacune à un ralentissement observé :

  1. La frappe ne reconstruit pas l'interface.
  2. Le changement d'onglet ne réindexe pas le dictionnaire sur place.
  3. Les notifications ne s'accumulent pas dans la pile de dialogues.
"""

import pytest

from controllers.autocomplete_controller import AutocompleteController
from models.document import Document
from models.editor_state import EditorState
from models.scheduler import scheduler


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

    def update(self, *controls):
        pass


@pytest.fixture
def doc():
    return Document(content="")


@pytest.fixture
def ac(doc):
    state = EditorState()
    state.docs = [doc]
    controller = AutocompleteController(
        state, FakeEditor(), lambda: doc, lambda: None, FakePage(),
        refresh_fn=lambda: None, llm_ready_fn=lambda: False,
    )
    yield controller
    scheduler.cancel_all()


# ---------------------------------------------------------------------------
# 1. La frappe ne reconstruit pas l'interface
# ---------------------------------------------------------------------------

def test_la_frappe_signale_quelle_est_en_cours(ac, doc):
    """`typing` permet à AppController de ne pas envoyer deux fois la frappe.

    Sans ce drapeau, chaque caractère produisait deux comparaisons du
    sous-arbre de l'éditeur : une pour la suggestion, une pour la barre
    d'état. Sur un fichier coloré, ce sous-arbre contient des milliers de
    spans.
    """
    seen = []
    ac._refresh = lambda: seen.append(ac.typing)

    doc.content = "bonjou"
    ac.on_text_changed(len("bonjou"))

    assert seen, "la suggestion aurait dû déclencher un rafraîchissement"
    assert all(seen), "le drapeau doit être levé pendant tout le traitement"
    assert ac.typing is False, "et retombé une fois la touche traitée"


def test_le_drapeau_retombe_meme_en_cas_derreur(ac, doc):
    def boom():
        raise RuntimeError("rafraîchissement cassé")

    ac._refresh = boom
    doc.content = "bonjou"

    with pytest.raises(RuntimeError):
        ac.on_text_changed(len("bonjou"))

    assert ac.typing is False


# ---------------------------------------------------------------------------
# 2. Le changement d'onglet ne réindexe pas sur place
# ---------------------------------------------------------------------------

def test_le_changement_donglet_differe_la_reindexation(ac):
    """Réindexer parcourt tout le document : cela ne doit pas retenir la bascule."""
    indexed = []
    ac._word_completer.update_from_text = lambda text: indexed.append(text)

    ac.refresh_dictionary_soon("un texte de plusieurs mots")

    assert indexed == [], "l'indexation doit être différée, pas immédiate"
    assert scheduler.is_pending("autocomplete.trie")


def test_update_trie_now_reste_synchrone(ac):
    """Le chemin explicite, lui, indexe tout de suite (tests, ouverture)."""
    indexed = []
    ac._word_completer.update_from_text = lambda text: indexed.append(text)

    ac.update_trie_now("anticonstitutionnellement")

    assert indexed == ["anticonstitutionnellement"]


# ---------------------------------------------------------------------------
# 3. Les notifications ne s'accumulent pas
# ---------------------------------------------------------------------------

class FakeDialogStack:
    def __init__(self):
        self.controls = []

    def update(self):
        pass


class FakeNotifierPage:
    def __init__(self):
        self._dialogs = FakeDialogStack()

    def show_dialog(self, dialog):
        dialog.open = True
        self._dialogs.controls.append(dialog)

    def run_thread(self, fn):
        fn()


@pytest.fixture
def notifier():
    from controllers.notifier import Notifier
    page = FakeNotifierPage()
    yield Notifier(page, lambda light, dark: light), page
    scheduler.cancel_all()


def test_une_seule_notification_vivante_a_la_fois(notifier):
    """C'est ce qui empêchait les notifications de s'afficher.

    Chaque bandeau restait dans `page._dialogs`, et Flutter met les `SnackBar`
    en file d'attente : la dixième n'apparaissait qu'après les neuf autres.
    """
    notif, page = notifier

    for i in range(10):
        notif.show(f"message {i}")

    assert len(page._dialogs.controls) == 1
    assert page._dialogs.controls[0].content.value == "message 9"


def test_deux_messages_identiques_rapproches_ne_comptent_que_pour_un(notifier):
    notif, page = notifier

    notif.show("Enregistré")
    notif.show("Enregistré")

    assert len(page._dialogs.controls) == 1


def test_prune_retire_les_bandeaux_oublies(notifier):
    """Filet pour les bandeaux qu'un chemin inhabituel aurait laissés."""
    import flet as ft

    notif, page = notifier
    for i in range(3):
        page._dialogs.controls.append(ft.SnackBar(content=ft.Text(str(i)), open=True))
    notif.show("courant")

    notif.prune()

    assert len(page._dialogs.controls) == 1
    assert page._dialogs.controls[0].content.value == "courant"


# ---------------------------------------------------------------------------
# 4. L'arborescence n'est pas relue à chaque rendu
# ---------------------------------------------------------------------------

def test_le_listage_du_dossier_est_memorise(tmp_path, monkeypatch):
    from models import workspace

    (tmp_path / "a.txt").write_text("", encoding="utf-8")
    workspace.invalidate_cache()

    calls = []
    real_scandir = workspace.os.scandir

    def counting_scandir(path):
        calls.append(path)
        return real_scandir(path)

    monkeypatch.setattr(workspace.os, "scandir", counting_scandir)

    for _ in range(5):
        workspace.list_dir(str(tmp_path))

    assert len(calls) == 1, "le disque ne doit être lu qu'une fois"

    workspace.invalidate_cache(str(tmp_path))
    workspace.list_dir(str(tmp_path))
    assert len(calls) == 2, "après invalidation, le disque est relu"
