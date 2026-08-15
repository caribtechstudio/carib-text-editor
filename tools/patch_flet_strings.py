"""
tools/patch_flet_strings.py — Francise les textes du client Flet.

Le client de bureau de Flet affiche « Working... » pendant que la partie
Python demarre. Ce texte est compile dans `data/app.so` (instantane Dart
AOT) : aucune option Python ne permet de le changer.

On le remplace donc directement dans l'octet-a-octet du build, sous deux
contraintes qui rendent l'operation sure :

  * **Longueur identique.** Dans un instantane Dart, la longueur d'une
    chaine est stockee a part, juste avant les octets, sous forme de Smi
    (l'entier decale d'un bit : 10 caracteres -> 0x14). Remplacer par un
    texte de meme longueur laisse cet en-tete valide ; une longueur
    differente corromprait l'instantane.
  * **Motif ancre sur l'en-tete.** On ne cherche pas « Working... » seul,
    mais l'en-tete de longueur suivi du texte. Cela evite de toucher une
    occurrence sans rapport ailleurs dans le binaire.

Le script est idempotent : relance sans effet si le texte est deja
remplace. Il s'applique au dossier `dist/`, jamais a site-packages — une
reinstallation de Flet ne doit rien casser, et les autres projets Python
de la machine ne sont pas concernes.

Usage :  python tools/patch_flet_strings.py [dossier_dist]
"""

import os
import sys

#: (texte d'origine, remplacement). Les deux doivent faire la meme
#: longueur en octets et rester en Latin-1 (Dart OneByteString).
REPLACEMENTS = [
    (b"Working...", b"Chargement"),
]

_REL_PATH = os.path.join("_internal", "flet_desktop", "app", "flet",
                         "data", "app.so")


def _smi_header(length: int) -> bytes:
    """En-tete de longueur d'une chaine Dart : l'entier decale d'un bit."""
    return (length << 1).to_bytes(8, "little")


def patch_file(path: str) -> int:
    """Applique les remplacements. Retourne le nombre de textes changes."""
    with open(path, "rb") as fh:
        data = fh.read()

    changed = 0
    for old, new in REPLACEMENTS:
        if len(old) != len(new):
            raise ValueError(
                f"« {old.decode()} » et « {new.decode()} » n'ont pas la meme "
                f"longueur ({len(old)} vs {len(new)}) : l'instantane Dart "
                f"serait corrompu."
            )

        header = _smi_header(len(old))
        needle = header + old
        count = data.count(needle)

        if count == 0:
            if data.count(header + new):
                print(f"  = « {new.decode()} » deja en place.")
            else:
                print(f"  ! « {old.decode()} » introuvable — le format de "
                      f"Flet a peut-etre change. Ignore.")
            continue
        if count > 1:
            print(f"  ! « {old.decode()} » trouve {count} fois : trop "
                  f"ambigu pour patcher sans risque. Ignore.")
            continue

        data = data.replace(needle, header + new)
        changed += 1
        print(f"  + « {old.decode()} » -> « {new.decode()} »")

    if changed:
        # Ecriture atomique : un build interrompu ne doit pas laisser un
        # app.so tronque, qui rendrait l'application impossible a lancer.
        tmp = path + ".tmp"
        with open(tmp, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)

    return changed


def main(argv: list) -> int:
    dist = argv[1] if len(argv) > 1 else os.path.join("dist", "Carib")
    target = os.path.join(dist, _REL_PATH)

    if not os.path.isfile(target):
        print(f"[patch_flet_strings] Introuvable : {target}")
        return 1

    size_before = os.path.getsize(target)
    print(f"[patch_flet_strings] {target}")
    changed = patch_file(target)

    if os.path.getsize(target) != size_before:
        print("[patch_flet_strings] ERREUR : la taille du fichier a change.")
        return 1

    print(f"[patch_flet_strings] {changed} texte(s) remplace(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
