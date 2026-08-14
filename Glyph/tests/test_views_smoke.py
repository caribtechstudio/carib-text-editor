"""
Tests de fumée des vues.

Aucun de ces contrôles n'est réellement rendu : on vérifie seulement que
chaque constructeur s'exécute et produit un contrôle Flet valide. C'est
précisément la classe d'erreurs que la compilation ne voit pas — un
paramètre renommé, une énumération inexistante, une clé de callback
manquante — et qui, sinon, ne se manifeste qu'à l'écran.
"""

import flet as ft
import pytest

from models.document import Document
from models.editor_state import EditorState
from models.syntax import detect_language, highlight
from core.theme import T


# ---------------------------------------------------------------------------
# Outillage
# ---------------------------------------------------------------------------

def light(l, d):
    return l


def dark(l, d):
    return d


THEMES = [pytest.param(light, False, id="clair"), pytest.param(dark, True, id="sombre")]


@pytest.fixture
def state():
    s = EditorState()
    s.docs = [Document(title="notes.md", content="# Titre\n\nDu **gras**.\n",
                       path="C:/tmp/notes.md")]
    s.idx = 0
    return s


def noop(*args, **kwargs):
    return None


ALL_CALLBACKS = {
    key: noop for key in (
        "close_ai", "apply_correction", "dismiss_correction", "replace_with_result",
        "copy_result", "review_inline", "switch_tab", "close_tab", "add_tab",
        "run_correction", "run_translate_fr_en", "run_translate_en_fr",
        "run_reformulate", "run_natural", "run_professional", "run_summarize",
        "run_keywords", "show_model_manager", "show_emoji_picker", "show_voice_menu",
        "copy_text_handler", "paste_text_handler", "cut_text_handler", "clear_text",
        "undo", "redo", "toggle_search", "zoom_in", "zoom_out", "set_mode",
        "open_command_bar", "toggle_sidebar", "open_file", "save_file",
        "save_file_as", "rename_file", "print_file", "show_help", "show_options",
        "open_recent", "toggle_recent_expanded", "open_workspace",
        "close_workspace", "toggle_dir", "open_path", "on_query_change",
        "on_search", "on_next", "on_prev", "on_close", "toggle_case",
        "toggle_whole_word", "toggle_regex", "toggle_replace",
        "on_replacement_change", "replace_current", "replace_all", "on_submit",
        "run_mode", "run", "accept", "reject", "insert_emoji",
    )
}


# ---------------------------------------------------------------------------
# Coloration et gouttière
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("c, is_dark", THEMES)
@pytest.mark.parametrize("name", ["a.py", "a.json", "a.md", "a.yaml", "a.js", "a.sql"])
def test_couche_de_coloration(c, is_dark, name):
    from views.syntax_view import build_syntax_text
    text = '# note\ndef f(x):\n    return "abc" + 1\n'
    control = build_syntax_text(text, highlight(text, detect_language(name)),
                                c, 16, is_dark)
    assert isinstance(control, ft.Text)


@pytest.mark.parametrize("c, is_dark", THEMES)
def test_couche_de_coloration_sans_segments(c, is_dark):
    from views.syntax_view import build_syntax_text
    assert isinstance(build_syntax_text("texte brut", [], c, 16, is_dark), ft.Text)


@pytest.mark.parametrize("c, _", THEMES)
@pytest.mark.parametrize("text", ["", "une ligne", "a\nb\nc\n", "x\n" * 500])
def test_gouttiere_de_numeros(c, _, text):
    from views.syntax_view import build_line_gutter
    control = build_line_gutter(text, c, 16, current_line=2)
    assert isinstance(control, ft.Container)
    assert control.width >= 38


# ---------------------------------------------------------------------------
# Espace de travail
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("c, _", THEMES)
def test_panneau_espace_de_travail(c, _, state, tmp_path):
    from views.workspace_view import build_workspace_panel
    (tmp_path / "note.md").write_text("x")
    (tmp_path / "sous").mkdir()

    state.workspace_path = str(tmp_path)
    callbacks = dict(ALL_CALLBACKS, active_path=str(tmp_path / "note.md"))
    assert isinstance(build_workspace_panel(state, c, callbacks), ft.Container)


def test_panneau_absent_sans_dossier(state):
    from views.workspace_view import build_workspace_panel
    state.workspace_path = ""
    assert build_workspace_panel(state, light, ALL_CALLBACKS) is None


# ---------------------------------------------------------------------------
# Barres et panneaux
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("c, _", THEMES)
def test_barre_de_recherche_avec_et_sans_remplacement(c, _, state):
    from views.search_bar import build_search_bar
    state.search.query = "abc"
    state.search.search("abc abc")

    for replace_visible in (False, True):
        state.search.replace_visible = replace_visible
        bar, field, counter = build_search_bar(c, state.search, ALL_CALLBACKS)
        assert isinstance(bar, ft.Container)
        assert isinstance(field, ft.TextField)
        assert isinstance(counter, ft.Text)


@pytest.mark.parametrize("c, _", THEMES)
def test_surlignage_de_recherche(c, _):
    from views.search_bar import build_highlight_text
    text = "chat et chat"
    matches = [(0, 4), (8, 12)]
    assert isinstance(build_highlight_text(text, matches, 0, c, 16), ft.Text)
    assert isinstance(build_highlight_text("", [], -1, c, 16), ft.Text)


@pytest.mark.parametrize("c, _", THEMES)
def test_barre_de_commande_et_palette(c, _, state):
    from views.command_bar import build_command_bar
    from views.command_palette import Command, build_command_palette

    state.kbar_visible = True
    assert isinstance(build_command_bar(state, c, ALL_CALLBACKS,
                                        "Sur la sélection", "gpt-4.1-mini"),
                      ft.Container)

    state.palette_visible = True
    commands = [Command(f"c{i}", f"Commande {i}", noop, "Groupe", "Ctrl+X")
                for i in range(20)]
    for query in ("", "commande", "zzz"):
        state.palette_query = query
        assert isinstance(build_command_palette(state, c, commands, ALL_CALLBACKS),
                          ft.Container)


@pytest.mark.parametrize("c, _", THEMES)
def test_diff_inline(c, _):
    from views.diff_view import build_diff_actions, build_diff_text, compute_diff
    segments = compute_diff("bonjour le monde", "bonsoir le monde")
    assert isinstance(build_diff_text("avant ", segments, " apres", c, 16), ft.Text)
    assert isinstance(build_diff_actions(c, 3, 2, ALL_CALLBACKS), ft.Container)


@pytest.mark.parametrize("c, _", THEMES)
def test_barre_de_statut_et_badge_ia(c, _):
    from views.status_bar import build_ai_badge, build_status_bar
    texts = [ft.Text(x) for x in ("mode", "msg", "car", "mots", "zoom", "pos", "enc")]
    bar = build_status_bar(c, *texts[:5], st_pos=texts[5], st_encoding=texts[6],
                           ai_badge=build_ai_badge(c, "ChatGPT · 0,03 €",
                                                   False, False, noop))
    assert isinstance(bar, ft.Container)

    for is_local in (True, False):
        for warning in (True, False):
            assert isinstance(build_ai_badge(c, "x", is_local, warning, noop),
                              ft.Container)


@pytest.mark.parametrize("c, _", THEMES)
def test_barre_laterale_repliee_et_depliee(c, _, state, tmp_path):
    from views.sidebar import build_sidebar
    state.recent_files = [str(tmp_path)]
    callbacks = dict(ALL_CALLBACKS, recent_chevron=ft.Text("x"),
                     recent_expandable=ft.Container())

    for collapsed in (True, False):
        state.sidebar_collapsed = collapsed
        assert isinstance(build_sidebar(state, c, callbacks), ft.Container)

    # Avec un dossier ouvert, l'arborescence remplace le ressort vertical.
    state.sidebar_collapsed = False
    state.workspace_path = str(tmp_path)
    assert isinstance(build_sidebar(state, c, callbacks), ft.Container)


@pytest.mark.parametrize("c, _", THEMES)
def test_barre_doutils_et_onglets(c, _, state):
    from views.menu_bar import build_menu_bar
    from views.tab_bar import build_tab_bar
    assert build_menu_bar(c, ALL_CALLBACKS) is not None
    assert build_tab_bar(state, c, ALL_CALLBACKS) is not None


@pytest.mark.parametrize("c, _", THEMES)
def test_panneau_ia_dans_tous_les_modes(c, _, state):
    from views.ai_panel import build_ai_panel

    state.show_ai = False
    assert build_ai_panel(state, c, ALL_CALLBACKS) is not None

    state.show_ai = True
    modes = ["correction", "translate_fr_en", "translate_en_fr", "reformulate",
             "natural", "professional", "summarize", "keywords", "free"]

    for mode in modes:
        state.ai_mode = mode
        state.ai_model_used = "openai · gpt-4.1-mini"

        # 1. En cours de génération
        state.ai_loading = True
        state.ai_stream = "des jetons arrivent"
        assert build_ai_panel(state, c, ALL_CALLBACKS) is not None

        # 2. En erreur
        state.ai_loading = False
        state.ai_error = "Une erreur lisible."
        assert build_ai_panel(state, c, ALL_CALLBACKS) is not None

        # 3. Avec un résultat
        state.ai_error = ""
        state.dispatch_ai_result(mode, {
            "corrections": [{"original": "erreur", "correction": "erreur",
                             "type": "orthographe", "explication": "x"}],
            "suggestions": [], "score": 90,
            "translation": "traduit", "notes": ["note"],
            "result": "reformulé", "changes": ["changement"],
            "key_points": ["point"], "reduction": "50 %",
            "theme": "sujet", "primary_keywords": ["a"],
            "secondary_keywords": ["b"],
        })
        state.ai_reformulation = state.ai_reformulation or "texte libre"
        assert build_ai_panel(state, c, ALL_CALLBACKS) is not None


@pytest.mark.parametrize("c, is_dark", THEMES)
def test_texte_fantome(c, is_dark):
    from views.ghost_text import build_ghost_hint, build_ghost_text

    text = "Bonjour le "
    # Sans coloration
    assert isinstance(build_ghost_text(text, len(text), "monde entier.",
                                       c, 16, dark=is_dark), ft.Text)
    # Avec coloration syntaxique par-dessous
    code = "def f():\n    return 1"
    segments = highlight(code, detect_language("a.py"))
    assert isinstance(build_ghost_text(code, 8, " # suite", c, 16,
                                       segments=segments, dark=is_dark), ft.Text)
    # Curseur au milieu, et cas limites
    assert isinstance(build_ghost_text(text, 3, "xyz", c, 16, dark=is_dark), ft.Text)
    assert isinstance(build_ghost_text("", 0, "", c, 16, dark=is_dark), ft.Text)
    assert isinstance(build_ghost_text(text, 999, "x", c, 16, dark=is_dark), ft.Text)

    assert build_ghost_hint(c, "") is None
    assert isinstance(build_ghost_hint(c, "une suggestion"), ft.Container)


def test_le_texte_fantome_preserve_le_document():
    """Le texte réel doit être restitué intégralement autour de la suggestion :
    une erreur ici afficherait un document tronqué à l'utilisateur."""
    from views.ghost_text import build_ghost_text

    text = "Le chat dort sur le canapé."
    for cursor in (0, 3, 12, len(text)):
        control = build_ghost_text(text, cursor, "<<GHOST>>", light, 16)
        rendered = "".join(span.text for span in control.spans)
        assert rendered.replace("<<GHOST>>", "") == text
