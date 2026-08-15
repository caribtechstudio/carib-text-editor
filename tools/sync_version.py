"""
tools/sync_version.py — Propage APP_VERSION dans les fichiers de build.

`core/constants.py` est la seule source de verite du numero de version. Ce
script y lit `APP_VERSION` et le recopie dans les fichiers qui ne peuvent pas
importer Python au moment ou ils sont lus :

  * `pyproject.toml`      → app.version
  * `installer/setup.iss` → #define AppVersion

`build.bat` l'appelle avant chaque compilation. Il est aussi execute par
l'integration continue en mode `--check`, qui echoue si les fichiers ont
divergé — c'est ce qui empeche qu'un installeur reparte avec l'ancien numero.

Usage :
    python tools/sync_version.py            # ecrit
    python tools/sync_version.py --check     # verifie seulement
"""

import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read_version() -> str:
    """Lit APP_VERSION sans importer le paquet (donc sans importer flet)."""
    path = os.path.join(ROOT, "core", "constants.py")
    with io.open(path, encoding="utf-8") as fh:
        source = fh.read()
    match = re.search(r'^APP_VERSION\s*=\s*"([^"]+)"', source, re.MULTILINE)
    if not match:
        raise SystemExit("APP_VERSION introuvable dans core/constants.py")
    return match.group(1)


#: (chemin relatif, motif, remplacement gabarit)
TARGETS = (
    ("pyproject.toml",
     re.compile(r'^(app\.version\s*=\s*")[^"]*(")', re.MULTILINE),
     r"\g<1>{v}\g<2>"),
    (os.path.join("installer", "setup.iss"),
     re.compile(r'^(#define\s+AppVersion\s+")[^"]*(")', re.MULTILINE),
     r"\g<1>{v}\g<2>"),
)


def main(argv) -> int:
    check_only = "--check" in argv
    version = read_version()
    print(f"Version de reference : {version}")

    stale = []
    for rel, pattern, template in TARGETS:
        path = os.path.join(ROOT, rel)
        if not os.path.isfile(path):
            print(f"  ignore  {rel} (absent)")
            continue

        with io.open(path, encoding="utf-8") as fh:
            original = fh.read()

        updated, count = pattern.subn(template.format(v=version), original)
        if count == 0:
            print(f"  ATTENTION  {rel} : motif de version introuvable")
            stale.append(rel)
            continue

        if updated == original:
            print(f"  a jour  {rel}")
            continue

        if check_only:
            print(f"  PERIME  {rel}")
            stale.append(rel)
        else:
            with io.open(path, "w", encoding="utf-8", newline="") as fh:
                fh.write(updated)
            print(f"  ecrit   {rel}")

    if stale:
        if check_only:
            print("\nEchec : lancez « python tools/sync_version.py » "
                  "et validez les fichiers modifies.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
