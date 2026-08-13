"""Tests de l'ordonnanceur unique."""

import threading
import time

import pytest

from models.scheduler import Scheduler


@pytest.fixture
def sched():
    s = Scheduler(name="test-scheduler")
    yield s
    s.stop()


def wait_for(predicate, timeout=3.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


# ---------------------------------------------------------------------------
# Comportement de base
# ---------------------------------------------------------------------------

def test_execute_apres_le_delai(sched):
    fired = threading.Event()
    sched.schedule("t", 0.05, fired.set)
    assert not fired.is_set()
    assert fired.wait(2.0)


def test_plusieurs_taches_dans_lordre_des_echeances(sched):
    order = []
    sched.schedule("c", 0.15, lambda: order.append("c"))
    sched.schedule("a", 0.05, lambda: order.append("a"))
    sched.schedule("b", 0.10, lambda: order.append("b"))

    assert wait_for(lambda: len(order) == 3)
    assert order == ["a", "b", "c"]


def test_annulation(sched):
    fired = threading.Event()
    sched.schedule("t", 0.05, fired.set)
    sched.cancel("t")
    assert not fired.wait(0.3)


def test_annulation_dune_tache_inexistante_ne_leve_pas(sched):
    sched.cancel("jamais-programmee")


# ---------------------------------------------------------------------------
# Anti-rebond : c'est le cas d'usage central
# ---------------------------------------------------------------------------

def test_reprogrammer_remplace_lecheance(sched):
    """Le comportement qui remplace les `threading.Timer` de la frappe :
    cent frappes ne doivent produire qu'une seule exécution."""
    calls = []
    for i in range(100):
        sched.schedule("frappe", 0.08, lambda i=i: calls.append(i))
        time.sleep(0.001)

    assert wait_for(lambda: calls)
    time.sleep(0.15)
    assert len(calls) == 1
    assert calls[0] == 99          # c'est bien le dernier rappel qui gagne


def test_une_seule_tache_en_attente_par_cle(sched):
    for _ in range(50):
        sched.schedule("k", 5.0, lambda: None)
    assert sched.pending == 1
    assert sched.is_pending("k")


def test_les_cles_distinctes_coexistent(sched):
    sched.schedule("a", 5.0, lambda: None)
    sched.schedule("b", 5.0, lambda: None)
    assert sched.pending == 2


# ---------------------------------------------------------------------------
# Un seul thread, quel que soit le volume
# ---------------------------------------------------------------------------

def test_aucun_thread_supplementaire_par_tache(sched):
    """Le défaut corrigé : `threading.Timer` créait un thread OS par frappe."""
    before = threading.active_count()
    sched.schedule("amorce", 5.0, lambda: None)
    time.sleep(0.05)
    after_first = threading.active_count()

    for i in range(200):
        sched.schedule(f"t{i}", 5.0, lambda: None)
    time.sleep(0.05)

    # 200 tâches supplémentaires, zéro thread supplémentaire.
    assert threading.active_count() == after_first
    assert after_first == before + 1


# ---------------------------------------------------------------------------
# Robustesse
# ---------------------------------------------------------------------------

def test_une_tache_qui_echoue_ne_tue_pas_lordonnanceur(sched):
    survivor = threading.Event()

    def boom():
        raise RuntimeError("échec volontaire")

    sched.schedule("boom", 0.02, boom)
    sched.schedule("suite", 0.08, survivor.set)
    assert survivor.wait(2.0)


def test_flush_execute_immediatement(sched):
    calls = []
    sched.schedule("t", 10.0, lambda: calls.append(1))
    sched.flush("t")
    assert calls == [1]
    assert not sched.is_pending("t")


def test_flush_sans_tache_ne_leve_pas(sched):
    sched.flush("inconnue")


def test_stop_abandonne_les_taches(sched):
    fired = threading.Event()
    sched.schedule("t", 0.05, fired.set)
    sched.stop()
    assert not fired.wait(0.3)
    assert sched.pending == 0


def test_cancel_all(sched):
    for i in range(10):
        sched.schedule(f"t{i}", 5.0, lambda: None)
    sched.cancel_all()
    assert sched.pending == 0


def test_delai_negatif_execute_tout_de_suite(sched):
    fired = threading.Event()
    sched.schedule("t", -5, fired.set)
    assert fired.wait(2.0)
