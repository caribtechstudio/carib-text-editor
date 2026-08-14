"""
controllers/autocomplete_controller.py -- Suggestion unique, en texte fantôme.

Changement de modèle par rapport à la popup en liste : il n'y a plus qu'**une
seule** proposition, affichée en gris dans le flux du texte. L'utilisateur
n'a plus à quitter sa phrase des yeux, ni à viser avec les flèches.

Deux sources alimentent cette suggestion, dans cet ordre :

  1. **Le dictionnaire local** (trie construit sur le document) — instantané,
     hors ligne, gratuit. Il complète le mot en cours de frappe.
  2. **Le modèle de langage** — il propose la suite de la phrase, mais
     seulement quand aucun mot n'est en cours et après une pause.

La suggestion ne vit que dans la couche d'affichage : elle n'entre jamais
dans le document tant qu'elle n'est pas acceptée.
"""

import flet as ft

from models.ai_completer import AICompleter
from models.scheduler import scheduler
from models.text_utils import word_before_cursor
from models.word_completer import WordCompleter

#: Sources possibles pour la suggestion courante.
SOURCE_WORD = "word"
SOURCE_AI = "ai"

#: Cle d'ordonnancement de la reindexation du dictionnaire.
_TRIE_TASK = "autocomplete.trie"


class AutocompleteController:
    """Produit et applique la suggestion en texte fantôme."""

    #: Nombre minimum de caractères avant de compléter un mot.
    MIN_PREFIX_LEN = 2
    #: Le dictionnaire est reconstruit au repos, jamais pendant la frappe.
    TRIE_UPDATE_DELAY = 2.0
    #: Contexte envoyé au modèle pour la prédiction de phrase.
    AI_CONTEXT_CHARS = 500

    def __init__(self, state, editor, cur_doc_fn, rebuild_fn, page,
                 refresh_fn=None, llm_ready_fn=None, manager=None):
        self.state = state
        self.editor = editor
        self._cur_doc = cur_doc_fn
        self._rebuild = rebuild_fn
        #: Rafraîchit uniquement la couche d'affichage (pas d'arbre complet).
        self._refresh = refresh_fn or rebuild_fn
        self._page = page
        self._llm_ready = llm_ready_fn or (lambda: False)

        self._word_completer = WordCompleter()
        self._ai_completer = AICompleter(manager)
        self._ai_completer.on_prediction = self._on_ai_prediction

        self._cursor = 0

        #: Vrai le temps du traitement d'une frappe. L'appelant
        #: (`EditorController`) enverra lui-même l'état au client juste après ;
        #: le rappel de rafraîchissement peut donc se contenter de préparer la
        #: couche d'affichage, sans déclencher un second envoi pour la même
        #: touche. Lu par `AppController._refresh_ghost`.
        self.typing = False

    # ------------------------------------------------------------------
    # Frappe
    # ------------------------------------------------------------------
    def on_text_changed(self, cursor: int | None = None):
        if not self.state.ac_enabled:
            return
        self.typing = True
        try:
            self._on_text_changed(cursor)
        finally:
            self.typing = False

    def _on_text_changed(self, cursor: int | None):
        d = self._cur_doc()
        if not d or not d.content:
            self.dismiss()
            return

        text = d.content
        self._cursor = cursor if cursor is not None else len(text)
        prefix = word_before_cursor(text, self._cursor)

        if len(prefix) >= self.MIN_PREFIX_LEN:
            # Complétion locale : instantanée, elle prime sur le modèle.
            candidates = self._word_completer.complete(prefix, max_results=1)
            if candidates and candidates[0].startswith(prefix.lower()):
                self._set_ghost(candidates[0][len(prefix):], SOURCE_WORD)
                self._ai_completer.cancel()
                self._schedule_trie_update(text)
                return

        # Aucun mot à compléter : on laisse le modèle proposer une suite.
        self._clear_ghost()
        self._request_ai_prediction(text)
        self._schedule_trie_update(text)

    # ------------------------------------------------------------------
    # Suggestion
    # ------------------------------------------------------------------
    def _set_ghost(self, suggestion: str, source: str):
        suggestion = suggestion or ""
        if (self.state.ac_ghost, self.state.ac_source) == (suggestion, source):
            return
        self.state.ac_ghost = suggestion
        self.state.ac_source = source
        self.state.ac_visible = bool(suggestion)
        self._refresh()

    def _clear_ghost(self):
        if not self.state.ac_ghost:
            self.state.ac_visible = False
            return
        self.state.ac_ghost = ""
        self.state.ac_source = ""
        self.state.ac_visible = False
        self._refresh()

    @property
    def has_suggestion(self) -> bool:
        return bool(self.state.ac_ghost)

    # ------------------------------------------------------------------
    # Prédiction par le modèle
    # ------------------------------------------------------------------
    def _request_ai_prediction(self, text: str):
        if not self._llm_ready():
            return
        upto = text[:self._cursor]
        # Proposer une suite au milieu d'un mot n'a pas de sens.
        if upto and not upto[-1].isspace() and word_before_cursor(text, self._cursor):
            return
        context = upto[-self.AI_CONTEXT_CHARS:]
        if not context.strip():
            return
        self._ai_completer.request_completion(context, self._cursor)

    def _on_ai_prediction(self, prediction: str):
        """Appelé depuis le thread réseau."""
        if not self.state.ac_enabled or not prediction:
            return

        def apply():
            # Le curseur a pu bouger pendant l'appel : on ne colle pas une
            # suggestion périmée dans le texte de l'utilisateur.
            d = self._cur_doc()
            if not d:
                return
            if word_before_cursor(d.content, self._cursor):
                return
            self._set_ghost(prediction, SOURCE_AI)

        try:
            self._page.run_thread(apply)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Acceptation
    # ------------------------------------------------------------------
    def accept(self) -> bool:
        """Tab — insère toute la suggestion."""
        return self._insert(self.state.ac_ghost)

    def accept_word(self) -> bool:
        """Ctrl+→ — insère seulement le premier mot de la suggestion.

        Permet de garder la main : on prend le début utile de la proposition
        sans avaler une phrase entière qu'on n'aurait pas voulue.
        """
        ghost = self.state.ac_ghost
        if not ghost:
            return False

        # On coupe après le premier mot, séparateur inclus.
        idx = 0
        while idx < len(ghost) and ghost[idx].isspace():
            idx += 1
        while idx < len(ghost) and not ghost[idx].isspace():
            idx += 1

        chunk = ghost[:idx] or ghost
        if not self._insert(chunk, keep_rest=ghost[idx:]):
            return False
        return True

    def _insert(self, chunk: str, keep_rest: str = "") -> bool:
        if not chunk:
            return False
        d = self._cur_doc()
        if not d:
            return False

        text = d.content
        cursor = min(self._cursor, len(text))
        new_text = text[:cursor] + chunk + text[cursor:]
        new_cursor = cursor + len(chunk)

        d.apply_change(new_text)
        d.modified = True
        self.editor.value = new_text
        self._cursor = new_cursor

        if keep_rest:
            # Acceptation mot à mot : le reste de la proposition demeure.
            self.state.ac_ghost = keep_rest
            self.state.ac_visible = True
        else:
            self.state.ac_ghost = ""
            self.state.ac_source = ""
            self.state.ac_visible = False
            self._ai_completer.cancel()

        try:
            self.editor.selection = ft.TextSelection(
                base_offset=new_cursor, extent_offset=new_cursor)
        except (AttributeError, TypeError):
            pass

        self.state.cursor = new_cursor
        self._refresh()
        self._page.run_task(self.editor.focus)
        return True

    # ------------------------------------------------------------------
    # Fermeture
    # ------------------------------------------------------------------
    def dismiss(self):
        """Échap — abandonne la suggestion courante."""
        self._ai_completer.cancel()
        self._clear_ghost()

    # ------------------------------------------------------------------
    # Dictionnaire local
    # ------------------------------------------------------------------
    def _schedule_trie_update(self, text: str):
        scheduler.schedule(_TRIE_TASK, self.TRIE_UPDATE_DELAY,
                           lambda: self._word_completer.update_from_text(text))

    def update_trie_now(self, text: str):
        """Réindexe immédiatement. Réservé aux tests et aux appels hors frappe."""
        if text:
            self._word_completer.update_from_text(text)

    #: Délai de réindexation après un changement d'onglet. Court — la
    #: suggestion doit connaître le vocabulaire du nouveau document presque
    #: tout de suite — mais différé, ce qui est l'essentiel.
    TRIE_SWITCH_DELAY = 0.2

    def refresh_dictionary_soon(self, text: str):
        """Réindexe le document **hors du thread d'interface**.

        Le changement d'onglet appelait `update_trie_now`, qui parcourt tout
        le document et reconstruit le trie sur place. Sur un fichier de
        plusieurs centaines de milliers de caractères, cela figeait l'interface
        à chaque bascule — exactement le ralentissement ressenti. L'indexation
        n'a aucune raison d'être synchrone : tant qu'elle n'est pas finie, le
        dictionnaire précédent reste utilisable.
        """
        if not text:
            return
        scheduler.schedule(_TRIE_TASK, self.TRIE_SWITCH_DELAY,
                           lambda: self._word_completer.update_from_text(text))

    def shutdown(self):
        scheduler.cancel(_TRIE_TASK)
        self._ai_completer.cancel()
