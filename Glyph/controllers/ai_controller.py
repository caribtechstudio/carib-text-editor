"""
controllers/ai_controller.py -- Orchestration IA multi-mode.

Gere les 3 fonctionnalites IA :
  1. Correction orthographique/grammaticale
  2. Traduction francais <-> anglais
  3. Reformulation (rephrase, naturel, pro, resume, mots-cles)
"""

import threading

from theme import T
from ai_checker import OllamaManager, AIProcessor, DEFAULT_MODEL_ID, MODELS_BY_ID
from views.dialogs.setup_dialog import show_setup_dialog


class AIController:
    """Gere le lancement et l'affichage des resultats IA."""

    def __init__(self, page, state, editor, c,
                 tab_ctrl, show_snack, rebuild_fn, clipboard=None):
        self._page = page
        self.state = state
        self.editor = editor
        self._c = c
        self._tab = tab_ctrl
        self._snack = show_snack
        self._rebuild = rebuild_fn
        self._clipboard = clipboard

    # ------------------------------------------------------------------
    # Verification et preparation
    # ------------------------------------------------------------------
    def _ensure_ready(self) -> bool:
        """Verifie qu'Ollama est pret et qu'un modele est selectionne.
        Retourne True si tout est pret, False sinon."""
        if not OllamaManager.is_ollama_installed():
            show_setup_dialog(self._page, self._c, self.state)
            return False
        if not OllamaManager.is_server_running():
            self._snack("Demarrage d'Ollama...")
            OllamaManager.start_server()
            return False
        model = self._get_active_model()
        if not model:
            show_setup_dialog(self._page, self._c, self.state)
            return False
        if not OllamaManager.is_model_available(model):
            show_setup_dialog(self._page, self._c, self.state)
            return False
        return True

    def _get_active_model(self) -> str:
        """Retourne l'ID du modele actif, ou vide si aucun."""
        if self.state.ai_selected_model:
            return self.state.ai_selected_model
        # Fallback : chercher le premier modele installe du catalogue
        installed = OllamaManager.get_installed_catalog_models()
        if installed:
            self.state.ai_selected_model = installed[0]["id"]
            return self.state.ai_selected_model
        return ""

    def _get_text(self) -> str | None:
        """Recupere le texte a traiter (selection ou tout le document)."""
        self._tab.save_content()
        d = self._tab.cur_doc()
        if not d or not d.content.strip():
            self._snack("Rien a analyser.")
            return None
        return d.content.strip()

    # ------------------------------------------------------------------
    # Lancement generique
    # ------------------------------------------------------------------
    def _run_ai(self, mode: str, retry_count: int = 0):
        """Lance le traitement IA pour un mode donne."""
        text = self._get_text()
        if text is None:
            return

        if not OllamaManager.is_ollama_installed():
            show_setup_dialog(self._page, self._c, self.state)
            return

        if not OllamaManager.is_server_running():
            self._snack("Demarrage d'Ollama...")
            OllamaManager.start_server()
            if retry_count < 3:
                import time
                def retry():
                    time.sleep(2.5)
                    self._page.run_thread(lambda: self._run_ai(mode, retry_count + 1))
                threading.Thread(target=retry, daemon=True).start()
            else:
                self._snack("Impossible de demarrer Ollama.", self._c(T.L_ERROR, T.D_ERROR))
            return

        model = self._get_active_model()
        if not model:
            show_setup_dialog(self._page, self._c, self.state)
            return

        if not OllamaManager.is_model_available(model):
            show_setup_dialog(self._page, self._c, self.state)
            return

        if self.state.ai_processor and self.state.ai_processor.is_running:
            self._snack("Traitement IA deja en cours.")
            return

        # Preparer l'etat
        self.state.clear_ai_results()
        self.state.ai_mode = mode
        self.state.show_ai = True
        self.state.ai_loading = True
        self._rebuild()

        page = self._page
        state = self.state
        rebuild = self._rebuild

        def on_result(data):
            state.dispatch_ai_result(mode, data)
            state.ai_loading = False
            page.run_thread(rebuild)

        def on_error(msg):
            state.ai_error = msg
            state.ai_loading = False
            page.run_thread(rebuild)

        state.ai_processor = AIProcessor(on_result=on_result, on_error=on_error)
        state.ai_processor.process(text, mode, model)

    # ------------------------------------------------------------------
    # Points d'entree publics (un par bouton/raccourci)
    # ------------------------------------------------------------------
    def run_correction(self, e=None):
        """Lance la correction orthographique et grammaticale."""
        self._run_ai("correction")

    def run_translate_fr_en(self, e=None):
        """Lance la traduction francais -> anglais."""
        self._run_ai("translate_fr_en")

    def run_translate_en_fr(self, e=None):
        """Lance la traduction anglais -> francais."""
        self._run_ai("translate_en_fr")

    def run_reformulate(self, e=None):
        """Lance la reformulation avec d'autres mots."""
        self._run_ai("reformulate")

    def run_natural(self, e=None):
        """Lance la reformulation ton naturel."""
        self._run_ai("natural")

    def run_professional(self, e=None):
        """Lance la reformulation ton professionnel."""
        self._run_ai("professional")

    def run_summarize(self, e=None):
        """Lance le resume du texte."""
        self._run_ai("summarize")

    def run_keywords(self, e=None):
        """Lance l'extraction de mots-cles."""
        self._run_ai("keywords")

    # ------------------------------------------------------------------
    # Actions de resultat
    # ------------------------------------------------------------------
    def apply_correction(self, original, replacement):
        """Applique une correction dans le document."""
        d = self._tab.cur_doc()
        if not d:
            return
        if original in d.content:
            d.push_undo(d.content)
            d.content = d.content.replace(original, replacement, 1)
            self.editor.value = d.content
            d.modified = True
            self._snack(f'"{original}" -> "{replacement}"',
                        self._c(T.L_SUCCESS, T.D_SUCCESS))
        else:
            self._snack(f'"{original}" introuvable.',
                        self._c(T.L_WARNING, T.D_WARNING))

    def replace_with_result(self, new_text):
        """Remplace tout le contenu du document par le resultat IA."""
        d = self._tab.cur_doc()
        if not d or not new_text:
            return
        d.push_undo(d.content)
        d.content = new_text
        self.editor.value = d.content
        d.modified = True
        self._snack("Texte remplace.", self._c(T.L_SUCCESS, T.D_SUCCESS))

    async def copy_result(self, e, text):
        """Copie un texte dans le presse-papier."""
        if not text or not self._clipboard:
            return
        await self._clipboard.set(text)
        self._snack("Copie dans le presse-papier.", self._c(T.L_SUCCESS, T.D_SUCCESS))

    def close_ai(self):
        """Ferme le panneau IA."""
        self.state.show_ai = False
        self._rebuild()

    # ------------------------------------------------------------------
    # Gestion du modele
    # ------------------------------------------------------------------
    def select_model(self, model_id: str):
        """Change le modele IA actif."""
        self.state.ai_selected_model = model_id
        info = MODELS_BY_ID.get(model_id)
        name = info["name"] if info else model_id
        self._snack(f"Modele IA : {name}")

    def show_model_manager(self, e=None):
        """Ouvre le gestionnaire de modeles."""
        show_setup_dialog(self._page, self._c, self.state)
