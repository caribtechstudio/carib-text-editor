"""
Tests de l'icône de zone de notification.

L'icône conditionne le mode résident : sans elle, Glyph deviendrait un
processus invisible que l'utilisateur ne pourrait ni retrouver ni arrêter.
`AppController` refuse donc d'activer le mode si `start()` échoue — c'est ce
contrat qui est vérifié ici.
"""

import sys
import time

import pytest

from models.tray import TrayIcon

windows_only = pytest.mark.skipif(sys.platform != "win32",
                                  reason="Zone de notification propre à Windows")


def test_degradation_hors_windows(monkeypatch):
    """Sur un autre système, `start()` doit répondre False sans lever."""
    import models.tray as tray_module
    monkeypatch.setattr(tray_module, "_IS_WINDOWS", False)
    icon = TrayIcon("Test", None)
    assert icon.start() is False
    assert not icon.active
    icon.stop()               # ne doit pas lever non plus


@windows_only
def test_creation_et_retrait():
    icon = TrayIcon("Glyph — test", None)
    try:
        assert icon.start() is True
        assert icon.active
    finally:
        icon.stop()
        time.sleep(0.3)


@windows_only
def test_start_est_idempotent():
    icon = TrayIcon("Glyph — test", None)
    try:
        assert icon.start() is True
        assert icon.start() is True       # second appel : sans effet
    finally:
        icon.stop()
        time.sleep(0.3)


@windows_only
def test_icone_absente_utilise_le_repli():
    """Un chemin d'icône invalide ne doit pas empêcher l'affichage."""
    icon = TrayIcon("Glyph — test", "C:/chemin/qui/nexiste/pas.ico")
    try:
        assert icon.start() is True
    finally:
        icon.stop()
        time.sleep(0.3)


@windows_only
def test_stop_sans_start_ne_leve_pas():
    TrayIcon("Glyph", None).stop()


def test_une_exception_dans_un_rappel_est_absorbee():
    """Une exception remontant dans la WndProc corromprait la boucle de
    messages de Windows : elle doit être arrêtée à la frontière."""
    def boom():
        raise RuntimeError("échec volontaire")

    TrayIcon._safe(boom)          # ne doit pas lever
