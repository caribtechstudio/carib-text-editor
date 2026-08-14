"""Tests de l'explorateur de dossier et de la récupération après crash."""

import json
import os

import pytest

from models import recovery
from models.workspace import (IGNORED_DIRS, build_tree, display_name, is_text_file,
                              list_dir)


# ===========================================================================
# Espace de travail
# ===========================================================================

@pytest.fixture
def projet(tmp_path):
    (tmp_path / "notes.md").write_text("# notes")
    (tmp_path / "script.py").write_text("x = 1")
    (tmp_path / "photo.png").write_bytes(b"\x89PNG")
    (tmp_path / "README").write_text("sans extension")
    (tmp_path / ".cache").write_text("caché")

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("app")
    (tmp_path / "src" / "deep").mkdir()
    (tmp_path / "src" / "deep" / "x.txt").write_text("profond")

    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "junk.js").write_text("bruit")
    (tmp_path / ".git").mkdir()
    return tmp_path


def test_extensions_texte():
    assert is_text_file("a.md") and is_text_file("a.py") and is_text_file("a.txt")
    assert is_text_file("README")            # sans extension = souvent du texte
    assert not is_text_file("a.png")
    assert not is_text_file("a.exe")


def test_list_dir_filtre_le_bruit(projet):
    dirs, files, truncated = list_dir(str(projet))
    assert "src" in dirs
    assert "node_modules" not in dirs        # dossier de dépendances masqué
    assert ".git" not in dirs                # dossier caché masqué
    assert "notes.md" in files and "script.py" in files
    assert "photo.png" not in files          # binaire masqué
    assert ".cache" not in files
    assert not truncated


def test_arborescence_est_paresseuse(projet):
    """Sans dossier déplié, on ne descend pas — c'est ce qui rend l'ouverture
    d'un gros dépôt instantanée."""
    plat = build_tree(str(projet), expanded=set())
    noms = [e.name for e in plat]
    assert "src" in noms
    assert "app.py" not in noms


def test_arborescence_descend_dans_les_dossiers_deplies(projet):
    expanded = {os.path.normcase(str(projet / "src"))}
    noms = [e.name for e in build_tree(str(projet), expanded)]
    assert "app.py" in noms
    assert "deep" in noms
    assert "x.txt" not in noms               # « deep » n'est pas déplié


def test_dossiers_avant_fichiers(projet):
    entries = build_tree(str(projet), expanded=set())
    premiers_fichiers = next(i for i, e in enumerate(entries) if not e.is_dir)
    assert all(e.is_dir for e in entries[:premiers_fichiers])


def test_dossier_inexistant_ou_vide(tmp_path):
    assert build_tree("", set()) == []
    assert build_tree(str(tmp_path / "absent"), set()) == []
    assert build_tree(str(tmp_path), set()) == []


def test_nom_affiche(tmp_path):
    assert display_name(str(tmp_path)) == tmp_path.name
    assert display_name(str(tmp_path) + os.sep) == tmp_path.name


def test_gros_dossier_tronque(tmp_path, monkeypatch):
    import models.workspace as ws
    monkeypatch.setattr(ws, "MAX_ENTRIES_PER_DIR", 10)
    for i in range(50):
        (tmp_path / f"f{i}.txt").write_text("x")
    dirs, files, truncated = list_dir(str(tmp_path))
    assert truncated
    assert len(files) <= 10


# ===========================================================================
# Récupération après crash
# ===========================================================================

class FakeDoc:
    def __init__(self, title, content, modified=True, path=None):
        self.title = title
        self.content = content
        self.modified = modified
        self.path = path
        self.encoding = "utf-8"
        self.newline = "\n"


@pytest.fixture(autouse=True)
def journal_isole(tmp_path, monkeypatch):
    """Isole le journal du vrai ~/.glyph de la machine."""
    monkeypatch.setattr(recovery, "_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(recovery, "_RECOVERY_FILE", str(tmp_path / "recovery.json"))
    yield
    recovery.clear()


def test_rien_a_recuperer_au_depart():
    assert recovery.load() == []
    assert not recovery.has_pending()


def test_le_journal_enregistre_les_documents_modifies():
    docs = [FakeDoc("brouillon", "du travail en cours"),
            FakeDoc("propre", "déjà sauvé", modified=False)]
    recovery.RecoveryJournal(lambda: docs).snapshot()

    pending = recovery.load()
    assert len(pending) == 1
    assert pending[0]["title"] == "brouillon"
    assert pending[0]["content"] == "du travail en cours"


def test_le_journal_ignore_les_documents_vides():
    recovery.RecoveryJournal(lambda: [FakeDoc("vide", "")]).snapshot()
    assert recovery.load() == []


def test_une_fermeture_propre_efface_le_journal():
    """C'est l'absence du journal qui prouve, au démarrage suivant, que la
    session précédente s'est terminée normalement."""
    docs = [FakeDoc("brouillon", "contenu")]
    recovery.RecoveryJournal(lambda: docs).snapshot()
    assert recovery.has_pending()

    recovery.clear()
    assert not recovery.has_pending()


def test_le_journal_se_vide_quand_tout_est_enregistre():
    docs = [FakeDoc("brouillon", "contenu")]
    journal = recovery.RecoveryJournal(lambda: docs)
    journal.snapshot()
    assert recovery.has_pending()

    docs[0].modified = False
    journal.snapshot()
    assert not recovery.has_pending()


def test_journal_corrompu_est_ignore(tmp_path):
    (tmp_path / "recovery.json").write_text("ceci n'est pas du JSON {{{")
    assert recovery.load() == []
    assert not os.path.exists(tmp_path / "recovery.json")   # nettoyé


def test_journal_trop_ancien_est_ignore(tmp_path):
    import time
    payload = {"saved_at": time.time() - recovery.MAX_AGE_SECONDS - 10,
               "documents": [{"title": "vieux", "content": "x"}]}
    (tmp_path / "recovery.json").write_text(json.dumps(payload))
    assert recovery.load() == []


def test_ecriture_identique_nest_pas_repetee(tmp_path):
    docs = [FakeDoc("stable", "contenu inchangé")]
    journal = recovery.RecoveryJournal(lambda: docs)
    journal.snapshot()
    mtime = os.path.getmtime(tmp_path / "recovery.json")

    journal.snapshot()
    assert os.path.getmtime(tmp_path / "recovery.json") == mtime


def test_libelle_dancienete():
    recovery.RecoveryJournal(lambda: [FakeDoc("x", "y")]).snapshot()
    assert "minute" in recovery.age_label()
