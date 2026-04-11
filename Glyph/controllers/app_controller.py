"""
controllers/app_controller.py — Contrôleur principal qui orchestre tout.
"""

import ctypes
import threading
import flet as ft

from constants import APP_NAME, APP_VERSION, MODE_READ, resource_path
from theme import T
from models.document import Document
from models.editor_state import EditorState
from models.spell_checker import SpellCheckerWrapper
from models.voice_manager import VoiceManager
from phrase_random import PhrasePlaceHolder

from views.sidebar import build_sidebar
from views.tab_bar import build_tab_bar
from views.menu_bar import build_menu_bar
from views.status_bar import build_status_bar
from views.ai_panel import build_ai_panel
from views.editor_area import create_editor
from views.search_bar import build_search_bar, build_highlight_text
from views.dialogs.emoji_picker import show_emoji_picker
from views.dialogs.help_dialog import show_help
from views.dialogs.info_dialog import show_info, show_credits
from views.dialogs.voice_dialog import show_voice_menu
from views.dialogs.options_dialog import show_options

from controllers.editor_controller import EditorController
from controllers.tab_controller import TabController
from controllers.file_controller import FileController
from controllers.ai_controller import AIController
from controllers.voice_controller import VoiceController
from controllers.keyboard_controller import KeyboardController
from controllers.search_controller import SearchController
from models.file_manager import write_file
from models.session_manager import save_session, load_session, restore_docs


class AppController:
    """Point central de l'application — relie modèles, vues et contrôleurs."""

    def __init__(self, page: ft.Page):
        self.page = page
        self._configure_page()

        # Modèles
        self.state = EditorState()
        self._session_data = load_session()  # chargé tôt, appliqué après config page
        self._apply_session_settings()       # applique les préférences avant la page
        if not self.state.docs:
            self.state.docs.append(Document())
        self.spell = SpellCheckerWrapper(resource_path("ressource/spellchecker/fr.json.gz"))
        self.voice = VoiceManager()
        self.ph = PhrasePlaceHolder()

        # File picker & Clipboard
        self.file_picker = ft.FilePicker()
        self.clipboard = ft.Clipboard()
        page.services.append(self.file_picker)
        page.services.append(self.clipboard)

        # Status bar widgets
        self.st_mode = ft.Text("Mode Texte", size=12, color=self.c(T.L_ACCENT, T.D_ACCENT),
                               font_family="Nunito SemiBold", weight=ft.FontWeight.W_600)
        self.st_msg = ft.Text("", size=12, color=self.c(T.L_TERTIARY, T.D_TERTIARY), expand=True)
        self.st_chars = ft.Text("0 car.", size=12, color=self.c(T.L_TERTIARY, T.D_TERTIARY))
        self.st_words = ft.Text("0 mots", size=12, color=self.c(T.L_TERTIARY, T.D_TERTIARY))
        self.st_zoom = ft.Text("100 %", size=12, color=self.c(T.L_TERTIARY, T.D_TERTIARY))

        # Sélection courante (mise à jour par on_selection_change)
        self._selection = None
        self._ctrl_pressed = False

        # Editor
        self.editor = create_editor(
            self.c, self.ph.get_random_phrase(),
            self._on_text_changed, self._on_selection_change,
        )

        # Conteneurs persistants pour animations fluides
        self._sidebar = ft.Container(
            width=56,  # état initial (collapsed)
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            animate=ft.Animation(250, ft.AnimationCurve.EASE_OUT_CUBIC),
        )
        self._toolbar_wrap = ft.Container(
            height=60,
            opacity=1.0,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT_CUBIC),
            animate_opacity=ft.Animation(200, ft.AnimationCurve.EASE_OUT_CUBIC),
        )
        self._tab_bar_wrap = ft.Container()
        self._editor_wrap = ft.Container(
            expand=True,
            scale=ft.Scale(scale=1.0),
            animate_scale=ft.Animation(250, ft.AnimationCurve.EASE_OUT_CUBIC),
        )
        self._scroll_detector = ft.GestureDetector(
            expand=True,
            on_scroll=self._on_editor_scroll,
        )

        # Sous-contrôleurs
        self.tab_ctrl = TabController(
            self.state, self.editor, self.ph, self.rebuild, self.update_status,
        )
        self.editor_ctrl = EditorController(
            self.state, self.editor, self.tab_ctrl.cur_doc,
            self.rebuild, self.update_status, page,
        )
        self.file_ctrl = FileController(
            page, self.state, self.editor, self.c, self.file_picker,
            self.tab_ctrl, self.show_snack, self.rebuild,
        )
        self.ai_ctrl = AIController(
            page, self.state, self.editor, self.c,
            self.tab_ctrl, self.show_snack, self.rebuild,
            clipboard=self.clipboard,
        )
        self.voice_ctrl = VoiceController(
            page, self.voice, self.editor, self.c,
            self.tab_ctrl, self.show_snack, self.rebuild,
        )
        self.search_ctrl = SearchController(
            self.state, self.editor, self.state.search,
            self.tab_ctrl, self.update_status, self.rebuild, page,
        )
        self.kb_ctrl = KeyboardController(
            page, self.c, self.tab_ctrl, self.file_ctrl,
            self.ai_ctrl, self.voice_ctrl,
            self.check_spelling, self._show_emoji_picker,
            self._request_close, self.toggle_toolbar,
            undo=self.undo, redo=self.redo,
            search_ctrl=self.search_ctrl,
            zoom_in=self.zoom_in, zoom_out=self.zoom_out,
            set_mode=self.set_mode,
        )
        self.kb_ctrl._zoom_reset = self.zoom_reset

        # Connecter auto-save : EditorController → FileController
        self.editor_ctrl._auto_save_callback = self.file_ctrl.auto_save
        self.file_ctrl._st_msg = self.st_msg
        self.file_ctrl._save_session = self._save_session
        self.file_ctrl._refresh_tab_bar = self._refresh_tab_bar
        self.tab_ctrl._on_tabs_changed = self._save_session

        # Raccourcis clavier (avec tracking Ctrl pour Ctrl+molette)
        async def _on_keyboard(e):
            self._ctrl_pressed = e.ctrl
            await self.kb_ctrl.on_keyboard_event(e)
        page.on_keyboard_event = _on_keyboard

        # Interception de la fermeture de fenêtre
        page.window.prevent_close = True
        page.window.on_event = self._on_window_event

        # Restaurer les onglets de la session précédente
        self._apply_session_tabs()
        self._session_data = None  # libérer la mémoire

        # Render initial
        self.update_status()
        self.rebuild()

    # ------------------------------------------------------------------
    # Page
    # ------------------------------------------------------------------
    def _configure_page(self):
        p = self.page
        p.title = f"{APP_NAME} — v{APP_VERSION}"
        p.theme_mode = ft.ThemeMode.LIGHT  # défaut, écrasé par _apply_session_settings
        p.padding = 0
        p.spacing = 0
        p.window = ft.Window(width=1280, height=820, min_width=1050, min_height=550,
                              icon=resource_path("ressource/icon/icon.ico"))

        # Polices Nunito
        p.fonts = {
            "Nunito": "Font/Nunito/static/Nunito-Regular.ttf",
            "Nunito SemiBold": "Font/Nunito/static/Nunito-SemiBold.ttf",
            "Nunito Bold": "Font/Nunito/static/Nunito-Bold.ttf",
        }
        p.theme = ft.Theme(font_family="Nunito")
        p.dark_theme = ft.Theme(font_family="Nunito")

    # ------------------------------------------------------------------
    # Session persistence
    # ------------------------------------------------------------------
    def _save_session(self):
        """Sauvegarde la session courante (options + onglets) sur disque."""
        theme = "dark" if self.dark() else "light"
        editor_content = self.editor.value if self.editor else None
        save_session(self.state, theme, editor_content)

    # ------------------------------------------------------------------
    # Session restore
    # ------------------------------------------------------------------
    def _apply_session_settings(self):
        """Applique les préférences sauvegardées (thème, zoom, etc.)."""
        data = self._session_data
        if not data or "settings" not in data:
            return
        s = data["settings"]
        if s.get("theme") == "dark":
            self.page.theme_mode = ft.ThemeMode.DARK
        else:
            self.page.theme_mode = ft.ThemeMode.LIGHT
        self.state.auto_save = bool(s.get("auto_save", False))
        zoom = s.get("zoom_level", 100)
        if isinstance(zoom, (int, float)) and 50 <= zoom <= 200:
            self.state.zoom_level = int(zoom)
        self.state.show_toolbar = bool(s.get("show_toolbar", True))
        self.state.sidebar_collapsed = bool(s.get("sidebar_collapsed", True))
        mode = s.get("mode", "text")
        if mode in ("text", "calc", "read"):
            self.state.mode = mode
        # Modele IA selectionne
        ai_model = s.get("ai_selected_model", "")
        if isinstance(ai_model, str):
            self.state.ai_selected_model = ai_model

    def _apply_session_tabs(self):
        """Restaure les onglets depuis la session sauvegardée."""
        data = self._session_data
        if not data or "tabs" not in data:
            return
        tabs_data = data["tabs"]
        if not isinstance(tabs_data, list) or not tabs_data:
            return
        docs, missing = restore_docs(tabs_data)
        if not docs:
            return
        self.state.docs = docs
        active = data.get("active_tab", 0)
        if isinstance(active, int) and 0 <= active < len(docs):
            self.state.idx = active
        else:
            self.state.idx = 0
        # Synchroniser l'éditeur avec l'onglet actif
        self.tab_ctrl.sync_editor()
        if missing:
            self.show_snack(
                f"{missing} fichier(s) introuvable(s) — restauré(s) depuis la session."
            )

    # ------------------------------------------------------------------
    # Theme helpers
    # ------------------------------------------------------------------
    def dark(self):
        return self.page.theme_mode == ft.ThemeMode.DARK

    def c(self, l, d):
        return d if self.dark() else l

    def show_snack(self, msg, color=None):
        self.page.show_dialog(
            ft.SnackBar(
                content=ft.Text(msg, color="#FFFFFF", size=13),
                bgcolor=color or self.c(T.L_PRIMARY, T.D_SURFACE),
                duration=3000,
                open=True,
            )
        )

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------
    def update_status(self):
        d = self.tab_ctrl.cur_doc()
        if not d:
            return
        t = d.content
        self.st_chars.value = f"{len(t)} car."
        self.st_words.value = f"{len(t.split()) if t.strip() else 0} mots"
        self.st_mode.value = {
            "text": "Mode Texte", "calc": "Mode Calcul", "read": "Mode Lecture"
        }.get(self.state.mode, "Mode Texte")

        search = self.state.search
        if search.visible and search.query:
            if search.matches:
                match = search.current_match()
                ctx = self._search_context(t, match) if match else ""
                self.st_msg.value = (
                    f"Recherche : {search.current_index + 1}/{search.total}"
                    f"  —  {ctx}" if ctx else
                    f"Recherche : {search.current_index + 1}/{search.total} résultat(s)"
                )
                self.st_msg.color = self.c(T.L_ACCENT, T.D_ACCENT)
            else:
                self.st_msg.value = f"Recherche : aucun résultat pour « {search.query} »"
                self.st_msg.color = self.c(T.L_WARNING, T.D_WARNING)
        elif d.modified:
            self.st_msg.value = "Modifications non enregistrées"
            self.st_msg.color = self.c(T.L_WARNING, T.D_WARNING)
        elif d.path:
            if not self.st_msg.value or self.st_msg.value == "Modifications non enregistrées":
                self.st_msg.value = ""
            self.st_msg.color = self.c(T.L_TERTIARY, T.D_TERTIARY)
        else:
            self.st_msg.value = ""
            self.st_msg.color = self.c(T.L_TERTIARY, T.D_TERTIARY)

    @staticmethod
    def _search_context(text: str, match: tuple[int, int]) -> str:
        """Retourne le numéro de ligne et un extrait autour du match."""
        start, end = match
        line_num = text[:start].count("\n") + 1
        # Extraire un bout de contexte autour du match
        ctx_start = max(0, start - 20)
        ctx_end = min(len(text), end + 20)
        before = text[ctx_start:start].replace("\n", " ")
        matched = text[start:end]
        after = text[end:ctx_end].replace("\n", " ")
        prefix = "..." if ctx_start > 0 else ""
        suffix = "..." if ctx_end < len(text) else ""
        return f"Ligne {line_num} : {prefix}{before}[{matched}]{after}{suffix}"

    # ------------------------------------------------------------------
    # Editor event delegate
    # ------------------------------------------------------------------
    def _on_selection_change(self, e):
        self._selection = e.control.selection

    def _on_text_changed(self, e):
        self.editor_ctrl.on_text_changed(e)

    # ------------------------------------------------------------------
    # Modes
    # ------------------------------------------------------------------
    def set_mode(self, mode):
        self.state.mode = mode
        self.editor.read_only = (mode == MODE_READ)
        self.update_status()
        self.show_snack({
            "text": "Mode texte", "calc": "Mode calcul", "read": "Mode lecture"
        }.get(mode, ""))
        self.rebuild()
        self._save_session()

    # ------------------------------------------------------------------
    # Undo / Redo
    # ------------------------------------------------------------------
    def undo(self, e=None):
        self.tab_ctrl.save_content()
        d = self.tab_ctrl.cur_doc()
        if not d:
            return
        result = d.undo()
        if result is None:
            self.show_snack("Rien à annuler.")
            return
        self.editor.value = result
        d.modified = True
        self.update_status()
        self.page.update()

    def redo(self, e=None):
        self.tab_ctrl.save_content()
        d = self.tab_ctrl.cur_doc()
        if not d:
            return
        result = d.redo()
        if result is None:
            self.show_snack("Rien à rétablir.")
            return
        self.editor.value = result
        d.modified = True
        self.update_status()
        self.page.update()

    # ------------------------------------------------------------------
    # Zoom
    # ------------------------------------------------------------------
    _BASE_TEXT_SIZE = 16

    def _zoom_text_size(self):
        """Retourne la taille de texte correspondant au niveau de zoom actuel."""
        return round(self._BASE_TEXT_SIZE * self.state.zoom_level / 100)

    def _apply_zoom(self, direction=0):
        """Applique le zoom avec une animation scale en 2 temps (overshoot + retour)."""
        sz = self._zoom_text_size()
        self.editor.text_size = sz
        self.editor.text_style = ft.TextStyle(
            size=sz,
            height=1.4,
            font_family="Nunito",
            letter_spacing=0.2,
            color=self.editor.text_style.color if self.editor.text_style else self.c(T.L_PRIMARY, T.D_PRIMARY),
        )
        self.editor.hint_style = ft.TextStyle(
            size=sz, font_family="Nunito", letter_spacing=0.2,
            color=self.c(T.L_MUTED, T.D_MUTED), italic=True,
        )
        self.st_zoom.value = f"{self.state.zoom_level} %"
        self.st_zoom.color = self.c(T.L_TERTIARY, T.D_TERTIARY)

        # Animation scale overshoot : zoom in → 1.03, zoom out → 0.97, puis retour à 1.0
        if hasattr(self, '_editor_wrap') and self._editor_wrap and direction != 0:
            # Annuler tout timer précédent pour éviter les conflits
            if hasattr(self, '_zoom_timer') and self._zoom_timer:
                self._zoom_timer.cancel()
            # Forcer le retour à 1.0 d'abord (sans animation perceptible)
            # pour que le prochain overshoot produise toujours un delta
            self._editor_wrap.scale = ft.Scale(scale=1.0)
            self.page.update()
            # Appliquer l'overshoot
            overshoot = 1.03 if direction > 0 else 0.97
            self._editor_wrap.scale = ft.Scale(scale=overshoot)
            self.page.update()
            # Retour progressif à 1.0
            def settle():
                self._editor_wrap.scale = ft.Scale(scale=1.0)
                self.page.update()
            self._zoom_timer = threading.Timer(0.2, settle)
            self._zoom_timer.start()
        else:
            self.page.update()

    @staticmethod
    def _is_ctrl_pressed():
        """Vérifie l'état réel de Ctrl via l'API Windows."""
        try:
            return bool(ctypes.windll.user32.GetAsyncKeyState(0x11) & 0x8000)
        except (AttributeError, OSError):
            return False

    def _on_editor_scroll(self, e: ft.ScrollEvent):
        """Ctrl+molette → zoom in/out."""
        if not self._is_ctrl_pressed():
            return
        dy = e.scroll_delta.y
        if dy < 0:
            self.zoom_in()
        elif dy > 0:
            self.zoom_out()

    def zoom_in(self):
        if self.state.zoom_level >= 200:
            self.show_snack("Zoom maximum atteint (200 %)")
            return
        self.state.zoom_level = min(200, self.state.zoom_level + 10)
        self._apply_zoom(direction=1)
        self._save_session()

    def zoom_out(self):
        if self.state.zoom_level <= 50:
            self.show_snack("Zoom minimum atteint (50 %)")
            return
        self.state.zoom_level = max(50, self.state.zoom_level - 10)
        self._apply_zoom(direction=-1)
        self._save_session()

    def zoom_reset(self):
        if self.state.zoom_level == 100:
            return
        self.state.zoom_level = 100
        self._apply_zoom()
        self._save_session()

    # ------------------------------------------------------------------
    # Clipboard & Clear
    # ------------------------------------------------------------------
    def _get_selection(self):
        """Retourne (start, end) de la sélection ou None si pas de sélection."""
        sel = self._selection
        if sel and not sel.is_collapsed:
            start = min(sel.start, sel.end)
            end = max(sel.start, sel.end)
            return start, end
        return None

    def _get_cursor_pos(self):
        """Retourne la position du curseur (ou fin du texte si inconnu)."""
        sel = self._selection
        if sel:
            return sel.start
        d = self.tab_ctrl.cur_doc()
        return len(d.content) if d else 0

    async def copy_text(self):
        """Copie la sélection ou tout le texte dans le presse-papier."""
        self.tab_ctrl.save_content()
        d = self.tab_ctrl.cur_doc()
        if not d or not d.content.strip():
            self.show_snack("Rien à copier.")
            return
        sel = self._get_selection()
        if sel:
            text = d.content[sel[0]:sel[1]]
            await self.clipboard.set(text)
            self.show_snack("Sélection copiée.")
        else:
            await self.clipboard.set(d.content)
            self.show_snack("Texte copié dans le presse-papier.")

    async def paste_text(self):
        """Colle à la position du curseur, remplace la sélection si active."""
        clip = await self.clipboard.get()
        if not clip:
            self.show_snack("Presse-papier vide.")
            return
        self.tab_ctrl.save_content()
        self.editor_ctrl.force_snapshot()
        d = self.tab_ctrl.cur_doc()
        if not d:
            return
        sel = self._get_selection()
        if sel:
            d.content = d.content[:sel[0]] + clip + d.content[sel[1]:]
        else:
            cursor = self._get_cursor_pos()
            d.content = d.content[:cursor] + clip + d.content[cursor:]
        d.modified = True
        self.editor.value = d.content
        self.update_status()
        self.rebuild()
        self.show_snack("Texte collé.")

    async def _copy_text_handler(self, e):
        """Handler d'événement async pour le bouton Copier."""
        await self.copy_text()

    async def _paste_text_handler(self, e):
        """Handler d'événement async pour le bouton Coller."""
        await self.paste_text()

    async def _cut_text_handler(self, e):
        """Handler d'événement async pour le bouton Couper."""
        await self.cut_text()

    async def cut_text(self):
        """Coupe la sélection ou tout le texte."""
        self.tab_ctrl.save_content()
        self.editor_ctrl.force_snapshot()
        d = self.tab_ctrl.cur_doc()
        if not d or not d.content.strip():
            self.show_snack("Rien à couper.")
            return
        sel = self._get_selection()
        if sel:
            text = d.content[sel[0]:sel[1]]
            await self.clipboard.set(text)
            d.content = d.content[:sel[0]] + d.content[sel[1]:]
            self.show_snack("Sélection coupée.")
        else:
            await self.clipboard.set(d.content)
            d.content = ""
            self.show_snack("Texte coupé dans le presse-papier.")
        d.modified = True
        self.editor.value = d.content
        self.update_status()
        self.rebuild()

    def clear_text(self):
        """Affiche un dialogue de confirmation avant d'effacer tout le texte."""
        self.tab_ctrl.save_content()
        self.editor_ctrl.force_snapshot()
        d = self.tab_ctrl.cur_doc()
        if not d or not d.content.strip():
            self.show_snack("L'éditeur est déjà vide.")
            return

        # Capturer l'index ET le document au moment du clic,
        # pour éviter d'effacer le mauvais onglet si l'utilisateur change.
        target_idx = self.state.idx
        target_doc = d
        target_title = d.title or "Sans titre"

        def confirm(e):
            self.page.pop_dialog()
            # Vérifier que l'onglet cible existe encore
            if target_idx >= len(self.state.docs) or self.state.docs[target_idx] is not target_doc:
                self.show_snack("L'onglet a été fermé entre-temps.",
                                self.c(T.L_WARNING, T.D_WARNING))
                return
            target_doc.content = ""
            target_doc.modified = True
            # Si l'onglet cible est toujours l'onglet actif, mettre à jour le widget
            if self.state.idx == target_idx:
                self.editor.value = ""
            self.update_status()
            self.rebuild()
            self.show_snack("Contenu effacé.", self.c(T.L_WARNING, T.D_WARNING))

        def cancel(e):
            self.page.pop_dialog()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Effacer le contenu", size=16,
                          font_family="Nunito SemiBold", weight=ft.FontWeight.W_600),
            content=ft.Text(
                f"Tout le texte de « {target_title} » sera supprimé.\n"
                "Cette action est irréversible.",
                size=14, color=self.c(T.L_SECONDARY, T.D_SECONDARY),
            ),
            actions=[
                ft.TextButton("Annuler", on_click=cancel),
                ft.ElevatedButton(
                    "Effacer",
                    bgcolor=self.c(T.L_ERROR, T.D_ERROR),
                    color="#FFFFFF",
                    on_click=confirm,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.show_dialog(dlg)

    # ------------------------------------------------------------------
    # Spelling
    # ------------------------------------------------------------------
    def check_spelling(self, e=None):
        if not self.spell.available:
            self.show_snack("pyspellchecker non installé.",
                             self.c(T.L_WARNING, T.D_WARNING))
            return
        self.tab_ctrl.save_content()
        d = self.tab_ctrl.cur_doc()
        if not d:
            return
        wrong = self.spell.check(d.content)
        if wrong:
            self.show_snack(
                f"{len(wrong)} faute(s) : {', '.join(list(wrong)[:8])}",
                self.c(T.L_WARNING, T.D_WARNING),
            )
        else:
            self.show_snack("Aucune faute !", self.c(T.L_SUCCESS, T.D_SUCCESS))

    # ------------------------------------------------------------------
    # Dialog wrappers
    # ------------------------------------------------------------------
    def _show_emoji_picker(self):
        def insert_emoji(ch):
            d = self.tab_ctrl.cur_doc()
            if d:
                d.content = (self.editor.value or "") + ch
                self.editor.value = d.content
                d.modified = True
            self.rebuild()
        show_emoji_picker(self.page, self.c, {"insert_emoji": insert_emoji})

    def _show_voice_menu(self):
        show_voice_menu(self.page, self.c, {
            "read_text": self.voice_ctrl.read_text,
            "voice_typing": self.voice_ctrl.voice_typing,
            "voice_ms": self.voice_ctrl.voice_ms,
        })

    def _show_options(self):
        show_options(self.page, self.c, self.dark, {
            "set_mode": self.set_mode,
            "toggle_theme": self.toggle_theme,
            "toggle_auto_save": self.toggle_auto_save,
            "is_auto_save": lambda: self.state.auto_save,
            "show_model_manager": self.ai_ctrl.show_model_manager,
            "show_help": lambda: show_help(self.page, self.c),
            "show_info": lambda: show_info(self.page, self.c),
            "show_credits": lambda: show_credits(self.page, self.c),
        })

    # ------------------------------------------------------------------
    # Fermeture de l'application
    # ------------------------------------------------------------------
    async def _on_window_event(self, e):
        if e.type != ft.WindowEventType.CLOSE:
            return
        await self._request_close()

    async def _request_close(self):
        """Demande de fermeture — sauvegarde la session puis propose de sauvegarder les docs."""
        self._save_session()
        if not self.file_ctrl.has_unsaved_docs():
            await self.page.window.destroy()
            return
        self._show_close_dialog()

    async def _save_all_and_quit(self):
        """Enregistre tous les documents modifiés puis ferme l'application.

        - Documents avec chemin : sauvegarde directe.
        - Documents sans chemin : ouvre « Enregistrer sous » pour chacun.
          Si l'utilisateur annule un dialogue, la fermeture est abandonnée.
        """
        self.tab_ctrl.save_content()
        for d in self.state.docs:
            if not d.modified:
                continue
            if d.path:
                try:
                    write_file(d.path, d.content)
                    d.modified = False
                except OSError:
                    pass
            else:
                path = await self.file_picker.save_file(
                    dialog_title=f"Enregistrer « {d.title} » avant de quitter",
                    file_name=(d.title + ".txt"),
                    allowed_extensions=["txt"],
                )
                if not path:
                    self.show_snack("Fermeture annulée.")
                    self.rebuild()
                    return
                d.path = path
                d.title = __import__("os").path.basename(path)
                try:
                    write_file(d.path, d.content)
                    d.modified = False
                except OSError:
                    pass
        self._save_session()
        await self.page.window.destroy()

    def _show_close_dialog(self):
        has_pathless = any(d.modified and not d.path for d in self.state.docs)

        async def save_and_quit(e):
            self.page.pop_dialog()
            await self._save_all_and_quit()

        async def quit_without_save(e):
            self.page.pop_dialog()
            self._save_session()  # sauvegarder la session pour restaurer les onglets
            await self.page.window.destroy()

        def cancel(e):
            self.page.pop_dialog()

        detail_lines = []
        for d in self.state.docs:
            if d.modified:
                label = d.title or "Sans titre"
                tag = " (nouveau)" if not d.path else ""
                detail_lines.append(f"  • {label}{tag}")
        detail = "\n".join(detail_lines)

        note = ""
        if has_pathless:
            note = "\n\nLes documents marqués (nouveau) nécessiteront de choisir un emplacement."

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Modifications non enregistrées", size=16,
                          font_family="Nunito SemiBold", weight=ft.FontWeight.W_600),
            content=ft.Text(
                f"Les documents suivants ont été modifiés :\n{detail}{note}",
                size=14, color=self.c(T.L_SECONDARY, T.D_SECONDARY),
            ),
            actions=[
                ft.TextButton("Annuler", on_click=cancel),
                ft.TextButton("Quitter sans enregistrer",
                              on_click=quit_without_save),
                ft.ElevatedButton(
                    "Enregistrer et quitter",
                    bgcolor=self.c(T.L_ACCENT, T.D_ACCENT),
                    color="#FFFFFF",
                    on_click=save_and_quit,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.show_dialog(dlg)

    def toggle_auto_save(self):
        self.state.auto_save = not self.state.auto_save
        label = "activée" if self.state.auto_save else "désactivée"
        self.show_snack(f"Sauvegarde automatique {label}")
        self.rebuild()
        self._save_session()

    def toggle_theme(self):
        self.page.theme_mode = ft.ThemeMode.LIGHT if self.dark() else ft.ThemeMode.DARK
        self.rebuild()
        self._save_session()

    # ------------------------------------------------------------------
    # Callbacks dicts
    # ------------------------------------------------------------------
    def toggle_sidebar(self):
        self.state.sidebar_collapsed = not self.state.sidebar_collapsed
        self._sidebar.width = 56 if self.state.sidebar_collapsed else 240
        self._sidebar.content = build_sidebar(
            self.state, self.c, self._sidebar_callbacks(),
        )
        self.page.update()
        self._save_session()

    def toggle_toolbar(self):
        self.state.show_toolbar = not self.state.show_toolbar
        if self.state.show_toolbar:
            self._toolbar_wrap.content = build_menu_bar(
                self.c, self._menu_bar_callbacks(),
            )
            self._toolbar_wrap.height = 60
            self._toolbar_wrap.opacity = 1.0
        else:
            self._toolbar_wrap.height = 0
            self._toolbar_wrap.opacity = 0.0
        self.page.update()
        self._save_session()

    def _sidebar_callbacks(self):
        return {
            "toggle_sidebar": self.toggle_sidebar,
            "open_file": self.file_ctrl.open_file,
            "save_file": self.file_ctrl.save_file,
            "save_file_as": self.file_ctrl.save_file_as,
            "add_tab": self.tab_ctrl.add_tab,
            "rename_file": self.file_ctrl.rename_current_file,
            "print_file": self.file_ctrl.print_file,
            "show_help": lambda: show_help(self.page, self.c),
            "show_options": self._show_options,
        }

    def _switch_tab(self, idx):
        self.editor_ctrl.reset_snapshot_tracking()
        self.tab_ctrl.switch_tab(idx)
        self.search_ctrl.on_tab_switch()
        self._save_session()

    def _refresh_tab_bar(self):
        """Met à jour la barre d'onglets sans reconstruire toute l'interface."""
        self._tab_bar_wrap.content = build_tab_bar(
            self.state, self.c, self._tab_bar_callbacks())

    def _tab_bar_callbacks(self):
        return {
            "switch_tab": self._switch_tab,
            "close_tab": self._confirm_close_tab,
            "add_tab": self.tab_ctrl.add_tab,
        }

    def _confirm_close_tab(self, idx):
        """Demande confirmation si l'onglet a des modifications non enregistrées."""
        docs = self.state.docs
        if idx < 0 or idx >= len(docs):
            return
        d = docs[idx]
        if not d.modified:
            self.tab_ctrl.close_tab(idx)
            return

        async def save_and_close(e):
            """Enregistre vers le chemin existant puis ferme l'onglet."""
            self.page.pop_dialog()
            self.tab_ctrl.save_content()
            if d.path:
                try:
                    write_file(d.path, d.content)
                    d.modified = False
                except OSError:
                    pass
            self.tab_ctrl.close_tab(idx)

        async def save_as_and_close(e):
            """Ouvre « Enregistrer sous » puis ferme l'onglet."""
            self.page.pop_dialog()
            self.tab_ctrl.save_content()
            path = await self.file_picker.save_file(
                dialog_title=f"Enregistrer « {d.title or 'Sans titre'} »",
                file_name=(d.title + ".txt"),
                allowed_extensions=["txt"],
            )
            if not path:
                return  # l'utilisateur a annulé → on ne ferme pas l'onglet
            d.path = path
            d.title = __import__("os").path.basename(path)
            try:
                write_file(d.path, d.content)
                d.modified = False
            except OSError:
                pass
            self.tab_ctrl.close_tab(idx)

        def close_without_save(e):
            self.page.pop_dialog()
            d.modified = False
            self.tab_ctrl.close_tab(idx)

        def cancel(e):
            self.page.pop_dialog()

        title = d.title or "Sans titre"
        has_path = bool(d.path)

        actions = [ft.TextButton("Annuler", on_click=cancel)]
        actions.append(ft.TextButton("Fermer sans enregistrer",
                                     on_click=close_without_save))
        if has_path:
            actions.append(ft.TextButton("Enregistrer sous",
                                         on_click=save_as_and_close))
            actions.append(ft.ElevatedButton(
                "Enregistrer",
                bgcolor=self.c(T.L_ACCENT, T.D_ACCENT),
                color="#FFFFFF",
                on_click=save_and_close,
            ))
        else:
            actions.append(ft.ElevatedButton(
                "Enregistrer sous",
                bgcolor=self.c(T.L_ACCENT, T.D_ACCENT),
                color="#FFFFFF",
                on_click=save_as_and_close,
            ))

        hint = "" if has_path else " Ce document n'a pas encore été enregistré."
        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Fermer l'onglet", size=16, font_family="Nunito SemiBold",
                          weight=ft.FontWeight.W_600),
            content=ft.Text(
                f"« {title} » a été modifié.{hint}",
                size=14, color=self.c(T.L_SECONDARY, T.D_SECONDARY),
            ),
            actions=actions,
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.show_dialog(dlg)

    def _menu_bar_callbacks(self):
        return {
            "run_correction": self.ai_ctrl.run_correction,
            "run_translate_fr_en": self.ai_ctrl.run_translate_fr_en,
            "run_translate_en_fr": self.ai_ctrl.run_translate_en_fr,
            "run_reformulate": self.ai_ctrl.run_reformulate,
            "run_natural": self.ai_ctrl.run_natural,
            "run_professional": self.ai_ctrl.run_professional,
            "run_summarize": self.ai_ctrl.run_summarize,
            "run_keywords": self.ai_ctrl.run_keywords,
            "show_model_manager": self.ai_ctrl.show_model_manager,
            "show_emoji_picker": self._show_emoji_picker,
            "show_voice_menu": self._show_voice_menu,
            "copy_text_handler": self._copy_text_handler,
            "paste_text_handler": self._paste_text_handler,
            "cut_text_handler": self._cut_text_handler,
            "clear_text": self.clear_text,
            "undo": self.undo,
            "redo": self.redo,
            "toggle_search": self.search_ctrl.toggle_search,
            "zoom_in": self.zoom_in,
            "zoom_out": self.zoom_out,
            "set_mode": self.set_mode,
        }

    def _ai_panel_callbacks(self):
        return {
            "close_ai": self.ai_ctrl.close_ai,
            "apply_correction": self.ai_ctrl.apply_correction,
            "dismiss_correction": self.ai_ctrl.dismiss_correction,
            "replace_with_result": self.ai_ctrl.replace_with_result,
            "copy_result": self.ai_ctrl.copy_result,
        }

    # ------------------------------------------------------------------
    # Full rebuild
    # ------------------------------------------------------------------
    def _search_bar_callbacks(self):
        return {
            "on_query_change": self.search_ctrl.on_query_change,
            "on_search": lambda e: self.search_ctrl.go_next(),
            "on_next": self.search_ctrl.go_next,
            "on_prev": self.search_ctrl.go_prev,
            "on_close": self.search_ctrl.close_search,
            "toggle_case": self.search_ctrl.toggle_case,
            "toggle_whole_word": self.search_ctrl.toggle_whole_word,
            "toggle_regex": self.search_ctrl.toggle_regex,
        }

    def rebuild(self):
        self.update_status()
        sz = self._zoom_text_size()
        self.editor.text_size = sz
        self.editor.hint_style = ft.TextStyle(
            size=sz, font_family="Nunito", letter_spacing=0.2,
            color=self.c(T.L_MUTED, T.D_MUTED), italic=True)
        self.st_zoom.value = f"{self.state.zoom_level} %"
        self.st_zoom.color = self.c(T.L_TERTIARY, T.D_TERTIARY)
        self.editor.cursor_color = self.c(T.L_ACCENT, T.D_ACCENT)
        self.editor.selection_color = ft.Colors.with_opacity(
            0.45, self.c(T.L_HL_CURRENT, T.D_HL_CURRENT))
        self.editor.read_only = (self.state.mode == MODE_READ)
        self.st_mode.color = self.c(T.L_ACCENT, T.D_ACCENT)
        self.st_chars.color = self.c(T.L_TERTIARY, T.D_TERTIARY)
        self.st_words.color = self.c(T.L_TERTIARY, T.D_TERTIARY)

        # Construire les éléments de la zone centrale
        search = self.state.search
        has_highlights = search.visible and search.matches
        center_controls = []

        # Toolbar animée (conteneur persistant — hauteur 60↔0)
        self._toolbar_wrap.content = build_menu_bar(self.c, self._menu_bar_callbacks())
        if self.state.show_toolbar:
            self._toolbar_wrap.height = 60
            self._toolbar_wrap.opacity = 1.0
        else:
            self._toolbar_wrap.height = 0
            self._toolbar_wrap.opacity = 0.0
        center_controls.append(self._toolbar_wrap)
        if search.visible:
            search_bar, search_field, search_counter = build_search_bar(
                self.c, search, self._search_bar_callbacks(),
            )
            self.search_ctrl.counter_ref = search_counter
            center_controls.append(search_bar)

        # Mode surlignage : texte transparent + couche Text colorée dessous
        if has_highlights:
            self.editor.text_style = ft.TextStyle(
                size=sz, height=1.4, font_family="Nunito", letter_spacing=0.2,
                color=ft.Colors.TRANSPARENT,
            )
            d = self.tab_ctrl.cur_doc()
            text = d.content if d else ""
            highlight_text = build_highlight_text(
                text, search.matches, search.current_index, self.c,
            )
            hl_container = ft.Container(
                expand=True, padding=30,
                content=highlight_text,
            )
            # Stocker les refs pour mise à jour sans rebuild
            self.search_ctrl.highlight_container = hl_container
            self.search_ctrl._c = self.c
            editor_area = ft.Stack(
                expand=True,
                controls=[
                    # Couche basse : texte surligné (visible)
                    hl_container,
                    # Couche haute : éditeur transparent (capture l'input)
                    self.editor,
                ],
            )
        else:
            self.editor.text_style = ft.TextStyle(
                size=sz, height=1.4, font_family="Nunito", letter_spacing=0.2,
                color=self.c(T.L_PRIMARY, T.D_PRIMARY),
            )
            self.search_ctrl.highlight_container = None
            editor_area = ft.Container(expand=True, content=self.editor)

        self._editor_wrap.content = editor_area
        self._scroll_detector.content = self._editor_wrap
        center_controls.append(self._scroll_detector)

        # Sidebar animée (conteneur persistant)
        self._sidebar.width = 56 if self.state.sidebar_collapsed else 240
        self._sidebar.content = build_sidebar(self.state, self.c, self._sidebar_callbacks())

        self._tab_bar_wrap.content = build_tab_bar(self.state, self.c, self._tab_bar_callbacks())

        layout = ft.Row(expand=True, spacing=0, controls=[
            self._sidebar,
            ft.Column(expand=True, spacing=0, controls=[
                self._tab_bar_wrap,
                ft.Container(
                    expand=True, bgcolor=self.c(T.L_EDITOR, T.D_EDITOR),
                    content=ft.Column(expand=True, spacing=0,
                                      controls=center_controls),
                ),
                build_status_bar(self.c, self.st_mode, self.st_msg,
                                 self.st_chars, self.st_words, self.st_zoom),
            ]),
            build_ai_panel(self.state, self.c, self._ai_panel_callbacks()),
        ])

        # Fade-in subtil au premier rendu
        is_first = not self.page.controls
        self.page.controls.clear()
        if is_first:
            self.page.add(ft.Container(
                content=layout, expand=True,
                opacity=0, animate_opacity=ft.Animation(400, ft.AnimationCurve.EASE_OUT),
            ))
            self.page.update()
            self.page.controls[0].opacity = 1
        else:
            self.page.add(layout)
        self.page.update()
