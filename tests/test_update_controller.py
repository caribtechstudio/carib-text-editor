"""
tests/test_update_controller.py — Enchainement de la mise a jour.

Verifie la regle qui compte le plus : **aucune connexion tant que
l'utilisateur n'a pas donne son accord**, et le comportement des trois
reponses possibles (maintenant / plus tard / ignorer).

Le contrôleur est teste avec une fausse page Flet : on ne cherche pas a
verifier le rendu, seulement l'ordre des appels et l'etat persiste.
"""

import threading

import pytest

from controllers.update_controller import UpdateController
from models import updater


# ---------------------------------------------------------------------------
# Doublures
# ---------------------------------------------------------------------------

class FakePage:
    """Page Flet minimale. `run_thread` execute tout de suite."""

    def __init__(self):
        self.dialogs = []
        self.urls = []
        self.tasks = []
        self.height = 820

    def run_thread(self, fn):
        fn()

    def run_task(self, fn, *a, **kw):
        self.tasks.append(fn)

    def show_dialog(self, dlg):
        self.dialogs.append(dlg)

    def pop_dialog(self):
        if self.dialogs:
            self.dialogs.pop()

    def launch_url(self, url):
        self.urls.append(url)

    def update(self):
        pass


class FakeServices:
    def __init__(self):
        self.snacks = []

    def show_snack(self, msg, color=None):
        self.snacks.append(msg)


class FakeApp:
    def __init__(self):
        self.state = type("S", (), {"docs": []})()
        self.destroyed = False

    async def shutdown_and_destroy(self):
        self.destroyed = True


def _colour(light, dark):
    return light


class _SyncThread:
    """Thread qui s'execute a `start()`, sur le thread appelant.

    Le contrôleur lance ses appels reseau dans un thread demon : sans cette
    doublure, chaque assertion courrait apres lui et le resultat dependrait
    de l'ordonnanceur. On teste ici l'enchainement, pas la concurrence.
    """

    def __init__(self, target=None, name=None, daemon=None, args=(), kwargs=None):
        self._target = target
        self._args = args
        self._kwargs = kwargs or {}
        self.name = name

    def start(self):
        if self._target:
            self._target(*self._args, **self._kwargs)

    def join(self, timeout=None):
        pass


@pytest.fixture
def ctrl(tmp_path, monkeypatch):
    monkeypatch.setattr(updater, "_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(updater, "_PREFS_FILE", str(tmp_path / "update.json"))
    monkeypatch.setattr("controllers.update_controller.threading.Thread",
                        _SyncThread)
    page, svc, app = FakePage(), FakeServices(), FakeApp()
    controller = UpdateController(page, _colour, svc, app)
    controller.page, controller.svc, controller.app = page, svc, app
    return controller


def _info(version="0.99.0", *, downloadable=True):
    return updater.UpdateInfo(
        version=version, tag=f"v{version}", name=f"Carib {version}",
        notes="Corrections diverses.",
        page_url="https://github.com/caribtechstudio/carib-text-editor/releases/tag/v" + version,
        asset_name="Carib_Setup.exe" if downloadable else "",
        asset_url=("https://github.com/caribtechstudio/carib-text-editor/releases/download/"
                   "v/Carib_Setup.exe") if downloadable else "",
        asset_size=1000, sha256="ab" * 32 if downloadable else "")


# ---------------------------------------------------------------------------
# Consentement initial
# ---------------------------------------------------------------------------

def test_aucune_connexion_avant_le_consentement(ctrl, monkeypatch):
    """Au premier lancement, Carib demande — il n'interroge pas GitHub."""
    appels = []
    monkeypatch.setattr(updater, "check",
                        lambda *a, **kw: appels.append(1) or None)

    ctrl.maybe_check_on_startup()

    assert appels == [], "GitHub a ete interroge sans consentement"
    assert len(ctrl.page.dialogs) == 1, "la demande d'autorisation manque"
    assert ctrl.prefs.enabled is None


def test_refus_du_consentement_desactive_durablement(ctrl, monkeypatch):
    monkeypatch.setattr(updater, "check", lambda *a, **kw: None)
    ctrl.set_enabled(False)

    ctrl.maybe_check_on_startup()

    assert ctrl.page.dialogs == []
    assert updater.UpdatePrefs.load().enabled is False


def test_le_reglage_survit_au_redemarrage(ctrl):
    ctrl.set_enabled(True)
    assert updater.UpdatePrefs.load().enabled is True


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

def test_verification_silencieuse_quand_a_jour(ctrl, monkeypatch):
    monkeypatch.setattr(updater, "check", lambda *a, **kw: None)
    ctrl.set_enabled(True)

    ctrl.maybe_check_on_startup()

    assert ctrl.page.dialogs == []
    assert ctrl.svc.snacks == [], "un demarrage a jour doit rester muet"


def test_verification_manuelle_confirme_qu_on_est_a_jour(ctrl, monkeypatch):
    monkeypatch.setattr(updater, "check", lambda *a, **kw: None)
    ctrl.set_enabled(True)

    ctrl.check_now()

    assert any("à jour" in s for s in ctrl.svc.snacks)


def test_un_echec_reseau_au_demarrage_reste_muet(ctrl, monkeypatch):
    """Ne pas joindre GitHub n'est pas un probleme que l'utilisateur doit regler."""
    def boom(*a, **kw):
        raise updater.UpdateError("Impossible de contacter GitHub.")
    monkeypatch.setattr(updater, "check", boom)
    ctrl.set_enabled(True)

    ctrl.maybe_check_on_startup()

    assert ctrl.svc.snacks == []


def test_un_echec_reseau_manuel_est_signale(ctrl, monkeypatch):
    def boom(*a, **kw):
        raise updater.UpdateError("Impossible de contacter GitHub.")
    monkeypatch.setattr(updater, "check", boom)
    ctrl.set_enabled(True)

    ctrl.check_now()

    assert any("GitHub" in s for s in ctrl.svc.snacks)


def test_la_date_n_avance_pas_apres_un_echec(ctrl, monkeypatch):
    def boom(*a, **kw):
        raise updater.UpdateError("reseau")
    monkeypatch.setattr(updater, "check", boom)
    ctrl.set_enabled(True)

    ctrl.maybe_check_on_startup()

    assert ctrl.prefs.last_check == 0.0, \
        "une coupure reseau ne doit pas faire sauter la verification du jour"


# ---------------------------------------------------------------------------
# Proposition
# ---------------------------------------------------------------------------

def test_une_version_disponible_est_proposee(ctrl, monkeypatch):
    monkeypatch.setattr(updater, "check", lambda *a, **kw: _info())
    ctrl.set_enabled(True)

    ctrl.maybe_check_on_startup()

    assert len(ctrl.page.dialogs) == 1
    assert ctrl.prefs.last_check > 0


def test_une_version_ignoree_n_est_plus_proposee(ctrl, monkeypatch):
    monkeypatch.setattr(updater, "check", lambda *a, **kw: _info("0.99.0"))
    ctrl.set_enabled(True)
    ctrl.prefs.skipped_version = "0.99.0"
    ctrl.prefs.save()

    ctrl.maybe_check_on_startup()

    assert ctrl.page.dialogs == []


def test_une_verification_manuelle_leve_l_oubli(ctrl, monkeypatch):
    """« Rechercher une mise a jour » doit reproposer une version ignoree."""
    monkeypatch.setattr(updater, "check", lambda *a, **kw: _info("0.99.0"))
    ctrl.set_enabled(True)
    ctrl.prefs.skipped_version = "0.99.0"
    ctrl.prefs.save()

    ctrl.check_now()

    assert len(ctrl.page.dialogs) == 1
    assert ctrl.prefs.skipped_version == ""


# ---------------------------------------------------------------------------
# Telechargement et installation
# ---------------------------------------------------------------------------

def test_le_telechargement_mene_a_la_confirmation(ctrl, monkeypatch):
    monkeypatch.setattr(updater, "download",
                        lambda info, **kw: r"C:\tmp\Carib_Setup.exe")
    ctrl._start_download(_info())

    # Le dialogue de progression a ete referme, celui de confirmation ouvert.
    assert len(ctrl.page.dialogs) == 1
    assert not ctrl._busy


def test_un_telechargement_annule_ne_propose_pas_d_installer(ctrl, monkeypatch):
    def cancelled(info, **kw):
        raise updater.UpdateCancelled()
    monkeypatch.setattr(updater, "download", cancelled)

    ctrl._start_download(_info())

    assert ctrl.page.dialogs == []
    assert any("annul" in s.lower() for s in ctrl.svc.snacks)


def test_une_empreinte_invalide_bloque_l_installation(ctrl, monkeypatch):
    def bad(info, **kw):
        raise updater.UpdateError("L'empreinte du fichier ne correspond pas.")
    monkeypatch.setattr(updater, "download", bad)

    ctrl._start_download(_info())

    assert ctrl.page.dialogs == [], "aucune installation ne doit etre proposee"
    assert any("empreinte" in s.lower() for s in ctrl.svc.snacks)


def test_un_seul_telechargement_a_la_fois(ctrl, monkeypatch):
    lent = threading.Event()
    monkeypatch.setattr(updater, "download",
                        lambda info, **kw: (lent.wait(2), "x")[1])
    ctrl._busy = True

    ctrl._start_download(_info())
    lent.set()

    assert ctrl.page.dialogs == []


def test_sans_depot_configure_rien_ne_se_passe(ctrl, monkeypatch):
    monkeypatch.setattr(updater, "GITHUB_REPO", "")
    ctrl.maybe_check_on_startup()
    assert ctrl.page.dialogs == []
