"""
Tests d'intégrité des fichiers — la partie la plus critique de l'application.

Un éditeur de texte qui corrompt les fichiers de ses utilisateurs n'a aucune
valeur, quelles que soient ses autres qualités.
"""

import os

import pytest

from models.file_manager import (BinaryFileError, FileTooLargeError,
                                 detect_newline, file_changed_on_disk,
                                 load_file, rename_file_on_disk, write_file)


# ---------------------------------------------------------------------------
# Fins de ligne
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text, expected", [
    ("a\r\nb\r\nc", "\r\n"),
    ("a\nb\nc", "\n"),
    ("a\rb\rc", "\r"),
    ("a\r\nb\r\nc\nd", "\r\n"),      # CRLF majoritaire
    ("une seule ligne", os.linesep if os.linesep in ("\r\n", "\n") else "\n"),
])
def test_detect_newline(text, expected):
    assert detect_newline(text) == expected


def test_crlf_est_preserve_apres_aller_retour(tmp_path):
    """Le bug le plus insidieux : ouvrir puis enregistrer réécrivait tout le
    fichier en LF, produisant un diff Git de 100 % des lignes."""
    path = tmp_path / "windows.txt"
    path.write_bytes(b"ligne 1\r\nligne 2\r\nligne 3\r\n")

    loaded = load_file(str(path))
    assert loaded.newline == "\r\n"
    assert loaded.text == "ligne 1\nligne 2\nligne 3\n"   # normalisé en mémoire

    write_file(str(path), loaded.text, encoding=loaded.encoding,
               newline=loaded.newline)
    assert path.read_bytes() == b"ligne 1\r\nligne 2\r\nligne 3\r\n"


def test_lf_reste_lf(tmp_path):
    path = tmp_path / "unix.txt"
    path.write_bytes(b"a\nb\n")
    loaded = load_file(str(path))
    write_file(str(path), loaded.text, encoding=loaded.encoding,
               newline=loaded.newline)
    assert path.read_bytes() == b"a\nb\n"


# ---------------------------------------------------------------------------
# Encodage
# ---------------------------------------------------------------------------

def test_utf8_avec_accents(tmp_path):
    path = tmp_path / "fr.txt"
    path.write_bytes("Éléphant à Noël".encode("utf-8"))
    loaded = load_file(str(path))
    assert loaded.text == "Éléphant à Noël"
    assert loaded.encoding == "utf-8"
    assert loaded.confident


def test_bom_utf8_detecte_et_conserve(tmp_path):
    path = tmp_path / "bom.txt"
    path.write_bytes(b"\xef\xbb\xbf" + "Café".encode("utf-8"))
    loaded = load_file(str(path))
    assert loaded.text == "Café"
    assert loaded.encoding == "utf-8-sig"

    write_file(str(path), loaded.text, encoding=loaded.encoding,
               newline=loaded.newline)
    assert path.read_bytes().startswith(b"\xef\xbb\xbf")


def test_cp1252_signale_comme_non_certain(tmp_path):
    """Un repli 8 bits doit être signalé : sans ça, une réécriture en UTF-8
    détruit silencieusement les caractères accentués."""
    path = tmp_path / "legacy.txt"
    path.write_bytes("Créé à Paris".encode("cp1252"))
    loaded = load_file(str(path))
    assert loaded.encoding != "utf-8"
    assert loaded.text == "Créé à Paris"


def test_fichier_binaire_refuse(tmp_path):
    path = tmp_path / "image.txt"
    path.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\x0d")
    with pytest.raises(BinaryFileError):
        load_file(str(path))


def test_fichier_trop_gros_refuse(tmp_path, monkeypatch):
    import models.file_manager as fm
    monkeypatch.setattr(fm, "MAX_FILE_BYTES", 10)
    path = tmp_path / "gros.txt"
    path.write_text("beaucoup trop de contenu ici")
    with pytest.raises(FileTooLargeError):
        load_file(str(path))


# ---------------------------------------------------------------------------
# Écriture atomique
# ---------------------------------------------------------------------------

def test_ecriture_atomique_ne_laisse_pas_de_temporaire(tmp_path):
    path = tmp_path / "doc.txt"
    write_file(str(path), "contenu")
    assert path.read_text(encoding="utf-8") == "contenu"
    assert list(tmp_path.iterdir()) == [path]      # aucun .tmp résiduel


def test_echec_decriture_preserve_le_fichier_original(tmp_path, monkeypatch):
    """La garantie centrale : un échec en cours d'écriture ne doit jamais
    laisser le fichier de l'utilisateur tronqué."""
    path = tmp_path / "precieux.txt"
    path.write_text("données originales", encoding="utf-8")

    import models.file_manager as fm
    real_replace = os.replace

    def exploding_replace(src, dst):
        raise OSError("disque plein")

    monkeypatch.setattr(fm.os, "replace", exploding_replace)
    with pytest.raises(OSError):
        write_file(str(path), "nouveau contenu")

    monkeypatch.setattr(fm.os, "replace", real_replace)
    assert path.read_text(encoding="utf-8") == "données originales"
    # Et le temporaire a bien été nettoyé.
    assert [p.name for p in tmp_path.iterdir()] == ["precieux.txt"]


def test_write_file_retourne_mtime_et_taille(tmp_path):
    path = tmp_path / "x.txt"
    mtime, size = write_file(str(path), "abc")
    assert size == 3
    assert mtime > 0


# ---------------------------------------------------------------------------
# Modification externe
# ---------------------------------------------------------------------------

def test_modification_externe_detectee(tmp_path):
    path = tmp_path / "partage.txt"
    write_file(str(path), "version 1")
    loaded = load_file(str(path))

    assert not file_changed_on_disk(str(path), loaded.mtime, loaded.size)

    path.write_text("version 2 nettement plus longue", encoding="utf-8")
    assert file_changed_on_disk(str(path), loaded.mtime, loaded.size)


# ---------------------------------------------------------------------------
# Renommage
# ---------------------------------------------------------------------------

def test_renommage_refuse_decraser_une_cible_existante(tmp_path):
    source = tmp_path / "a.txt"
    source.write_text("A")
    (tmp_path / "b.txt").write_text("B ne doit pas disparaitre")

    with pytest.raises(OSError):
        rename_file_on_disk(str(source), "b.txt")
    assert (tmp_path / "b.txt").read_text() == "B ne doit pas disparaitre"


def test_renommage_refuse_les_caracteres_interdits(tmp_path):
    source = tmp_path / "a.txt"
    source.write_text("A")
    with pytest.raises(OSError):
        rename_file_on_disk(str(source), "in/valide.txt")


def test_renommage_nominal(tmp_path):
    source = tmp_path / "avant.txt"
    source.write_text("contenu")
    new_path = rename_file_on_disk(str(source), "apres.txt")
    assert os.path.basename(new_path) == "apres.txt"
    assert not source.exists()
