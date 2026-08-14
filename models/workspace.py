"""
models/workspace.py — Ouverture d'un dossier comme espace de travail.

Passer de « j'ouvre un fichier » à « je travaille dans mon dossier » change
l'usage de l'éditeur — c'est la différence entre le Bloc-notes et VS Code ou
Obsidian.

Le parcours est **paresseux** : seul le contenu des dossiers réellement
dépliés est lu. Ouvrir un dossier contenant dix mille fichiers ne coûte donc
que la lecture de son premier niveau.
"""

import os
import time

#: Durée de vie du cache de listage. L'arborescence est relue à chaque
#: reconstruction de la barre latérale ; sans cache, une rafale de
#: reconstructions (frappe, changement d'onglet) déclenchait autant d'accès
#: disque — coûteux sur un lecteur réseau ou un dossier synchronisé.
#: 1,5 s est assez court pour qu'un fichier créé à l'extérieur apparaisse au
#: geste suivant, assez long pour absorber la rafale.
_CACHE_TTL = 1.5

#: chemin normalisé → (instant, dossiers, fichiers, tronqué)
_dir_cache: dict[str, tuple[float, list[str], list[str], bool]] = {}

#: Extensions considérées comme du texte éditable (miroir de FileController).
TEXT_EXTENSIONS = frozenset({
    ".txt", ".md", ".markdown", ".log", ".csv", ".tsv", ".json", ".yaml",
    ".yml", ".ini", ".cfg", ".conf", ".xml", ".html", ".css", ".js", ".ts",
    ".py", ".sql", ".sh", ".bat", ".env", ".toml", ".rst", ".tex",
})

#: Dossiers systématiquement masqués : ils polluent l'arborescence et ne
#: contiennent jamais ce que l'utilisateur cherche à éditer.
IGNORED_DIRS = frozenset({
    ".git", ".svn", ".hg", "__pycache__", "node_modules", ".venv", "venv",
    "env", ".idea", ".vscode", "dist", "build", ".pytest_cache", ".mypy_cache",
    "site-packages", ".next", "target", "bin", "obj",
})

#: Garde-fou : un dossier anormalement peuplé est tronqué plutôt que de
#: produire des milliers de widgets.
MAX_ENTRIES_PER_DIR = 300


class Entry:
    """Une ligne de l'arborescence."""

    __slots__ = ("name", "path", "is_dir", "depth")

    def __init__(self, name: str, path: str, is_dir: bool, depth: int):
        self.name = name
        self.path = path
        self.is_dir = is_dir
        self.depth = depth


def is_text_file(name: str) -> bool:
    ext = os.path.splitext(name)[1].lower()
    # Les fichiers sans extension (README, LICENSE, Makefile) sont fréquemment
    # du texte : on les accepte plutôt que de les cacher.
    return ext in TEXT_EXTENSIONS or ext == ""


def invalidate_cache(path: str | None = None):
    """Oublie le listage mémorisé — après une création, un renommage, une
    suppression, ou l'ouverture d'un autre dossier de travail."""
    if path is None:
        _dir_cache.clear()
        return
    _dir_cache.pop(os.path.normcase(path), None)
    # Le parent aussi : c'est lui qui contient l'entrée qui vient de changer.
    _dir_cache.pop(os.path.normcase(os.path.dirname(path)), None)


def list_dir(path: str) -> tuple[list[str], list[str], bool]:
    """Retourne (dossiers, fichiers, tronqué) pour un dossier donné.

    Le résultat est mémorisé brièvement (`_CACHE_TTL`) : reconstruire la barre
    latérale ne doit pas relire le disque à chaque fois.
    """
    key = os.path.normcase(path)
    cached = _dir_cache.get(key)
    now = time.monotonic()
    if cached is not None and now - cached[0] < _CACHE_TTL:
        return cached[1], cached[2], cached[3]

    try:
        with os.scandir(path) as it:
            entries = list(it)
    except OSError:
        _dir_cache[key] = (now, [], [], False)
        return [], [], False

    dirs, files = [], []
    for entry in entries:
        if entry.name.startswith("."):
            continue
        try:
            if entry.is_dir():
                if entry.name not in IGNORED_DIRS:
                    dirs.append(entry.name)
            elif is_text_file(entry.name):
                files.append(entry.name)
        except OSError:
            continue

    dirs.sort(key=str.lower)
    files.sort(key=str.lower)

    truncated = len(dirs) + len(files) > MAX_ENTRIES_PER_DIR
    if truncated:
        keep = MAX_ENTRIES_PER_DIR // 2
        dirs, files = dirs[:keep], files[:keep]

    _dir_cache[key] = (now, dirs, files, truncated)
    return dirs, files, truncated


def build_tree(root: str, expanded: set[str], max_depth: int = 6) -> list[Entry]:
    """Aplatit l'arborescence en une liste de lignes affichables.

    Seuls les dossiers présents dans `expanded` sont parcourus : c'est ce qui
    rend l'ouverture d'un gros dépôt instantanée.
    """
    if not root or not os.path.isdir(root):
        return []

    result: list[Entry] = []

    def walk(path: str, depth: int):
        if depth > max_depth:
            return
        dirs, files, _ = list_dir(path)
        for name in dirs:
            full = os.path.join(path, name)
            result.append(Entry(name, full, True, depth))
            if os.path.normcase(full) in expanded:
                walk(full, depth + 1)
        for name in files:
            result.append(Entry(name, os.path.join(path, name), False, depth))

    walk(root, 0)
    return result


def display_name(root: str) -> str:
    """Nom court du dossier racine, pour l'en-tête de la barre latérale."""
    root = root.rstrip(os.sep)
    return os.path.basename(root) or root
