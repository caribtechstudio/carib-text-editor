"""
tests/test_privacy_and_logging.py — Garde-fous de confidentialite.

Ces tests protegent des promesses ecrites dans CONFIDENTIALITE.md. Si l'un
d'eux tombe, ce n'est pas une regression fonctionnelle : c'est la politique
de confidentialite qui devient fausse.
"""

import logging
import os

import pytest

from core import logging_setup
from models import user_data


# ---------------------------------------------------------------------------
# Aucun envoi audio vers un tiers
# ---------------------------------------------------------------------------

def test_aucune_reconnaissance_vocale_distante():
    """`recognize_google` envoyait le micro chez Google sans consentement.

    Le retrait est le correctif le plus important de la 0.14.0 : ce test
    empeche sa reintroduction par inadvertance.
    """
    from models import voice_manager

    source = open(voice_manager.__file__, encoding="utf-8").read()
    assert "recognize_google" not in source.split('"""', 2)[-1], \
        "recognize_google est de retour dans le code de voice_manager"

    assert not hasattr(voice_manager, "sr_available")
    assert not hasattr(voice_manager.VoiceManager, "listen_speech")


def test_speech_recognition_absent_des_dependances():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(root, "requirements.txt"), encoding="utf-8") as fh:
        lines = [l.strip() for l in fh if l.strip() and not l.startswith("#")]
    assert not any("speechrecognition" in l.lower() for l in lines)


# ---------------------------------------------------------------------------
# Le journal ne doit jamais publier de secret
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("prefixe, corps", [
    ("sk-" "proj-", "AbCdEf0123456789XyZ"),
    ("sk-" "ant-api03-", "abcdefghijklmnop"),
    ("AI" "za", "SyA1b2C3d4E5f6G7h8I9j0KlMnOpQrStUv"),
])
def test_les_cles_api_sont_masquees(prefixe, corps):
    """Les fausses cles sont assemblees a l'execution, jamais ecrites en un
    seul morceau : une chaine ayant la forme complete d'une cle declencherait
    le « secret scanning » de GitHub, qui peut bloquer une poussee. Le
    redacteur, lui, voit bien la cle entiere — c'est ce qu'on teste."""
    secret = prefixe + corps
    masque = logging_setup.redact(f"echec avec la cle {secret} sur /v1/chat")
    assert secret not in masque
    assert "cle-masquee" in masque


def test_les_en_tetes_d_autorisation_sont_masques():
    masque = logging_setup.redact("Authorization: Bearer abcdef1234567890")
    assert "abcdef1234567890" not in masque


def test_redact_laisse_le_texte_ordinaire_intact():
    texte = "Ouverture de C:/Users/Arnaud/notes.txt (1240 caracteres)"
    assert logging_setup.redact(texte) == texte


def test_le_filtre_masque_aussi_les_arguments(tmp_path):
    """La redaction doit survivre au formatage differe de `logging`."""
    record = logging.LogRecord(
        "carib", logging.ERROR, __file__, 1,
        "cle refusee : %s", ("sk-" "proj-SECRET0123456789abc",), None)
    logging_setup._RedactingFilter().filter(record)
    assert "SECRET0123456789abc" not in record.getMessage()


# ---------------------------------------------------------------------------
# Effacement des donnees locales
# ---------------------------------------------------------------------------

@pytest.fixture
def fake_data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(user_data, "_DATA_DIR", str(tmp_path))
    (tmp_path / "session.json").write_text("{}", encoding="utf-8")
    (tmp_path / "llm.json").write_text("{}", encoding="utf-8")
    (tmp_path / "credentials.dat").write_bytes(b"chiffre")
    (tmp_path / "logs").mkdir()
    (tmp_path / "logs" / "carib.log").write_text("trace", encoding="utf-8")
    return tmp_path


def test_inventaire_liste_ce_qui_existe(fake_data_dir):
    labels = [label for label, _path, _size in user_data.inventory()]
    assert len(labels) == 4
    assert any("Session" in l for l in labels)


def test_effacement_complet(fake_data_dir):
    removed, errors = user_data.erase()
    assert errors == []
    assert removed == 4
    assert not (fake_data_dir / "session.json").exists()
    assert not (fake_data_dir / "credentials.dat").exists()
    assert not (fake_data_dir / "logs").exists()


def test_effacement_conserve_les_cles_si_demande(fake_data_dir):
    user_data.erase(keep_credentials=True)
    assert (fake_data_dir / "credentials.dat").exists()
    assert not (fake_data_dir / "session.json").exists()


def test_effacement_sur_un_dossier_vide(tmp_path, monkeypatch):
    monkeypatch.setattr(user_data, "_DATA_DIR", str(tmp_path / "absent"))
    removed, errors = user_data.erase()
    assert (removed, errors) == (0, [])


def test_human_size():
    assert user_data.human_size(0) == "0 o"
    assert user_data.human_size(512) == "512 o"
    assert "Ko" in user_data.human_size(2048)
    assert "Mo" in user_data.human_size(5 * 1024 * 1024)


# ---------------------------------------------------------------------------
# Les documents legaux voyagent avec l'application
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("filename", [
    "LICENSE.txt", "EULA.txt", "TIERS.txt", "CONFIDENTIALITE.md",
])
def test_les_documents_legaux_sont_presents(filename):
    from core.constants import resource_path

    path = resource_path(filename)
    assert os.path.isfile(path), f"{filename} manquant : le build echouera"
    assert os.path.getsize(path) > 200


def test_l_attribution_flaticon_est_presente():
    """Condition de la licence gratuite Flaticon : attribution visible."""
    source = open(
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "views", "dialogs", "info_dialog.py"),
        encoding="utf-8").read()
    assert "Flaticon" in source
    assert "flaticon.com" in source.lower()
