"""
models/startup_probe.py — Mesure du temps de démarrage réel.

Mesurer « à la main » un exécutable Flutter ne marche pas : `WaitForInputIdle`
suppose une boucle de messages Win32 que Flutter n'utilise pas, et une fenêtre
peut exister avant d'avoir affiché quoi que ce soit.

L'application se chronomètre donc elle-même. Le lanceur (`tools/measure_startup.py`)
passe l'horodatage de départ dans `CARIB_T0` et un fichier de sortie dans
`CARIB_STARTUP_LOG` ; Carib y inscrit le délai écoulé au moment où la première
image est réellement peinte. Le chiffre inclut donc **tout** : bootloader
PyInstaller, démarrage de l'interpréteur, imports, moteur Flutter.

Sans ces variables d'environnement, le module ne coûte rien : deux lectures
de `os.environ` au lancement.
"""

import os
import time

#: Horodatage de référence. Le lanceur le fournit pour englober le coût du
#: bootloader ; à défaut, on part du chargement de ce module.
T0 = float(os.environ.get("CARIB_T0") or 0) or time.time()

_LOG_PATH = os.environ.get("CARIB_STARTUP_LOG") or ""
_seen: set[str] = set()


def enabled() -> bool:
    return bool(_LOG_PATH)


def mark(label: str) -> float | None:
    """Consigne le passage à une étape du démarrage.

    Chaque étiquette n'est enregistrée qu'une fois : les jalons posés dans
    du code réexécuté (comme `rebuild`) ne polluent pas la mesure.
    """
    if not _LOG_PATH or label in _seen:
        return None
    _seen.add(label)

    elapsed = time.time() - T0
    try:
        with open(_LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(f"{label}\t{elapsed:.3f}\n")
    except OSError:
        pass
    return elapsed


def record_first_frame(label: str = "first_frame") -> float | None:
    """Jalon final : la première image est peinte."""
    return mark(label)
