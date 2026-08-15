"""
controllers/ai_ux_controller.py — Interaction IA moderne.

Trois mécaniques, qui remplacent le parcours « je clique sur un bouton, un
panneau s'ouvre à droite, je lis une liste » :

  * **Ctrl+K** — une barre de prompt au centre de l'écran. L'utilisateur
    décrit son intention en français ; les actions prédéfinies restent
    disponibles en un clic.
  * **Revue en diff inline** — le résultat s'affiche à sa place dans le
    document, suppressions barrées en rouge et ajouts en vert. Tab accepte,
    Échap refuse. C'est ce que font Cursor et Notion, et c'est ce qui fait
    la différence entre « il y a de l'IA » et « on écrit avec ».
  * **Palette de commandes** (Ctrl+Maj+P) — toutes les actions de Carib
    dans une liste filtrable.
"""

import flet as ft

from views.diff_view import compute_diff


class AIUXController:
    """Pilote la barre Ctrl+K, la revue de diff et la palette de commandes."""

    #: Modes dont le résultat est un texte de remplacement, donc « diffable ».
    REPLACEMENT_MODES = frozenset({
        "reformulate", "natural", "professional", "summarize",
        "translate_fr_en", "translate_en_fr", "free",
    })

    def __init__(self, page, state, editor, tab_ctrl, ai_ctrl,
                 rebuild_fn, show_snack, get_selection_fn, get_cursor_fn):
        self._page = page
        self.state = state
        self._editor = editor
        self._tab = tab_ctrl
        self._ai = ai_ctrl
        self._rebuild = rebuild_fn
        self._snack = show_snack
        self._get_selection = get_selection_fn
        self._get_cursor = get_cursor_fn
        #: Liste de `views.command_palette.Command`, fournie par AppController.
        self.commands: list = []

    # ------------------------------------------------------------------
    # Barre Ctrl+K
    # ------------------------------------------------------------------
    def toggle_command_bar(self):
        if self.state.kbar_visible:
            self.close_command_bar()
        else:
            self.open_command_bar()

    def open_command_bar(self):
        self.state.kbar_visible = True
        self.state.kbar_query = ""
        self.state.palette_visible = False
        self._rebuild()

    def close_command_bar(self):
        if not self.state.kbar_visible:
            return
        self.state.kbar_visible = False
        self.state.kbar_query = ""
        self._rebuild()
        self._page.run_task(self._editor.focus)

    def on_kbar_change(self, e):
        self.state.kbar_query = e.control.value or ""

    def submit_command_bar(self):
        """Envoie la consigne libre saisie par l'utilisateur."""
        instruction = (self.state.kbar_query or "").strip()
        if not instruction:
            return
        self.state.kbar_visible = False
        self._rebuild()
        self._ai.run_free_prompt(instruction, on_done=self._offer_diff)

    def run_mode_from_bar(self, mode: str):
        """Lance une action prédéfinie depuis les puces de la barre."""
        self.state.kbar_visible = False
        self._rebuild()
        runner = getattr(self._ai, f"run_{mode}", None)
        if runner:
            runner()

    def scope_label(self) -> str:
        """Décrit sur quoi l'action va porter — l'utilisateur doit le savoir."""
        sel = self._get_selection()
        if sel and sel[1] > sel[0]:
            return f"Sur la sélection ({sel[1] - sel[0]} caractères)"
        d = self._tab.cur_doc()
        size = len(d.content) if d else 0
        return f"Sur tout le document ({size} caractères)"

    # ------------------------------------------------------------------
    # Revue en diff inline
    # ------------------------------------------------------------------
    def _offer_diff(self, proposed: str):
        """Appelé quand une transformation libre a produit un résultat."""
        if not proposed:
            return
        start, end = self.state.ai_source_range
        self.start_diff(self.state.ai_source_text, proposed, start, end)

    def start_diff(self, original: str, proposed: str, start: int, end: int):
        """Ouvre la revue de modification."""
        if not proposed or proposed.strip() == (original or "").strip():
            self._snack("Aucune modification proposée.")
            return
        self.state.diff_active = True
        self.state.diff_original = original
        self.state.diff_proposed = proposed
        self.state.diff_range = (start, end)
        # Le document passe en lecture seule pendant la revue : la couche de
        # diff serait désynchronisée si l'utilisateur tapait par-dessus.
        self._editor.read_only = True
        self._rebuild()

    def review_from_ai_panel(self):
        """Bascule le résultat affiché dans le panneau vers une revue inline."""
        text = (self.state.ai_reformulation or self.state.ai_translation
                or self.state.ai_summary)
        if not text:
            self._snack("Aucun résultat à comparer.")
            return
        start, end = self.state.ai_source_range
        self.start_diff(self.state.ai_source_text, text, start, end)

    def accept_diff(self):
        """Applique la proposition dans le document, en une étape annulable."""
        if not self.state.diff_active:
            return
        d = self._tab.cur_doc()
        if not d:
            self.reject_diff()
            return

        start, end = self.state.diff_range
        end = min(end, len(d.content))
        start = max(0, min(start, end))
        proposed = self.state.diff_proposed

        new_text = d.content[:start] + proposed + d.content[end:]
        d.apply_change(new_text)
        d.modified = True
        self._editor.value = d.content

        cursor = start + len(proposed)
        try:
            self._editor.selection = ft.TextSelection(
                base_offset=cursor, extent_offset=cursor)
        except (AttributeError, TypeError):
            pass

        self._clear_diff()
        self._snack("Modification appliquée — Ctrl+Z pour revenir en arrière.")

    def reject_diff(self):
        if not self.state.diff_active:
            return
        self._clear_diff()
        self._snack("Proposition écartée.")

    def _clear_diff(self):
        from core.constants import MODE_READ
        self.state.diff_active = False
        self.state.diff_original = ""
        self.state.diff_proposed = ""
        self.state.diff_range = (0, 0)
        self._editor.read_only = (self.state.mode == MODE_READ)
        self._rebuild()
        self._page.run_task(self._editor.focus)

    def diff_segments(self):
        return compute_diff(self.state.diff_original, self.state.diff_proposed)

    # ------------------------------------------------------------------
    # Palette de commandes
    # ------------------------------------------------------------------
    def toggle_palette(self):
        if self.state.palette_visible:
            self.close_palette()
        else:
            self.open_palette()

    def open_palette(self):
        self.state.palette_visible = True
        self.state.palette_query = ""
        self.state.palette_selected = 0
        self.state.kbar_visible = False
        self._rebuild()

    def close_palette(self):
        if not self.state.palette_visible:
            return
        self.state.palette_visible = False
        self.state.palette_query = ""
        self._rebuild()
        self._page.run_task(self._editor.focus)

    def on_palette_change(self, e):
        self.state.palette_query = e.control.value or ""
        self.state.palette_selected = 0
        self._rebuild()

    def navigate_palette(self, direction: int):
        from views.command_palette import MAX_VISIBLE, fuzzy_filter
        total = min(len(fuzzy_filter(self.commands, self.state.palette_query)),
                    MAX_VISIBLE)
        if total == 0:
            return
        self.state.palette_selected = (self.state.palette_selected + direction) % total
        self._rebuild()

    def run_palette_selection(self):
        from views.command_palette import MAX_VISIBLE, fuzzy_filter
        results = fuzzy_filter(self.commands, self.state.palette_query)[:MAX_VISIBLE]
        if not results:
            self.close_palette()
            return
        idx = max(0, min(self.state.palette_selected, len(results) - 1))
        self.run_command(results[idx])

    def run_command(self, command):
        self.state.palette_visible = False
        self.state.palette_query = ""
        self._rebuild()
        try:
            command.action()
        except Exception as exc:                        # une commande ne doit jamais tuer l'app
            self._snack(f"La commande a échoué : {exc}")

    # ------------------------------------------------------------------
    # Échap global
    # ------------------------------------------------------------------
    def handle_escape(self) -> bool:
        """Ferme la surcouche la plus haute. True si quelque chose a été fermé."""
        if self.state.diff_active:
            self.reject_diff()
            return True
        if self.state.palette_visible:
            self.close_palette()
            return True
        if self.state.kbar_visible:
            self.close_command_bar()
            return True
        return False
