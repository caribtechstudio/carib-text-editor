"""
controllers/editor_controller.py — Gestion de la saisie, des emojis et de la calculatrice.

Deux principes gouvernent ce contrôleur :

  1. **Tout raisonne sur le curseur.** Le remplacement d'emoji et le mode
     calcul regardent la position d'édition réelle, pas la fin du document.
  2. **Rien de coûteux à chaque frappe.** Aucune opération en O(taille du
     document) n'est autorisée dans `on_text_changed` : le comptage de mots
     et la reconstruction du dictionnaire sont différés.
"""

import flet as ft

from constants import MODE_CALC
from models.calculator import eval_safe
from models.scheduler import scheduler
from models.text_utils import line_bounds_at_cursor, word_before_cursor
from my_emoji import EMOJI_DICT

AUTO_SAVE_DELAY = 3.0        # secondes après la dernière frappe
UNDO_SNAPSHOT_DELAY = 0.5    # pause avant de figer une étape d'annulation

#: Clés d'ordonnancement. Reprogrammer la même clé remplace l'échéance
#: précédente : plus besoin d'annuler un timer à la main.
_UNDO_TASK = "editor.undo_snapshot"
_AUTOSAVE_TASK = "editor.auto_save"


class EditorController:
    """Gère les événements de saisie dans l'éditeur."""

    def __init__(self, state, editor, cur_doc_fn, page, services,
                 autocomplete_ctrl=None):
        self.state = state
        self.editor = editor
        self._cur_doc = cur_doc_fn
        self._page = page
        self._svc = services
        self._rebuild = services.rebuild
        self._update_status = services.update_status
        self._get_cursor = services.get_cursor

        self.autocomplete_ctrl = autocomplete_ctrl

    # ------------------------------------------------------------------
    # Saisie
    # ------------------------------------------------------------------
    def on_text_changed(self, e):
        d = self._cur_doc()
        if not d:
            return

        # La base d'annulation est prise **avant** d'ecrire la frappe : le
        # tout premier caractere d'une salve redevient ainsi annulable.
        if d.undo_base is None:
            d.undo_base = d.content

        d.content = e.control.value or ""
        cursor = self._cursor_from_event(e)

        self._schedule_undo_snapshot(d)

        was_clean = not d.modified
        d.modified = True

        # Transformations locales — elles peuvent réécrire le contenu et
        # déplacer le curseur, donc elles passent avant l'autocomplétion.
        cursor = self._check_emoji_auto(d, cursor)
        cursor = self._detect_calc(d, cursor)

        if self.autocomplete_ctrl:
            self.autocomplete_ctrl.on_text_changed(cursor)

        self._update_status()
        # Seules la couche de texte et la barre d'état bougent ici : inutile
        # de faire comparer au moteur de rendu l'interface entière.
        self._svc.flush_typing()
        self._schedule_auto_save()

        if was_clean:
            # Le passage de « enregistré » à « modifié » change la barre
            # d'onglets (pastille) : on la rafraîchit une seule fois.
            self._rebuild()

    def _cursor_from_event(self, e) -> int:
        """Position du curseur au moment de l'événement.

        Flet expose la sélection sur le contrôle ; on retombe sur le suivi
        d'AppController puis sur la fin du texte si elle est indisponible.
        """
        sel = getattr(e.control, "selection", None)
        if sel is not None and getattr(sel, "start", None) is not None:
            return sel.start
        tracked = self._get_cursor()
        if tracked is not None:
            return tracked
        return len(e.control.value or "")

    def _set_cursor(self, pos: int):
        """Repositionne le curseur après une réécriture programmatique."""
        try:
            self.editor.selection = ft.TextSelection(base_offset=pos, extent_offset=pos)
        except (AttributeError, TypeError):
            pass

    # ------------------------------------------------------------------
    # Historique d'annulation (deltas, avec regroupement par pause de frappe)
    # ------------------------------------------------------------------
    def _schedule_undo_snapshot(self, d):
        """Fige une étape d'annulation après 500 ms sans frappe.

        La base de comparaison est portée par `d` : la tâche différée ne peut
        donc jamais confronter le texte d'un document à celui d'un autre,
        même si l'utilisateur change d'onglet pendant le délai.
        """
        scheduler.schedule(_UNDO_TASK, UNDO_SNAPSHOT_DELAY, d.flush_pending_edit)

    def force_snapshot(self):
        """Clôt immédiatement l'étape en cours (avant un collage, un couper,
        un changement d'onglet…)."""
        scheduler.cancel(_UNDO_TASK)
        d = self._cur_doc()
        if d:
            d.flush_pending_edit()

    def reset_snapshot_tracking(self):
        """Abandonne l'étape en cours sans l'enregistrer.

        Réservé aux réécritures programmatiques qui gèrent elles-mêmes leur
        entrée d'historique (couper/coller, actions IA) : conserver la base
        y ferait enregistrer une seconde fois la même modification.
        """
        scheduler.cancel(_UNDO_TASK)
        d = self._cur_doc()
        if d:
            d.undo_base = None

    # ------------------------------------------------------------------
    # Sauvegarde automatique
    # ------------------------------------------------------------------
    def _schedule_auto_save(self):
        scheduler.cancel(_AUTOSAVE_TASK)
        if not self.state.auto_save:
            return
        if not self._cur_doc():
            return
        scheduler.schedule(_AUTOSAVE_TASK, AUTO_SAVE_DELAY, self._trigger_auto_save)

    def _trigger_auto_save(self):
        self._page.run_thread(self._svc.auto_save)

    # ------------------------------------------------------------------
    # Emojis — remplace le mot situé juste avant le curseur
    # ------------------------------------------------------------------
    def _check_emoji_auto(self, d, cursor: int) -> int:
        """Remplace `:code:` par l'emoji correspondant. Retourne le curseur ajusté."""
        text = d.content
        if not text:
            return cursor

        word = word_before_cursor(text, cursor)
        if not word:
            return cursor

        emoji = EMOJI_DICT.get(word)
        if not emoji:
            return cursor

        start = cursor - len(word)
        d.content = text[:start] + emoji + text[cursor:]
        self.editor.value = d.content
        new_cursor = start + len(emoji)
        self._set_cursor(new_cursor)
        return new_cursor

    # ------------------------------------------------------------------
    # Mode calcul — évalue la ligne courante quand elle se termine par « = »
    # ------------------------------------------------------------------
    def _detect_calc(self, d, cursor: int) -> int:
        if self.state.mode != MODE_CALC:
            return cursor
        text = d.content
        if not text:
            return cursor

        start, end = line_bounds_at_cursor(text, cursor)
        line = text[start:end].rstrip()
        if not line.endswith("="):
            return cursor

        expr = line[:-1].strip()
        if not expr:
            return cursor

        result = eval_safe(expr)
        if not result:
            return cursor

        new_line = f"{line} {result}"
        d.content = text[:start] + new_line + text[end:]
        self.editor.value = d.content
        new_cursor = start + len(new_line)
        self._set_cursor(new_cursor)
        return new_cursor
