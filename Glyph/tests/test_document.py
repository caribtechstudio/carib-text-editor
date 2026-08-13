"""Tests de l'historique d'annulation par deltas."""

from models.document import Document, _diff


# ---------------------------------------------------------------------------
# Calcul de delta
# ---------------------------------------------------------------------------

def test_diff_insertion_simple():
    edit = _diff("abc", "abXc")
    assert (edit.pos, edit.removed, edit.inserted) == (2, "", "X")


def test_diff_suppression_simple():
    edit = _diff("abcd", "acd")
    assert (edit.pos, edit.removed, edit.inserted) == (1, "b", "")


def test_diff_remplacement():
    edit = _diff("bonjour le monde", "bonsoir le monde")
    assert edit.apply("bonjour le monde") == "bonsoir le monde"
    assert edit.revert("bonsoir le monde") == "bonjour le monde"


def test_diff_textes_identiques_est_vide():
    assert _diff("abc", "abc").is_empty


def test_diff_prefixe_et_suffixe_ne_se_chevauchent_pas():
    """Cas piège : « aaa » → « aa » a un préfixe et un suffixe communs qui
    se recouvrent ; le delta doit rester cohérent."""
    edit = _diff("aaa", "aa")
    assert edit.apply("aaa") == "aa"
    assert edit.revert("aa") == "aaa"


def test_diff_depuis_vide_et_vers_vide():
    assert _diff("", "abc").apply("") == "abc"
    assert _diff("abc", "").apply("abc") == ""


# ---------------------------------------------------------------------------
# Undo / redo
# ---------------------------------------------------------------------------

def test_undo_redo_restaure_le_contenu():
    d = Document(content="version 1")
    d.apply_change("version 2")
    assert d.content == "version 2"

    assert d.undo() == "version 1"
    assert d.redo() == "version 2"


def test_undo_multiple_dans_lordre_inverse():
    d = Document(content="")
    for step in ("a", "ab", "abc", "abcd"):
        d.apply_change(step)

    assert d.undo() == "abc"
    assert d.undo() == "ab"
    assert d.undo() == "a"
    assert d.undo() == ""
    assert d.undo() is None


def test_une_nouvelle_modification_vide_la_pile_redo():
    d = Document(content="a")
    d.apply_change("ab")
    d.undo()
    d.apply_change("ax")
    assert d.redo() is None


def test_undo_sur_document_vierge_retourne_none():
    assert Document().undo() is None
    assert Document().redo() is None


def test_apply_change_identique_est_ignore():
    d = Document(content="abc")
    d.apply_change("abc")
    assert not d.can_undo


def test_historique_borne_a_max_undo():
    from models.document import MAX_UNDO
    d = Document(content="")
    for i in range(MAX_UNDO + 50):
        d.apply_change("x" * (i + 1))
    assert len(d.undo_stack) == MAX_UNDO


def test_deltas_bien_plus_legers_que_des_instantanes():
    """L'intérêt du changement : taper 100 caractères dans un gros document
    ne doit pas coûter 100 copies de ce document."""
    base = "lorem ipsum " * 5000          # ~60 000 caractères
    d = Document(content=base)
    for i in range(100):
        d.apply_change(base + "x" * (i + 1))

    cout = sum(len(e.removed) + len(e.inserted) for e in d.undo_stack)
    assert cout < len(base)               # au lieu de 100 × len(base)


def test_mark_saved_met_a_jour_les_metadonnees():
    d = Document(content="x", modified=True)
    d.mark_saved(1234.5, 42)
    assert not d.modified
    assert (d.mtime, d.size) == (1234.5, 42)
