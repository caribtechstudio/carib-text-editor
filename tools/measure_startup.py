"""
tools/measure_startup.py — Chronomètre le démarrage de Carib.

Lance l'application plusieurs fois et relève le délai entre le lancement du
processus et l'affichage de la première image, tel que mesuré par
l'application elle-même (voir models/startup_probe.py).

    python tools/measure_startup.py                    # source
    python tools/measure_startup.py dist/Carib/Carib.exe
    python tools/measure_startup.py dist/Carib/Carib.exe --runs 5

La première exécution après un build est toujours plus lente (cache disque
froid, analyse antivirus) : le minimum est plus représentatif que la moyenne.
"""

import argparse
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
#: Au-delà, on considère que l'application ne démarrera pas.
LAUNCH_TIMEOUT = 60
#: Délai laissé à la fenêtre après la première image avant de fermer.
SETTLE = 1.0


def run_once(target: list[str], log_path: Path) -> list[tuple[str, float]] | None:
    """Lance l'application une fois et retourne les jalons franchis."""
    if log_path.exists():
        log_path.unlink()

    env = dict(os.environ)
    env["CARIB_T0"] = repr(time.time())
    env["CARIB_STARTUP_LOG"] = str(log_path)

    process = subprocess.Popen(target, cwd=str(ROOT), env=env,
                               stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
    deadline = time.time() + LAUNCH_TIMEOUT
    marks: list[tuple[str, float]] = []
    try:
        while time.time() < deadline:
            try:
                content = log_path.read_text(encoding="utf-8")
            except OSError:
                content = ""
            # On attend le jalon final : les précédents arrivent avant lui.
            if "4_premiere_image" in content:
                marks = [(line.split("\t")[0], float(line.split("\t")[1]))
                         for line in content.strip().split("\n") if "\t" in line]
                break
            if process.poll() is not None:
                break
            time.sleep(0.02)
        time.sleep(SETTLE)
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
    return marks


def main():
    parser = argparse.ArgumentParser(description="Mesure le démarrage de Carib.")
    parser.add_argument("exe", nargs="?", default="",
                        help="Exécutable à mesurer (défaut : lancer les sources).")
    parser.add_argument("--runs", type=int, default=3)
    args = parser.parse_args()

    if args.exe:
        target = [str(Path(args.exe).resolve())]
        label = args.exe
    else:
        target = [sys.executable, str(ROOT / "carib.py")]
        label = "sources Python"

    print(f"Mesure de « {label} » — {args.runs} lancement(s)\n")

    with tempfile.TemporaryDirectory() as tmp:
        log_path = Path(tmp) / "startup.tsv"
        results = []
        for i in range(1, args.runs + 1):
            elapsed = run_once(target, log_path)
            if not elapsed:
                print(f"  essai {i} : échec (aucune première image)")
            else:
                total = elapsed[-1][1]
                results.append(total)
                detail = "  ".join(f"{name.split('_', 1)[1]}={t:.2f}"
                                   for name, t in elapsed)
                print(f"  essai {i} : {total:5.2f} s   [{detail}]")
            time.sleep(1.0)

    if not results:
        print("\nAucune mesure exploitable.")
        return 1

    print(f"\n  minimum  : {min(results):5.2f} s   <- le plus représentatif")
    print(f"  médiane  : {sorted(results)[len(results) // 2]:5.2f} s")
    print(f"  maximum  : {max(results):5.2f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
