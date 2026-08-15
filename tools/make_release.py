"""
tools/make_release.py — Prepare les fichiers a publier sur GitHub.

Produit `SHA256SUMS.txt` a cote de l'installeur, au format que
`models/updater.py` sait relire. C'est ce fichier qui permet a Carib de
verifier, chez l'utilisateur, que l'installeur telecharge est bien celui que
vous avez publie — et pas un fichier corrompu ou substitue en chemin.

**A lancer apres avoir signe l'installeur.** Signer modifie le fichier, donc
son empreinte : calculer avant la signature produit un SHA256SUMS.txt qui ne
correspondra a rien, et l'updater refusera la mise a jour.

Usage :
    python tools/make_release.py             # calcule et ecrit SHA256SUMS.txt
    python tools/make_release.py --verify    # re-verifie sans rien reecrire
"""

import hashlib
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(ROOT, "installer", "Output")
SUMS_NAME = "SHA256SUMS.txt"

_SHA256_RE = re.compile(r"\b([a-fA-F0-9]{64})\b")


def read_version() -> str:
    """Lit APP_VERSION sans importer le paquet (donc sans importer flet)."""
    path = os.path.join(ROOT, "core", "constants.py")
    with io.open(path, encoding="utf-8") as fh:
        match = re.search(r'^APP_VERSION\s*=\s*"([^"]+)"', fh.read(), re.MULTILINE)
    if not match:
        raise SystemExit("APP_VERSION introuvable dans core/constants.py")
    return match.group(1)


def sha256(path: str) -> str:
    """Empreinte d'un fichier, lu par blocs — un installeur pese ~150 Mo."""
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def find_installers(version: str) -> list[str]:
    """Installeurs presents dans installer/Output, version courante d'abord."""
    if not os.path.isdir(OUTPUT_DIR):
        return []
    names = [n for n in sorted(os.listdir(OUTPUT_DIR))
             if n.lower().endswith(".exe")]
    expected = f"Carib_v{version}_Setup.exe"
    if expected in names:
        return [expected]
    return names


def is_signed(path: str) -> bool:
    """L'installeur porte-t-il une signature Authenticode valide ?

    Purement informatif : le script n'echoue pas sur un binaire non signe,
    puisque la signature n'est pas encore en place. Mais mieux vaut le dire
    maintenant que le decouvrir apres publication.
    """
    if sys.platform != "win32":
        return False
    try:
        sys.path.insert(0, ROOT)
        from models.updater import verify_signature
        return verify_signature(path)[0] == "trusted"
    except Exception:
        return False


def write_sums(version: str) -> int:
    installers = find_installers(version)
    if not installers:
        print(f"[ERREUR] Aucun installeur dans {OUTPUT_DIR}")
        print("         Compilez d'abord installer/setup.iss avec Inno Setup.")
        return 1

    expected = f"Carib_v{version}_Setup.exe"
    if installers != [expected]:
        print(f"[ATTENTION] {expected} est introuvable.")
        print(f"            Trouve a la place : {', '.join(installers)}")
        print("            Verifiez que le build correspond bien a la version "
              f"{version}.")

    lines = []
    for name in installers:
        path = os.path.join(OUTPUT_DIR, name)
        digest = sha256(path)
        size = os.path.getsize(path)
        lines.append(f"{digest}  {name}")
        signature = "signe" if is_signed(path) else "NON SIGNE"
        print(f"  {name}")
        print(f"    taille    : {size / (1024 * 1024):.1f} Mo")
        print(f"    sha256    : {digest}")
        print(f"    signature : {signature}")
        if signature == "NON SIGNE":
            print("    ^ SmartScreen affichera « Editeur inconnu » a vos "
                  "utilisateurs.")

    sums_path = os.path.join(OUTPUT_DIR, SUMS_NAME)
    with io.open(sums_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")

    print(f"\n  Ecrit : {sums_path}")
    _print_publish_hint(version, installers[0])
    return 0


def verify_sums() -> int:
    sums_path = os.path.join(OUTPUT_DIR, SUMS_NAME)
    if not os.path.isfile(sums_path):
        print(f"[ERREUR] {sums_path} est introuvable.")
        return 1

    with io.open(sums_path, encoding="utf-8") as fh:
        content = fh.read()

    checked = failed = 0
    for line in content.splitlines():
        match = _SHA256_RE.search(line)
        if not match:
            continue
        expected_digest = match.group(1).lower()
        name = line.replace(match.group(1), "").strip().lstrip("*").strip()
        path = os.path.join(OUTPUT_DIR, name)
        if not os.path.isfile(path):
            print(f"  MANQUANT  {name}")
            failed += 1
            continue
        actual = sha256(path)
        if actual == expected_digest:
            print(f"  OK        {name}")
            checked += 1
        else:
            print(f"  ECHEC     {name}")
            print(f"            attendu {expected_digest}")
            print(f"            obtenu  {actual}")
            failed += 1

    if failed:
        print(f"\n[ERREUR] {failed} fichier(s) ne correspondent pas.")
        print("         Avez-vous signe l'installeur APRES avoir calcule "
              "les empreintes ?")
        return 1
    print(f"\n  {checked} fichier(s) verifie(s).")
    return 0


def _print_publish_hint(version: str, installer: str) -> None:
    print("\n" + "-" * 70)
    print("Publier la release :\n")
    print(f'  gh release create v{version} \\')
    print(f'    "installer/Output/{installer}" \\')
    print(f'    "installer/Output/{SUMS_NAME}" \\')
    print(f'    --title "Carib {version}" \\')
    print('    --notes-file notes.md')
    print("\nLa release ne doit etre ni un brouillon ni une preversion :")
    print("l'updater interroge /releases/latest, qui les exclut.")
    print("-" * 70)


def main(argv) -> int:
    version = read_version()
    print(f"Carib {version}\n")
    if "--verify" in argv:
        return verify_sums()
    return write_sums(version)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
