"""
models/document.py — Représentation d'un document ouvert dans l'éditeur.

L'historique d'annulation stocke des **deltas** et non des copies complètes
du document. Taper 50 caractères coûtait auparavant 50 copies intégrales du
texte (≈ 25 Mo pour un document de 500 Ko) ; il coûte désormais quelques
centaines d'octets.
"""

from models.file_manager import DEFAULT_ENCODING, DEFAULT_NEWLINE

MAX_UNDO = 200          # bien plus généreux qu'avant, pour un coût mémoire moindre


class _Edit:
    """Une modification contiguë : à `pos`, `removed` a été remplacé par `inserted`."""

    __slots__ = ("pos", "removed", "inserted")

    def __init__(self, pos: int, removed: str, inserted: str):
        self.pos = pos
        self.removed = removed
        self.inserted = inserted

    @property
    def is_empty(self) -> bool:
        return not self.removed and not self.inserted

    def apply(self, text: str) -> str:
        """Rejoue la modification (redo)."""
        return text[:self.pos] + self.inserted + text[self.pos + len(self.removed):]

    def revert(self, text: str) -> str:
        """Annule la modification (undo)."""
        return text[:self.pos] + self.removed + text[self.pos + len(self.inserted):]


def _diff(old: str, new: str) -> _Edit:
    """Réduit deux versions à la plus petite modification contiguë équivalente.

    Exact pour toute édition en un seul endroit (frappe, collage, suppression),
    ce qui couvre la quasi-totalité des cas réels. Pour des changements
    dispersés, le delta dégénère en un remplacement large — soit exactement
    ce qu'un instantané complet aurait coûté, jamais davantage.
    """
    if old == new:
        return _Edit(0, "", "")

    limit = min(len(old), len(new))
    start = 0
    while start < limit and old[start] == new[start]:
        start += 1

    # Suffixe commun, sans empiéter sur le préfixe déjà consommé.
    max_suffix = limit - start
    suffix = 0
    while (suffix < max_suffix
           and old[len(old) - 1 - suffix] == new[len(new) - 1 - suffix]):
        suffix += 1

    return _Edit(start, old[start:len(old) - suffix], new[start:len(new) - suffix])


class Document:
    """Un document : contenu, chemin disque, encodage et historique d'édition."""

    def __init__(self, title="Sans titre", content="", path=None, modified=False,
                 encoding=DEFAULT_ENCODING, newline=DEFAULT_NEWLINE,
                 mtime=0.0, size=0, encoding_confident=True):
        self.title = title
        self.content = content
        self.path = path
        self.modified = modified

        # --- Métadonnées de fichier, pour réécrire à l'identique ---
        self.encoding = encoding
        self.newline = newline
        self.encoding_confident = encoding_confident
        #: horodatage et taille au dernier accès disque — sert à repérer
        #: une modification externe avant d'écraser le fichier.
        self.mtime = mtime
        self.size = size

        self.undo_stack: list[_Edit] = []
        self.redo_stack: list[_Edit] = []

        #: Contenu au debut du groupe d'annulation en cours, ou None si
        #: aucune frappe n'est en attente de regroupement.
        #:
        #: Cette base appartient au **document** et non au controleur de
        #: saisie : un unique champ partage se retrouvait a pointer sur le
        #: texte d'un autre onglet des qu'un chemin de code oubliait de le
        #: reinitialiser (creation d'onglet, ouverture de fichier). Ctrl+Z
        #: injectait alors le contenu de l'onglet precedent a la place du
        #: texte que l'utilisateur venait de taper.
        self.undo_base: str | None = None

    # ------------------------------------------------------------------
    # Historique
    # ------------------------------------------------------------------
    def record_edit(self, old_text: str, new_text: str) -> None:
        """Enregistre le passage de `old_text` à `new_text` dans l'historique."""
        edit = _diff(old_text, new_text)
        if edit.is_empty:
            return
        self.undo_stack.append(edit)
        if len(self.undo_stack) > MAX_UNDO:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def flush_pending_edit(self) -> None:
        """Fige la salve de frappe en cours dans l'historique, s'il y en a une.

        Idempotent : appeler deux fois de suite n'enregistre rien la seconde
        fois.
        """
        base = self.undo_base
        self.undo_base = None
        if base is not None and base != self.content:
            self.record_edit(base, self.content)

    def apply_change(self, new_text: str) -> None:
        """Modifie le contenu en enregistrant l'opération dans l'historique."""
        # La salve de frappe en attente est figée d'abord. Sans cela elle
        # serait soit fondue dans la modification programmatique, soit
        # enregistrée une seconde fois par l'instantané différé — dans les
        # deux cas Ctrl+Z ne rendait plus le texte attendu.
        self.flush_pending_edit()
        if new_text == self.content:
            return
        self.record_edit(self.content, new_text)
        self.content = new_text

    def undo(self) -> str | None:
        """Annule la dernière modification. Retourne le nouveau contenu ou None."""
        if not self.undo_stack:
            return None
        edit = self.undo_stack.pop()
        self.redo_stack.append(edit)
        self.content = edit.revert(self.content)
        return self.content

    def redo(self) -> str | None:
        """Rétablit la dernière annulation. Retourne le nouveau contenu ou None."""
        if not self.redo_stack:
            return None
        edit = self.redo_stack.pop()
        self.undo_stack.append(edit)
        self.content = edit.apply(self.content)
        return self.content

    @property
    def can_undo(self) -> bool:
        return bool(self.undo_stack)

    @property
    def can_redo(self) -> bool:
        return bool(self.redo_stack)

    # ------------------------------------------------------------------
    # Métadonnées disque
    # ------------------------------------------------------------------
    def mark_saved(self, mtime: float, size: int) -> None:
        """À appeler après une écriture réussie sur disque."""
        self.modified = False
        self.mtime = mtime
        self.size = size
