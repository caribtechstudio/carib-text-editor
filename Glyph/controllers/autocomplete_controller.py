"""
controllers/autocomplete_controller.py -- Orchestration de l'autocompletion.

Combine la completion locale (mots) et la prediction IA (phrases)
pour proposer des suggestions fluides a l'utilisateur.
"""

import re
import threading

from models.word_completer import WordCompleter
from models.ai_completer import AICompleter
from ai_checker import OllamaManager


class AutocompleteController:
    """Orchestre les suggestions de mots et predictions IA."""

    # Nombre minimum de caracteres pour declencher la completion
    MIN_PREFIX_LEN = 2
    # Delai pour mettre a jour le trie (pas a chaque frappe)
    TRIE_UPDATE_DELAY = 2.0

    def __init__(self, state, editor, cur_doc_fn, rebuild_fn, page,
                 refresh_popup_fn=None):
        self.state = state
        self.editor = editor
        self._cur_doc = cur_doc_fn
        self._rebuild = rebuild_fn
        self._refresh_popup = refresh_popup_fn
        self._page = page

        # Composants
        self._word_completer = WordCompleter()
        self._ai_completer = AICompleter()
        self._ai_completer.on_prediction = self._on_ai_prediction

        # Timer pour mise a jour du trie
        self._trie_timer: threading.Timer | None = None

    def on_text_changed(self):
        """Appele apres chaque changement de texte dans l'editeur."""
        if not self.state.ac_enabled:
            return

        d = self._cur_doc()
        if not d or not d.content:
            self.dismiss()
            return

        # Extraire le mot en cours de saisie (avant le curseur)
        text = d.content
        prefix = self._extract_current_word(text)

        if len(prefix) < self.MIN_PREFIX_LEN:
            # Masquer les suggestions locales mais garder l'IA possible
            self.state.ac_suggestions = []
            self.state.ac_selected = 0
            self.state.ac_prefix = ""
            if not self.state.ac_ai_suggestion:
                self.state.ac_visible = False
            if self._refresh_popup:
                self._refresh_popup()
            # Lancer la prediction IA apres une pause
            self._request_ai_prediction(text)
            return

        self.state.ac_prefix = prefix

        # Completion locale instantanee
        suggestions = self._word_completer.complete(prefix)
        self.state.ac_suggestions = suggestions

        # Prediction IA en arriere-plan
        self._request_ai_prediction(text)

        # Afficher la popup si on a des resultats
        if suggestions or self.state.ac_ai_suggestion:
            self.state.ac_visible = True
            self.state.ac_selected = 0
        else:
            self.state.ac_visible = False

        # Rafraichir juste la popup (leger, pas de rebuild complet)
        if self._refresh_popup:
            self._refresh_popup()

        # Planifier la mise a jour du trie
        self._schedule_trie_update(text)

    def _request_ai_prediction(self, text: str):
        """Lance la prediction IA si Ollama est disponible."""
        model_id = self.state.ai_selected_model
        if not model_id:
            return
        if not OllamaManager.is_server_running():
            return
        self._ai_completer.request_completion(text, model_id)

    def _on_ai_prediction(self, prediction: str):
        """Callback appele quand l'IA retourne une prediction."""
        if not self.state.ac_enabled:
            return
        self.state.ac_ai_suggestion = prediction
        if prediction and (self.state.ac_suggestions or self.state.ac_prefix):
            self.state.ac_visible = True
        # Rafraichir la popup depuis le thread principal
        try:
            if self._refresh_popup:
                self._page.run_thread(self._do_refresh_popup)
        except Exception:
            pass

    def _do_refresh_popup(self):
        """Callback thread-safe pour rafraichir la popup."""
        if self._refresh_popup:
            self._refresh_popup()
        self._page.update()

    def navigate(self, direction: int):
        """Deplace la selection dans la popup (direction: +1 ou -1)."""
        if not self.state.ac_visible:
            return
        total = len(self.state.ac_suggestions)
        if self.state.ac_ai_suggestion:
            total += 1
        if total == 0:
            return
        self.state.ac_selected = (self.state.ac_selected + direction) % total

    def accept(self) -> bool:
        """Accepte la suggestion selectionnee. Retourne True si une action a ete faite."""
        if not self.state.ac_visible:
            return False

        d = self._cur_doc()
        if not d:
            return False

        idx = self.state.ac_selected
        text = d.content

        if idx < len(self.state.ac_suggestions):
            # Accepter un mot
            word = self.state.ac_suggestions[idx]
            new_text = self._replace_current_word(text, word)
        elif self.state.ac_ai_suggestion:
            # Accepter la prediction IA
            suggestion = self.state.ac_ai_suggestion
            # Ajouter apres le texte courant (avec espace si necessaire)
            if text and not text.endswith((" ", "\n")):
                # Completer le mot en cours puis ajouter la prediction
                prefix = self._extract_current_word(text)
                if prefix:
                    # Trouver si la prediction commence par la fin du prefix
                    new_text = text + " " + suggestion
                else:
                    new_text = text + suggestion
            else:
                new_text = text + suggestion
        else:
            return False

        # Appliquer
        d.content = new_text
        d.modified = True
        self.editor.value = new_text
        self._dismiss_silent()
        self._ai_completer.clear_cache()
        self._rebuild()
        return True

    def _dismiss_silent(self):
        """Reset l'etat sans declencher de rebuild."""
        self.state.ac_visible = False
        self.state.ac_suggestions = []
        self.state.ac_ai_suggestion = ""
        self.state.ac_selected = 0
        self.state.ac_prefix = ""
        self._ai_completer.cancel()

    def dismiss(self):
        """Ferme la popup d'autocompletion et rafraichit l'UI."""
        was_visible = self.state.ac_visible
        self._dismiss_silent()
        if was_visible and self._refresh_popup:
            self._refresh_popup()

    def _schedule_trie_update(self, text: str):
        """Met a jour le trie avec debounce."""
        if self._trie_timer:
            self._trie_timer.cancel()
        self._trie_timer = threading.Timer(
            self.TRIE_UPDATE_DELAY,
            self._word_completer.update_from_text, args=(text,),
        )
        self._trie_timer.daemon = True
        self._trie_timer.start()

    def update_trie_now(self, text: str):
        """Force la mise a jour du trie (ex: ouverture de fichier)."""
        if text:
            self._word_completer.update_from_text(text)

    @staticmethod
    def _extract_current_word(text: str) -> str:
        """Extrait le mot en cours de saisie (dernier mot incomplet)."""
        if not text:
            return ""
        # Si le texte finit par un espace ou newline, pas de mot en cours
        if text[-1] in (" ", "\n", "\t"):
            return ""
        # Trouver le dernier mot
        match = re.search(
            r"[a-zA-ZàâäéèêëïîôùûüçÀÂÄÉÈÊËÏÎÔÙÛÜÇ'']+$", text,
        )
        return match.group(0) if match else ""

    @staticmethod
    def _replace_current_word(text: str, replacement: str) -> str:
        """Remplace le dernier mot du texte par le remplacement."""
        match = re.search(
            r"[a-zA-ZàâäéèêëïîôùûüçÀÂÄÉÈÊËÏÎÔÙÛÜÇ'']+$", text,
        )
        if match:
            return text[:match.start()] + replacement
        return text + replacement
