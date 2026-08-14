"""
Tests du dispatch clavier.

Ces tests existent à cause d'un bug réel : `Ctrl+Maj+M` appelait
`self._toggle_md_preview`, un attribut jamais défini dans le constructeur.
Rien ne le signalait — ni la compilation, ni les autres tests — et le
raccourci levait une `AttributeError` au premier usage.

On parcourt donc **tous** les raccourcis déclarés et on vérifie qu'aucun ne
lève. C'est exactement la classe de défauts qu'un contrôleur à vingt
callbacks facultatifs produit.
"""

import asyncio
import inspect

import pytest

from controllers.keyboard_controller import KeyboardController


class Spy:
    """Enregistre les appels et accepte n'importe quelle signature."""

    def __init__(self):
        self.calls: list[str] = []

    def __getattr__(self, name):
        def recorder(*args, **kwargs):
            self.calls.append(name)
            return False            # `accept()` doit pouvoir renvoyer False
        return recorder


class FakeState:
    diff_active = False
    palette_visible = False
    kbar_visible = False
    ac_visible = False


class FakeUX:
    def __init__(self):
        self.state = FakeState()
        self.calls: list[str] = []

    def __getattr__(self, name):
        def recorder(*args, **kwargs):
            self.calls.append(name)
        return recorder


class FakeAutocomplete:
    """Autocomplétion en texte fantôme : une seule suggestion, pas de liste."""

    def __init__(self, suggestion=""):
        self.state = FakeState()
        self.suggestion = suggestion
        self.calls: list[str] = []

    @property
    def has_suggestion(self):
        return bool(self.suggestion)

    def accept(self):
        self.calls.append("accept")
        return bool(self.suggestion)

    def accept_word(self):
        self.calls.append("accept_word")
        return bool(self.suggestion)

    def dismiss(self):
        self.calls.append("dismiss")


class FakeSearch(Spy):
    visible = False


class FileSpy(Spy):
    """FileController factice : seules ces trois méthodes sont `async`."""

    ASYNC = {"open_file", "save_file", "save_file_as"}

    def __getattr__(self, name):
        if name in self.ASYNC:
            async def recorder(*args, **kwargs):
                self.calls.append(name)
        else:
            def recorder(*args, **kwargs):
                self.calls.append(name)
        return recorder


class Key:
    """Événement clavier minimal."""

    def __init__(self, key, ctrl=False, shift=False, alt=False):
        self.key = key
        self.ctrl = ctrl
        self.shift = shift
        self.alt = alt


@pytest.fixture
def controller():
    page = Spy()
    ux = FakeUX()
    kb = KeyboardController(
        page=page, c=lambda l, d: l, tab_ctrl=Spy(), file_ctrl=FileSpy(),
        ai_ctrl=Spy(), voice_ctrl=Spy(), check_spelling=lambda: None,
        show_emoji_picker=lambda: None, request_close=lambda: None,
        toggle_toolbar=lambda: None, undo=lambda: None, redo=lambda: None,
        search_ctrl=FakeSearch(), zoom_in=lambda: None, zoom_out=lambda: None,
        set_mode=lambda m: None, autocomplete_ctrl=FakeAutocomplete(),
        ai_ux=ux, goto_line=lambda: None, close_tab=lambda: None,
        show_help_fn=lambda: None, toggle_md_preview=lambda: None,
    )
    kb._zoom_reset = lambda: None
    return kb


def dispatch(kb, event):
    asyncio.run(kb.on_keyboard_event(event))


# ---------------------------------------------------------------------------
# Chaque raccourci doit s'exécuter sans lever
# ---------------------------------------------------------------------------

CTRL_KEYS = ["K", "F", "H", "G", "N", "W", "Tab", "O", "S", "E", "P", "Z", "Y",
             "T", "Numpad Add", "+", "=", "Numpad Subtract", "-", "Numpad 0",
             "0", "1", "2", "3"]
CTRL_SHIFT_KEYS = ["P", "Tab", "M", "S"]
FUNCTION_KEYS = ["F1", "F3", "F4", "F5", "F6", "F7", "F8", "F9"]


@pytest.mark.parametrize("key", CTRL_KEYS)
def test_raccourcis_ctrl(controller, key):
    dispatch(controller, Key(key, ctrl=True))


@pytest.mark.parametrize("key", CTRL_SHIFT_KEYS)
def test_raccourcis_ctrl_maj(controller, key):
    dispatch(controller, Key(key, ctrl=True, shift=True))


@pytest.mark.parametrize("key", FUNCTION_KEYS)
def test_touches_de_fonction(controller, key):
    dispatch(controller, Key(key))


def test_touche_inconnue_ne_leve_pas(controller):
    dispatch(controller, Key("Ç"))
    dispatch(controller, Key("F12"))
    dispatch(controller, Key("Escape"))


# ---------------------------------------------------------------------------
# Aucun callback facultatif ne doit être oublié dans le constructeur
# ---------------------------------------------------------------------------

def test_tous_les_attributs_utilises_sont_initialises():
    """Garde-fou contre la panne d'origine : un `self._x` référencé dans une
    méthode mais absent du constructeur."""
    source = inspect.getsource(KeyboardController)
    init_source = inspect.getsource(KeyboardController.__init__)

    # Les méthodes de la classe portent aussi un préfixe « _ » : elles sont
    # définies, pas assignées, donc on les écarte.
    methods = {name for name in dir(KeyboardController) if name.startswith("_")}

    used = set()
    for line in source.split("\n"):
        for token in line.split("self._")[1:]:
            name = ""
            for ch in token:
                if ch.isalnum() or ch == "_":
                    name += ch
                else:
                    break
            if name:
                used.add("_" + name)

    assigned = set()
    for line in init_source.split("\n"):
        stripped = line.strip()
        if stripped.startswith("self._") and "=" in stripped:
            assigned.add(stripped.split("=")[0].strip().replace("self.", ""))

    manquants = used - assigned - methods
    assert not manquants, f"attributs utilisés mais jamais initialisés : {manquants}"


# ---------------------------------------------------------------------------
# Priorité des surcouches
# ---------------------------------------------------------------------------

def test_la_revue_de_diff_capture_tout(controller):
    controller._ux.state.diff_active = True

    dispatch(controller, Key("Tab"))
    assert "accept_diff" in controller._ux.calls

    dispatch(controller, Key("Escape"))
    assert "reject_diff" in controller._ux.calls

    # Pendant la revue, aucun autre raccourci ne doit passer.
    controller._ux.calls.clear()
    dispatch(controller, Key("N", ctrl=True))
    assert controller._tab.calls == []


def test_la_palette_capture_la_navigation(controller):
    controller._ux.state.palette_visible = True

    dispatch(controller, Key("Arrow Down"))
    dispatch(controller, Key("Arrow Up"))
    dispatch(controller, Key("Enter"))
    assert {"navigate_palette", "run_palette_selection"} <= set(controller._ux.calls)


def test_echap_ferme_la_recherche_en_dernier_recours(controller):
    controller._search.visible = True
    dispatch(controller, Key("Escape"))
    assert "close_search" in controller._search.calls


# ---------------------------------------------------------------------------
# Texte fantôme
# ---------------------------------------------------------------------------

def test_tab_accepte_la_suggestion(controller):
    controller._ac.suggestion = "onjour"
    dispatch(controller, Key("Tab"))
    assert "accept" in controller._ac.calls


def test_ctrl_droite_accepte_un_mot(controller):
    controller._ac.suggestion = " le monde"
    dispatch(controller, Key("Arrow Right", ctrl=True))
    assert "accept_word" in controller._ac.calls


def test_les_fleches_restent_a_lediteur(controller):
    """La navigation dans le texte ne doit plus être détournée : c'était le
    défaut de la popup en liste."""
    controller._ac.suggestion = "quelque chose"
    dispatch(controller, Key("Arrow Down"))
    dispatch(controller, Key("Arrow Up"))
    dispatch(controller, Key("Arrow Right"))       # sans Ctrl
    assert controller._ac.calls == []


def test_echap_ecarte_la_suggestion(controller):
    controller._ac.suggestion = "quelque chose"
    dispatch(controller, Key("Escape"))
    assert "dismiss" in controller._ac.calls
