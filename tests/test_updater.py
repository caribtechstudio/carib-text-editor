"""
tests/test_updater.py — Mise a jour depuis GitHub.

L'updater telecharge puis **execute** un programme : ses garde-fous sont
donc testes en priorite — origine du fichier, empreinte, taille, annulation.
Un test qui passe ici est ce qui distingue une mise a jour d'une porte
d'entree.
"""

import hashlib
import json
import os
import threading

import pytest

from models import updater


# ---------------------------------------------------------------------------
# Comparaison de versions
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw, expected", [
    ("1.2.3", (1, 2, 3, 1, 0)),
    ("v1.2.3", (1, 2, 3, 1, 0)),
    ("0.14", (0, 14, 0, 1, 0)),
    ("2", (2, 0, 0, 1, 0)),
    ("0.13.2.4", (0, 13, 2, 1, 4)),
    ("1.0.0-beta.2", (1, 0, 0, 0, 2)),
    ("1.0.0-rc1", (1, 0, 0, 0, 1)),
    ("  v0.14.0  ", (0, 14, 0, 1, 0)),
])
def test_parse_version(raw, expected):
    assert updater.parse_version(raw) == expected


@pytest.mark.parametrize("raw", ["", "abc", "v", "version", "v-1.0", ".."])
def test_parse_version_rejette_ce_qui_ne_commence_pas_par_un_nombre(raw):
    with pytest.raises(ValueError):
        updater.parse_version(raw)


@pytest.mark.parametrize("raw", ["1.2.experimental", "1..2", "1.2-"])
def test_parse_version_tolere_les_suffixes_exotiques(raw):
    """Le parseur est volontairement permissif après le premier nombre.

    Les deux issues possibles sont sûres : soit `ValueError`, que `is_newer`
    rattrape en ne proposant rien, soit un tuple de préversion, qui se classe
    *avant* la version stable — donc ne propose rien non plus. Dans aucun cas
    une étiquette mal formée ne peut déclencher une mise à jour.
    """
    parsed = updater.parse_version(raw)          # ne doit pas lever
    assert parsed[0] == 1
    assert not updater.is_newer(raw, "9.0.0")


def test_is_newer():
    assert updater.is_newer("0.15.0", "0.14.0")
    assert updater.is_newer("1.0.0", "0.99.99")
    assert updater.is_newer("0.14.1", "0.14.0")
    assert not updater.is_newer("0.14.0", "0.14.0")
    assert not updater.is_newer("0.13.9", "0.14.0")


def test_une_preversion_ne_remplace_pas_une_version_stable():
    """« 1.0.0-beta » est anterieur a « 1.0.0 », pas posterieur."""
    assert not updater.is_newer("1.0.0-beta.1", "1.0.0")
    assert updater.is_newer("1.0.0", "1.0.0-beta.1")


def test_une_etiquette_illisible_ne_propose_rien():
    """Un tag exotique ne doit jamais declencher de mise a jour."""
    assert not updater.is_newer("latest", "0.14.0")
    assert not updater.is_newer("", "0.14.0")


# ---------------------------------------------------------------------------
# Origine du telechargement
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("url", [
    "https://github.com/o/r/releases/download/v1/Setup.exe",
    "https://objects.githubusercontent.com/abc",
    "https://api.github.com/repos/o/r/releases/latest",
])
def test_hotes_github_acceptes(url):
    updater._check_host(url)          # ne doit pas lever


@pytest.mark.parametrize("url", [
    "http://github.com/o/r/Setup.exe",          # pas de HTTPS
    "https://evil.example.com/Setup.exe",       # hote inconnu
    "https://github.com.evil.com/Setup.exe",    # homographe
    "https://raw.githubusercontent.com.evil/x",
    "ftp://github.com/x",
    "",
])
def test_origines_refusees(url):
    with pytest.raises(updater.UpdateError):
        updater._check_host(url)


# ---------------------------------------------------------------------------
# Choix de l'actif et empreinte
# ---------------------------------------------------------------------------

def test_pick_installer_prefere_le_setup():
    assets = [
        {"name": "Carib-portable.exe"},
        {"name": "Carib_v1.0.0_Setup.exe"},
        {"name": "notes.txt"},
    ]
    assert updater._pick_installer(assets)["name"] == "Carib_v1.0.0_Setup.exe"


def test_pick_installer_sans_exe():
    assert updater._pick_installer([{"name": "notes.txt"}]) is None


def test_parse_sums_trouve_la_bonne_ligne():
    content = (
        "aa" * 32 + "  autre.exe\n"
        + "bb" * 32 + " *Carib_v1.0.0_Setup.exe\n"
    )
    assert updater._parse_sums(content, "Carib_v1.0.0_Setup.exe") == "bb" * 32


def test_parse_sums_ligne_unique_sans_nom():
    digest = "cc" * 32
    assert updater._parse_sums(digest + "\n", "Carib_Setup.exe") == digest


def test_parse_sums_refuse_de_deviner_entre_plusieurs():
    content = "aa" * 32 + "  a.exe\n" + "bb" * 32 + "  b.exe\n"
    assert updater._parse_sums(content, "inconnu.exe") == ""


def test_extract_sha256_depuis_les_notes():
    digest = "ab" * 32
    body = f"## Nouveautes\n\nSHA-256 de Carib_Setup.exe : {digest}\n"
    assert updater._extract_sha256([], body, "Carib_Setup.exe") == digest


def test_extract_sha256_ambigu_renvoie_vide():
    body = "aa" * 32 + " et " + "bb" * 32
    assert updater._extract_sha256([], body, "Carib_Setup.exe") == ""


# ---------------------------------------------------------------------------
# Preferences
# ---------------------------------------------------------------------------

@pytest.fixture
def prefs_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(updater, "_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(updater, "_PREFS_FILE", str(tmp_path / "update.json"))
    return tmp_path


def test_prefs_par_defaut_ne_declenchent_aucune_connexion(prefs_tmp):
    """Tant que l'utilisateur n'a pas repondu, `enabled` vaut None."""
    prefs = updater.UpdatePrefs.load()
    assert prefs.enabled is None
    assert not prefs.due()


def test_prefs_aller_retour(prefs_tmp):
    prefs = updater.UpdatePrefs(enabled=True, skipped_version="9.9.9",
                                last_check=123.0)
    prefs.save()
    again = updater.UpdatePrefs.load()
    assert again.enabled is True
    assert again.skipped_version == "9.9.9"
    assert again.last_check == 123.0


def test_prefs_fichier_corrompu(prefs_tmp):
    (prefs_tmp / "update.json").write_text("{ pas du json", encoding="utf-8")
    assert updater.UpdatePrefs.load().enabled is None


def test_due_respecte_l_intervalle(prefs_tmp):
    prefs = updater.UpdatePrefs(enabled=True, last_check=1000.0)
    assert not prefs.due(now=1000.0 + updater.CHECK_INTERVAL - 1)
    assert prefs.due(now=1000.0 + updater.CHECK_INTERVAL + 1)


def test_desactive_ne_verifie_jamais(prefs_tmp):
    assert not updater.UpdatePrefs(enabled=False, last_check=0.0).due(now=1e9)


# ---------------------------------------------------------------------------
# check() — faux GitHub
# ---------------------------------------------------------------------------

class _FakeResponse:
    def __init__(self, payload=None, status=200, text="", chunks=None,
                 url="https://objects.githubusercontent.com/x", headers=None):
        self._payload = payload
        self.status_code = status
        self.text = text
        self.url = url
        self.headers = headers or {}
        self._chunks = chunks or []

    def json(self):
        if self._payload is None:
            raise ValueError("pas de JSON")
        return self._payload

    def iter_content(self, chunk_size=0):
        return iter(self._chunks)

    def close(self):
        pass


class _FakeHttp:
    """Remplace `requests` : enregistre les URL demandees."""

    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def get(self, url, **kw):
        self.calls.append(url)
        for prefix, response in self.routes.items():
            if url.startswith(prefix):
                if isinstance(response, Exception):
                    raise response
                return response
        return _FakeResponse(status=404)


RELEASE_URL = "https://api.github.com/repos/caribtechstudio/carib-text-editor/releases/latest"


def _release(tag="v0.15.0", assets=None, body=""):
    return {
        "tag_name": tag,
        "name": f"Carib {tag}",
        "body": body,
        "html_url": "https://github.com/caribtechstudio/carib-text-editor/releases/tag/" + tag,
        "published_at": "2026-08-15T10:00:00Z",
        "assets": assets or [],
    }


def test_check_detecte_une_version_plus_recente():
    asset = {"name": "Carib_v0.15.0_Setup.exe", "size": 1234,
             "browser_download_url":
                 "https://github.com/caribtechstudio/carib-text-editor/releases/download/v0.15.0/Carib_v0.15.0_Setup.exe"}
    http = _FakeHttp({RELEASE_URL: _FakeResponse(_release(assets=[asset]))})

    info = updater.check("0.14.0", session=http)

    assert info is not None
    assert info.version == "0.15.0"
    assert info.asset_name == "Carib_v0.15.0_Setup.exe"
    assert info.asset_size == 1234
    assert info.can_download


def test_check_a_jour_renvoie_none():
    http = _FakeHttp({RELEASE_URL: _FakeResponse(_release(tag="v0.14.0"))})
    assert updater.check("0.14.0", session=http) is None


def test_check_sans_release_publiee():
    """404 sur un depot neuf : ce n'est pas une erreur."""
    http = _FakeHttp({RELEASE_URL: _FakeResponse(status=404)})
    assert updater.check("0.14.0", session=http) is None


def test_check_limite_de_debit():
    http = _FakeHttp({RELEASE_URL: _FakeResponse(status=403)})
    with pytest.raises(updater.UpdateError):
        updater.check("0.14.0", session=http)


def test_check_erreur_reseau():
    http = _FakeHttp({RELEASE_URL: OSError("reseau coupe")})
    with pytest.raises(updater.UpdateError):
        updater.check("0.14.0", session=http)


def test_check_sans_depot_configure():
    assert updater.check("0.14.0", repo="") is None


def test_check_release_sans_installeur():
    """Une release sans .exe reste signalee, mais non telechargeable."""
    http = _FakeHttp({RELEASE_URL: _FakeResponse(
        _release(assets=[{"name": "notes.txt"}]))})
    info = updater.check("0.14.0", session=http)
    assert info is not None
    assert not info.can_download


def test_check_recupere_l_empreinte_depuis_sha256sums():
    digest = "ab" * 32
    sums_url = "https://github.com/caribtechstudio/carib-text-editor/releases/download/v0.15.0/SHA256SUMS.txt"
    assets = [
        {"name": "Carib_v0.15.0_Setup.exe", "size": 10,
         "browser_download_url":
             "https://github.com/caribtechstudio/carib-text-editor/releases/download/v0.15.0/Carib_v0.15.0_Setup.exe"},
        {"name": "SHA256SUMS.txt", "browser_download_url": sums_url},
    ]
    http = _FakeHttp({
        RELEASE_URL: _FakeResponse(_release(assets=assets)),
        sums_url: _FakeResponse(text=f"{digest}  Carib_v0.15.0_Setup.exe\n"),
    })

    info = updater.check("0.14.0", session=http)
    assert info.sha256 == digest


# ---------------------------------------------------------------------------
# download() — verifications avant execution
# ---------------------------------------------------------------------------

@pytest.fixture
def download_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(updater, "_DOWNLOAD_DIR", str(tmp_path / "updates"))
    # La verification Authenticode est propre a Windows et n'a pas de sens
    # sur un fichier de test : on la neutralise ici, elle a son propre test.
    monkeypatch.setattr(updater, "verify_signature",
                        lambda path: ("skipped", "test"))
    return tmp_path


def _info(payload: bytes, *, sha="", size=None):
    return updater.UpdateInfo(
        version="0.15.0", tag="v0.15.0",
        asset_name="Carib_v0.15.0_Setup.exe",
        asset_url="https://github.com/caribtechstudio/carib-text-editor/releases/download/v0.15.0/Carib_v0.15.0_Setup.exe",
        asset_size=len(payload) if size is None else size,
        sha256=sha)


def test_download_verifie_l_empreinte(download_tmp):
    payload = b"installeur factice"
    digest = hashlib.sha256(payload).hexdigest()
    info = _info(payload, sha=digest)
    http = _FakeHttp({"https://github.com": _FakeResponse(chunks=[payload])})

    path = updater.download(info, session=http)

    assert os.path.isfile(path)
    with open(path, "rb") as fh:
        assert fh.read() == payload


def test_download_refuse_une_empreinte_incorrecte(download_tmp):
    payload = b"contenu altere"
    info = _info(payload, sha="ff" * 32)
    http = _FakeHttp({"https://github.com": _FakeResponse(chunks=[payload])})

    with pytest.raises(updater.UpdateError, match="empreinte"):
        updater.download(info, session=http)

    # Le fichier suspect ne doit rester nulle part.
    assert not os.path.exists(
        os.path.join(updater._DOWNLOAD_DIR, info.asset_name))
    assert not os.path.exists(
        os.path.join(updater._DOWNLOAD_DIR, info.asset_name + ".part"))


def test_download_refuse_une_taille_incoherente(download_tmp):
    payload = b"trop court"
    info = _info(payload, size=99999)
    http = _FakeHttp({"https://github.com": _FakeResponse(chunks=[payload])})

    with pytest.raises(updater.UpdateError, match="incomplet"):
        updater.download(info, session=http)


def test_download_refuse_une_origine_non_github(download_tmp):
    info = _info(b"x")
    info.asset_url = "https://evil.example.com/Setup.exe"
    with pytest.raises(updater.UpdateError):
        updater.download(info, session=_FakeHttp({}))


def test_download_refuse_une_redirection_hors_github(download_tmp):
    """L'URL finale compte autant que l'URL initiale."""
    payload = b"charge utile"
    info = _info(payload)
    http = _FakeHttp({"https://github.com": _FakeResponse(
        chunks=[payload], url="https://evil.example.com/Setup.exe")})

    with pytest.raises(updater.UpdateError):
        updater.download(info, session=http)


def test_download_annulable(download_tmp):
    cancel = threading.Event()
    cancel.set()
    info = _info(b"abc")
    http = _FakeHttp({"https://github.com": _FakeResponse(chunks=[b"a", b"b"])})

    with pytest.raises(updater.UpdateCancelled):
        updater.download(info, cancel=cancel, session=http)

    assert not os.path.exists(
        os.path.join(updater._DOWNLOAD_DIR, info.asset_name + ".part"))


def test_download_signale_la_progression(download_tmp):
    payload = b"0123456789"
    seen = []
    info = _info(payload)
    http = _FakeHttp({"https://github.com": _FakeResponse(
        chunks=[payload[:5], payload[5:]])})

    updater.download(info, on_progress=lambda r, t: seen.append((r, t)),
                     session=http)

    assert seen == [(5, 10), (10, 10)]


def test_download_sans_installeur():
    info = updater.UpdateInfo(version="1.0.0", tag="v1.0.0")
    with pytest.raises(updater.UpdateError):
        updater.download(info)


def test_download_refuse_une_signature_invalide(download_tmp, monkeypatch):
    """Une signature *presente mais invalide* signale un fichier altere."""
    payload = b"binaire trafique"
    monkeypatch.setattr(updater, "verify_signature",
                        lambda path: ("invalid", "digest incorrect"))
    info = _info(payload)
    http = _FakeHttp({"https://github.com": _FakeResponse(chunks=[payload])})

    with pytest.raises(updater.UpdateError, match="signature"):
        updater.download(info, session=http)

    assert not os.path.exists(
        os.path.join(updater._DOWNLOAD_DIR, info.asset_name))


def test_download_tolere_un_binaire_non_signe(download_tmp, monkeypatch):
    """Tant que Carib n'est pas signe, l'absence de signature est acceptee."""
    payload = b"binaire non signe"
    monkeypatch.setattr(updater, "verify_signature",
                        lambda path: ("unsigned", "aucune signature"))
    info = _info(payload)
    http = _FakeHttp({"https://github.com": _FakeResponse(chunks=[payload])})

    assert os.path.isfile(updater.download(info, session=http))


def test_download_purge_les_anciens_telechargements(download_tmp):
    os.makedirs(updater._DOWNLOAD_DIR, exist_ok=True)
    vieux = os.path.join(updater._DOWNLOAD_DIR, "Carib_v0.13.0_Setup.exe")
    with open(vieux, "wb") as fh:
        fh.write(b"ancien")

    payload = b"nouveau"
    info = _info(payload)
    http = _FakeHttp({"https://github.com": _FakeResponse(chunks=[payload])})
    updater.download(info, session=http)

    assert not os.path.exists(vieux)


# ---------------------------------------------------------------------------
# Signature
# ---------------------------------------------------------------------------

def test_verify_signature_sur_un_fichier_quelconque(tmp_path):
    """Un fichier texte n'est pas signe : ni « trusted », ni plantage."""
    target = tmp_path / "faux.exe"
    target.write_bytes(b"pas un PE")
    state, _detail = updater.verify_signature(str(target))
    assert state in ("unsigned", "invalid", "skipped")


def test_launch_installer_refuse_un_chemin_absent():
    with pytest.raises(updater.UpdateError):
        updater.launch_installer("/introuvable/Setup.exe")


# ---------------------------------------------------------------------------
# Aller-retour avec tools/make_release.py
# ---------------------------------------------------------------------------

def test_le_format_produit_par_make_release_est_relisible(tmp_path, monkeypatch):
    """Le fichier ecrit a la publication doit etre lu par l'updater.

    C'est la jointure la plus fragile de toute la chaine de mise a jour :
    `tools/make_release.py` ecrit SHA256SUMS.txt sur la machine de build, et
    `models/updater.py` le relit des mois plus tard chez l'utilisateur. Si les
    deux formats divergent, l'empreinte n'est plus verifiee — en silence.
    """
    import importlib.util
    import os

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    spec = importlib.util.spec_from_file_location(
        "make_release", os.path.join(root, "tools", "make_release.py"))
    make_release = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(make_release)

    output = tmp_path / "Output"
    output.mkdir()
    installer = output / "Carib_v9.9.9_Setup.exe"
    installer.write_bytes(b"contenu de l'installeur")

    monkeypatch.setattr(make_release, "OUTPUT_DIR", str(output))
    monkeypatch.setattr(make_release, "is_signed", lambda path: False)
    assert make_release.write_sums("9.9.9") == 0

    content = (output / "SHA256SUMS.txt").read_text(encoding="utf-8")
    attendu = hashlib.sha256(b"contenu de l'installeur").hexdigest()

    # Le parseur de l'updater doit y retrouver exactement cette empreinte.
    assert updater._parse_sums(content, "Carib_v9.9.9_Setup.exe") == attendu


def test_make_release_detecte_une_empreinte_perimee(tmp_path, monkeypatch):
    """Signer apres avoir calcule les empreintes doit etre rattrape."""
    import importlib.util
    import os

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    spec = importlib.util.spec_from_file_location(
        "make_release2", os.path.join(root, "tools", "make_release.py"))
    make_release = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(make_release)

    output = tmp_path / "Output"
    output.mkdir()
    installer = output / "Carib_v9.9.9_Setup.exe"
    installer.write_bytes(b"avant signature")

    monkeypatch.setattr(make_release, "OUTPUT_DIR", str(output))
    monkeypatch.setattr(make_release, "is_signed", lambda path: False)
    make_release.write_sums("9.9.9")

    # L'installeur est signe : son contenu change, donc son empreinte.
    installer.write_bytes(b"apres signature, contenu different")

    assert make_release.verify_sums() == 1
