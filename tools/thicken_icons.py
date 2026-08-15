"""
tools/thicken_icons.py — Épaissit les icônes SVG de Carib.

Pourquoi ce script plutôt qu'un réglage
---------------------------------------
Les icônes de Carib ne sont pas des Material Symbols : ce sont des tracés
**pleins** (« Uicons »), en `viewBox="0 0 24 24"`, sans notion de graisse.
Contrairement à la fonte variable de Google, on ne peut pas leur demander un
`wght` de 400 — il n'y a aucun axe à faire varier.

Ce qu'on peut faire, en revanche, est exactement ce que produit une montée de
graisse : **ajouter de la matière de part et d'autre de chaque contour**. En
SVG, cela s'obtient en peignant les tracés avec un `stroke` de la même couleur
que leur remplissage. Un trait de 1,0 unité devient 1,0 + `WIDTH` unité(s),
les contre-formes se resserrent d'autant, et le dessin gagne en présence sans
qu'aucun trajet ne soit modifié.

Les attributs sont posés sur l'élément `<svg>` racine : `stroke`,
`stroke-width`, `stroke-linejoin` et `stroke-linecap` sont des propriétés
**héritées**, elles descendent donc sur tous les `<path>`, `<circle>` et
`<rect>` du fichier, quel que soit leur nombre.

Réversible et rejouable
-----------------------
Les fichiers d'origine sont copiés une fois pour toutes dans
`ressource/icon/_original/`. Le script repart toujours de cette copie : on
peut donc rejouer avec une autre épaisseur sans jamais cumuler les passes, et
`--restore` remet l'application dans son état initial.

Utilisation
-----------
    python tools/thicken_icons.py                 # épaisseur par défaut
    python tools/thicken_icons.py --width 0.8     # plus gras
    python tools/thicken_icons.py --restore       # retour aux originaux
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sys

#: Épaisseur ajoutée, en unités du `viewBox` (24 × 24).
#:
#: Elle se répartit de chaque côté du contour : 0,6 ajoute 0,3 unité par côté,
#: soit environ +55 % sur le trait de ~1,1 unité de ce jeu d'icônes. C'est le
#: pas qui rapproche le plus ces icônes du rendu d'un Material Symbol
#: `wght 400` sans refermer les contre-formes des plus petites (`at`, `it`,
#: `json-file`).
DEFAULT_WIDTH = 0.6

#: Couleur du contour. Elle doit être celle du remplissage : ces SVG n'ont pas
#: d'attribut `fill`, ils utilisent donc le noir par défaut de SVG. Flet
#: recolore ensuite l'image entière via `Image.color`, ce qui teinte contour et
#: remplissage de la même façon.
STROKE_COLOR = "#000000"

#: Marqueur d'idempotence : un fichier déjà traité le porte.
MARKER = "data-carib-weight"

_ICON_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "ressource", "icon")
_BACKUP_DIR = os.path.join(_ICON_DIR, "_original")

_SVG_TAG = re.compile(r"<svg\b([^>]*)>", re.IGNORECASE)


def _ensure_backup(icon_dir: str, backup_dir: str) -> int:
    """Copie les originaux la première fois. Retourne le nombre de copies."""
    os.makedirs(backup_dir, exist_ok=True)
    copied = 0
    for name in sorted(os.listdir(icon_dir)):
        if not name.lower().endswith(".svg"):
            continue
        target = os.path.join(backup_dir, name)
        if os.path.exists(target):
            continue
        shutil.copy2(os.path.join(icon_dir, name), target)
        copied += 1
    return copied


def thicken_svg(source: str, width: float) -> str:
    """Retourne `source` avec un contour de `width` unité(s) sur ses tracés."""
    match = _SVG_TAG.search(source)
    if match is None:
        return source

    attrs = match.group(1)
    # Repartir propre : on retire toute passe précédente avant d'en poser une.
    attrs = re.sub(r'\s+(?:stroke|stroke-width|stroke-linejoin|stroke-linecap|'
                   rf'{MARKER})="[^"]*"', "", attrs)

    added = (f' fill="{STROKE_COLOR}" stroke="{STROKE_COLOR}"'
             f' stroke-width="{width:g}"'
             ' stroke-linejoin="round" stroke-linecap="round"'
             f' {MARKER}="{width:g}"')

    return source[:match.start()] + f"<svg{attrs.rstrip()}{added}>" + source[match.end():]


def apply(width: float, icon_dir: str = _ICON_DIR,
          backup_dir: str = _BACKUP_DIR) -> tuple[int, int]:
    """Épaissit toutes les icônes. Retourne (traitées, sauvegardées)."""
    if not os.path.isdir(icon_dir):
        raise SystemExit(f"Dossier d'icônes introuvable : {icon_dir}")

    saved = _ensure_backup(icon_dir, backup_dir)

    done = 0
    for name in sorted(os.listdir(backup_dir)):
        if not name.lower().endswith(".svg"):
            continue
        with open(os.path.join(backup_dir, name), "r", encoding="utf-8") as fh:
            original = fh.read()
        result = thicken_svg(original, width)
        with open(os.path.join(icon_dir, name), "w", encoding="utf-8",
                  newline="\n") as fh:
            fh.write(result)
        done += 1
    return done, saved


def restore(icon_dir: str = _ICON_DIR, backup_dir: str = _BACKUP_DIR) -> int:
    """Remet les icônes d'origine. Retourne le nombre de fichiers restaurés."""
    if not os.path.isdir(backup_dir):
        raise SystemExit("Aucune sauvegarde : rien à restaurer.")
    count = 0
    for name in sorted(os.listdir(backup_dir)):
        if not name.lower().endswith(".svg"):
            continue
        shutil.copy2(os.path.join(backup_dir, name), os.path.join(icon_dir, name))
        count += 1
    return count


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--width", type=float, default=DEFAULT_WIDTH,
                        help=f"épaisseur ajoutée en unités de viewBox "
                             f"(défaut : {DEFAULT_WIDTH})")
    parser.add_argument("--restore", action="store_true",
                        help="remettre les icônes d'origine")
    args = parser.parse_args(argv)

    if args.restore:
        print(f"{restore()} icône(s) restaurée(s).")
        return 0

    if not 0 < args.width <= 3:
        parser.error("--width doit être compris entre 0 et 3.")

    done, saved = apply(args.width)
    if saved:
        print(f"{saved} original(aux) sauvegardé(s) dans {_BACKUP_DIR}")
    print(f"{done} icône(s) épaissie(s) de {args.width:g} unité(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
