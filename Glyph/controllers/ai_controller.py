"""
controllers/ai_controller.py -- Orchestration des actions IA.

Change majeur par rapport a la version precedente :

  * Le fournisseur n'est plus code en dur (Ollama). Tout passe par
    `LLMManager`, donc ChatGPT, Claude, Gemini et Ollama sont interchangeables.
  * Les reponses arrivent **en streaming** : le premier mot s'affiche en
    quelques centaines de millisecondes au lieu d'un ecran d'attente.
  * Le texte analyse est la **selection** si elle existe, sinon le document.
    Une correction s'applique alors a la bonne occurrence, et non a la
    premiere trouvee dans tout le fichier.
"""

import threading

from core.ai_prompts import MODE_LABELS, PROMPTS, USER_INSTRUCTIONS
from models.llm.base import CancelledError, LLMError, Message
from models.llm.client import CancelToken
from models.llm.json_parse import extract_json
from models.llm.schemas import schema_for, task_for
from core.theme import T


class AIController:
    """Lance les traitements IA et publie leurs resultats dans l'etat."""

    def __init__(self, page, state, editor, c, tab_ctrl, show_snack, rebuild_fn,
                 clipboard=None, manager=None, get_selection_fn=None,
                 request_consent_fn=None, open_setup_fn=None):
        self._page = page
        self.state = state
        self.editor = editor
        self._c = c
        self._tab = tab_ctrl
        self._snack = show_snack
        self._rebuild = rebuild_fn
        self._clipboard = clipboard
        self.manager = manager
        #: Retourne (debut, fin) de la selection courante, ou None.
        self._get_selection = get_selection_fn or (lambda: None)
        #: Affiche la demande de consentement cloud ; recoit un callback « continuer ».
        self._request_consent = request_consent_fn
        #: Ouvre le dialogue de connexion IA.
        self._open_setup = open_setup_fn or (lambda: None)

        self._cancel = CancelToken()

    # ------------------------------------------------------------------
    # Preparation
    # ------------------------------------------------------------------
    def _resolve_text(self) -> tuple[str, int, int] | None:
        """Texte a traiter : la selection si elle existe, sinon tout le document.

        Retourne (texte, debut, fin) pour pouvoir replacer le resultat au
        bon endroit.
        """
        self._tab.save_content()
        d = self._tab.cur_doc()
        if not d or not d.content.strip():
            self._snack("Rien a analyser.")
            return None

        sel = self._get_selection()
        if sel and sel[1] > sel[0]:
            start, end = sel
            fragment = d.content[start:end]
            if fragment.strip():
                return fragment.strip(), start, end

        return d.content.strip(), 0, len(d.content)

    def _ensure_ready(self) -> bool:
        """Verifie qu'une IA est configuree ; ouvre la configuration sinon."""
        if not self.manager or not self.manager.is_configured():
            self._open_setup()
            return False
        return True

    # ------------------------------------------------------------------
    # Lancement
    # ------------------------------------------------------------------
    def _run_ai(self, mode: str):
        if not self._ensure_ready():
            return

        resolved = self._resolve_text()
        if resolved is None:
            return
        text, start, end = resolved

        # Consentement : le texte de l'utilisateur va quitter sa machine.
        if self.manager.requires_consent(task_for(mode)) and self._request_consent:
            self._request_consent(lambda: self._launch(mode, text, start, end))
            return

        self._launch(mode, text, start, end)

    def _launch(self, mode: str, text: str, start: int, end: int):
        self._cancel.cancel()
        self._cancel = CancelToken()

        state = self.state
        state.clear_ai_results()
        state.ai_mode = mode
        state.show_ai = True
        state.ai_loading = True
        state.ai_stream = ""
        state.ai_source_range = (start, end)
        state.ai_source_text = text
        self._rebuild()

        system_prompt = PROMPTS.get(mode, "")
        instruction = USER_INSTRUCTIONS.get(mode, "{text}").format(text=text)
        schema = schema_for(mode)
        task = task_for(mode)
        cancel = self._cancel

        page = self._page

        def on_chunk(piece: str):
            # Le flux nourrit un compteur : afficher le JSON brut n'aurait
            # aucun sens, mais montrer que ca avance, si.
            state.ai_stream += piece

        def worker():
            try:
                result = self.manager.complete(
                    [Message("system", system_prompt), Message("user", instruction)],
                    task=task, stream=True, on_chunk=on_chunk,
                    json_schema=schema, temperature=0.1,
                    max_tokens=1024 if mode in ("keywords", "summarize") else 4096,
                    cancel=cancel,
                )
            except CancelledError:
                return
            except LLMError as exc:
                state.ai_error = exc.user_message
                state.ai_loading = False
                page.run_thread(self._rebuild)
                return
            except Exception as exc:                     # filet de securite
                state.ai_error = f"Erreur inattendue : {exc}"
                state.ai_loading = False
                page.run_thread(self._rebuild)
                return

            if cancel.cancelled:
                return

            parsed = extract_json(result.text)
            if parsed is None:
                state.ai_error = (
                    "La reponse du modele n'a pas pu etre interpretee.\n"
                    "Essayez un texte plus court ou un modele plus capable."
                )
            else:
                state.dispatch_ai_result(mode, parsed)

            state.ai_loading = False
            state.ai_elapsed = result.elapsed
            state.ai_model_used = f"{result.provider} · {result.model}"
            page.run_thread(self._rebuild)

        threading.Thread(target=worker, daemon=True).start()

    # ------------------------------------------------------------------
    # Prompt libre (Ctrl+K)
    # ------------------------------------------------------------------
    def run_free_prompt(self, instruction: str, on_done=None):
        """Applique une consigne libre au texte selectionne (ou au document)."""
        if not instruction.strip():
            return
        if not self._ensure_ready():
            return

        resolved = self._resolve_text()
        if resolved is None:
            return
        text, start, end = resolved

        def go():
            self._launch_free(instruction.strip(), text, start, end, on_done)

        if self.manager.requires_consent("edit") and self._request_consent:
            self._request_consent(go)
        else:
            go()

    def _launch_free(self, instruction, text, start, end, on_done):
        self._cancel.cancel()
        self._cancel = CancelToken()
        cancel = self._cancel

        state = self.state
        state.clear_ai_results()
        state.ai_mode = "free"
        state.ai_instruction = instruction
        state.ai_loading = True
        state.ai_stream = ""
        state.ai_source_range = (start, end)
        state.ai_source_text = text
        state.show_ai = True
        self._rebuild()

        system = (
            "Tu transformes le texte fourni selon la consigne de l'utilisateur. "
            "Reponds UNIQUEMENT par le texte transforme, sans preambule, sans "
            "guillemets, sans commentaire, en conservant la langue d'origine "
            "sauf si la consigne demande explicitement une traduction."
        )
        user = f"Consigne : {instruction}\n\nTexte :\n{text}"
        page = self._page

        def on_chunk(piece):
            state.ai_stream += piece
            # Le resultat est du texte brut : on peut l'afficher au fil de l'eau.
            state.ai_reformulation = state.ai_stream
            page.run_thread(self._rebuild)

        def worker():
            try:
                result = self.manager.complete(
                    [Message("system", system), Message("user", user)],
                    task="edit", stream=True, on_chunk=on_chunk,
                    temperature=0.3, cancel=cancel,
                )
            except CancelledError:
                return
            except LLMError as exc:
                state.ai_error = exc.user_message
                state.ai_loading = False
                page.run_thread(self._rebuild)
                return

            if cancel.cancelled:
                return

            state.ai_reformulation = result.text.strip()
            state.ai_loading = False
            state.ai_elapsed = result.elapsed
            state.ai_model_used = f"{result.provider} · {result.model}"
            page.run_thread(self._rebuild)
            if on_done:
                page.run_thread(lambda: on_done(state.ai_reformulation))

        threading.Thread(target=worker, daemon=True).start()

    # ------------------------------------------------------------------
    # Points d'entree publics
    # ------------------------------------------------------------------
    def run_correction(self, e=None):
        self._run_ai("correction")

    def run_translate_fr_en(self, e=None):
        self._run_ai("translate_fr_en")

    def run_translate_en_fr(self, e=None):
        self._run_ai("translate_en_fr")

    def run_reformulate(self, e=None):
        self._run_ai("reformulate")

    def run_natural(self, e=None):
        self._run_ai("natural")

    def run_professional(self, e=None):
        self._run_ai("professional")

    def run_summarize(self, e=None):
        self._run_ai("summarize")

    def run_keywords(self, e=None):
        self._run_ai("keywords")

    # ------------------------------------------------------------------
    # Application des resultats
    # ------------------------------------------------------------------
    def apply_correction(self, original: str, replacement: str):
        """Remplace une occurrence, en restant dans la zone analysee."""
        d = self._tab.cur_doc()
        if not d:
            return

        start, end = getattr(self.state, "ai_source_range", (0, len(d.content)))
        end = min(end, len(d.content))
        start = max(0, min(start, end))

        # Chercher d'abord dans la zone reellement analysee : sur un document
        # ou le mot apparait plusieurs fois, c'est ce qui evite de corriger
        # une occurrence que l'utilisateur n'a pas demandee.
        idx = d.content.find(original, start, end)
        if idx == -1:
            idx = d.content.find(original)
        if idx == -1:
            self._snack(f'« {original} » introuvable — le texte a change.',
                        self._c(T.L_WARNING, T.D_WARNING))
            return

        new_text = d.content[:idx] + replacement + d.content[idx + len(original):]
        d.apply_change(new_text)
        d.modified = True
        self.editor.value = d.content

        # Le document a change de longueur : recaler la zone analysee.
        delta = len(replacement) - len(original)
        self.state.ai_source_range = (start, end + delta)

        self._snack(f'« {original} » → « {replacement} »',
                    self._c(T.L_SUCCESS, T.D_SUCCESS))
        self._rebuild()

    def replace_with_result(self, new_text: str):
        """Remplace la zone analysee par le resultat de l'IA."""
        d = self._tab.cur_doc()
        if not d or not new_text:
            return

        start, end = getattr(self.state, "ai_source_range", (0, len(d.content)))
        end = min(end, len(d.content))
        start = max(0, min(start, end))

        if (start, end) == (0, len(d.content)):
            merged = new_text
        else:
            merged = d.content[:start] + new_text + d.content[end:]

        d.apply_change(merged)
        d.modified = True
        self.editor.value = d.content
        self.state.ai_source_range = (start, start + len(new_text))
        self._snack("Texte remplace.", self._c(T.L_SUCCESS, T.D_SUCCESS))
        self._rebuild()

    def copy_result(self, e=None, text=""):
        if not text:
            self._snack("Rien a copier.")
            return
        if not self._clipboard:
            return

        page, snack, c = self._page, self._snack, self._c

        async def _do_copy():
            try:
                await self._clipboard.set(text)
                page.run_thread(lambda: snack("Texte copie.", c(T.L_SUCCESS, T.D_SUCCESS)))
            except Exception:
                page.run_thread(lambda: snack("Erreur lors de la copie.",
                                              c(T.L_ERROR, T.D_ERROR)))

        page.run_task(_do_copy)

    def dismiss_correction(self, item, kind):
        if kind == "corr" and item in self.state.ai_corr:
            self.state.ai_corr.remove(item)
        elif kind == "sugg" and item in self.state.ai_sugg:
            self.state.ai_sugg.remove(item)
        self._rebuild()

    def close_ai(self):
        """Ferme le panneau et interrompt reellement la generation en cours."""
        self._cancel.cancel()
        self.state.ai_loading = False
        self.state.show_ai = False
        self._rebuild()

    def cancel(self):
        self._cancel.cancel()
        self.state.ai_loading = False
        self._rebuild()

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------
    def show_model_manager(self, e=None):
        self._open_setup()
