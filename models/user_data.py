"""
models/user_data.py — Inventaire et effacement des données locales.

Un utilisateur doit pouvoir savoir ce que Carib garde sur sa machine, et
l'effacer sans chercher un dossier caché. C'est ce que le RGPD appelle un
droit d'effacement ; ici il s'exerce entièrement en local, puisque aucune
donnée n'est envoyée nulle part.

Ce module est aussi la référence unique de « ce que Carib écrit » : la
politique de confidentialité décrit exactement cette liste, et la routine de
désinstallation supprime exactement ce dossier.
"""

import os
import shutil

_DATA_DIR = os.path.join(os.path.expanduser("~"), ".carib")

#: (nom de fichier ou dossier, libellé, contient des données sensibles ?)
ENTRIES = (
    ("session.json", "Session : onglets ouverts, fichiers récents, réglages", True),
    ("recovery", "Journal de récupération après interruption", True),
    ("credentials.dat", "Clés API (chiffrées par Windows)", True),
    ("llm.json", "Réglages d'intelligence artificielle", False),
    ("update.json", "Préférences de mise à jour", False),
    ("llm_models.json", "Liste des modèles mise en cache", False),
    ("logs", "Journal technique", False),
    ("updates", "Installeurs téléchargés", False),
    ("ipc.token", "Jeton d'instance unique", False),
)


def data_dir() -> str:
    return _DATA_DIR


def exists() -> bool:
    return os.path.isdir(_DATA_DIR)


def total_size() -> int:
    """Taille cumulée, en octets. 0 si le dossier n'existe pas."""
    total = 0
    for root, _dirs, files in os.walk(_DATA_DIR):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except OSError:
                pass
    return total


def inventory() -> list[tuple[str, str, int]]:
    """Ce qui existe réellement : [(libellé, chemin, octets)]."""
    found = []
    for name, label, _sensitive in ENTRIES:
        path = os.path.join(_DATA_DIR, name)
        if not os.path.exists(path):
            continue
        if os.path.isdir(path):
            size = sum(
                os.path.getsize(os.path.join(r, f))
                for r, _d, fs in os.walk(path) for f in fs
                if os.path.exists(os.path.join(r, f)))
        else:
            try:
                size = os.path.getsize(path)
            except OSError:
                size = 0
        found.append((label, path, size))
    return found


def erase(*, keep_credentials: bool = False) -> tuple[int, list[str]]:
    """Efface les données locales. Retourne (nb_supprimés, erreurs).

    `keep_credentials` conserve les clés API : effacer sa session ne doit pas
    obliger à ressaisir trois clés API si ce n'est pas ce qu'on voulait.
    """
    removed = 0
    errors: list[str] = []

    for name, _label, _sensitive in ENTRIES:
        if keep_credentials and name == "credentials.dat":
            continue
        path = os.path.join(_DATA_DIR, name)
        if not os.path.exists(path):
            continue
        try:
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
            removed += 1
        except OSError as exc:
            errors.append(f"{name} : {exc}")

    # Fichiers temporaires laissés par une écriture atomique interrompue.
    try:
        for name in os.listdir(_DATA_DIR):
            if name.endswith(".tmp"):
                try:
                    os.remove(os.path.join(_DATA_DIR, name))
                except OSError:
                    pass
    except OSError:
        pass

    return removed, errors


def human_size(num_bytes: int) -> str:
    if num_bytes <= 0:
        return "0 o"
    for unit in ("o", "Ko", "Mo", "Go"):
        if num_bytes < 1024 or unit == "Go":
            return f"{num_bytes:.0f} {unit}" if unit == "o" else f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} Go"
