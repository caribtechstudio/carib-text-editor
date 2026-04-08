"""
controllers/app_controller.py — Contrôleur principal qui orchestre tout.
"""

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
from models.file_manager import write_file


class AppController:
    """Point central de l'application — relie modèles, vues et contrôleurs."""

    def __init__(self, page: ft.Page):
        self.page = page
        self._configure_page()

        # Modèles
        self.state = EditorState()
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
        self.st_mode = ft.Text("Texte", size=12, color=self.c(T.L_ACCENT, T.D_ACCENT),
                               font_family="Nunito SemiBold", weight=ft.FontWeight.W_600)
        self.st_msg = ft.Text("", size=12, color=self.c(T.L_TERTIARY, T.D_TERTIARY), expand=True)
        self.st_chars = ft.Text("0 car.", size=12, color=self.c(T.L_TERTIARY, T.D_TERTIARY))
        self.st_words = ft.Text("0 mots", size=12, color=self.c(T.L_TERTIARY, T.D_TERTIARY))

        # Sélection courante (mise à jour par on_selection_change)
        self._selection = None

        # Editor
        self.editor = create_editor(
            self.c, self.ph.get_random_phrase(),
            self._on_text_changed, self._on_selection_change,
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
        )
        self.voice_ctrl = VoiceController(
            page, self.voice, self.editor, self.c,
            self.tab_ctrl, self.show_snack, self.rebuild,
        )
        self.kb_ctrl = KeyboardController(
            page, self.c, self.tab_ctrl, self.file_ctrl,
            self.ai_ctrl, self.voice_ctrl,
            self.check_spelling, self._show_emoji_picker,
            self._request_close, self.toggle_toolbar,
            undo=self.undo, redo=self.redo,
        )

        # Connecter auto-save : EditorController → FileController
        self.editor_ctrl._auto_save_callback = self.file_ctrl.auto_save
        self.file_ctrl._st_msg = self.st_msg

        # Raccourcis clavier
        page.on_keyboard_event = self.kb_ctrl.on_keyboard_event

        # Interception de la fermeture de fenêtre
        page.window.prevent_close = True
        page.window.on_event = self._on_window_event

        # Render initial
        self.update_status()
        self.rebuild()

    # ------------------------------------------------------------------
    # Page
    # ------------------------------------------------------------------
    def _configure_page(self):
        p = self.page
        p.title = f"{APP_NAME} — v{APP_VERSION}"
        p.theme_mode = ft.ThemeMode.LIGHT
        p.padding = 0
        p.spacing = 0
        p.window = ft.Window(width=1280, height=820, min_width=800, min_height=550,
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
            "text": "Texte", "calc": "Calcul", "read": "Lecture"
        }.get(self.state.mode, "Texte")
        if d.modified:
            self.st_msg.value = "Modifications non enregistrées"
            self.st_msg.color = self.c(T.L_WARNING, T.D_WARNING)
        elif d.path:
            if not self.st_msg.value or self.st_msg.value == "Modifications non enregistrées":
                self.st_msg.value = ""
            self.st_msg.color = self.c(T.L_TERTIARY, T.D_TERTIARY)
        else:
            self.st_msg.value = ""
            self.st_msg.color = self.c(T.L_TERTIARY, T.D_TERTIARY)

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
        """Demande de fermeture — propose de sauvegarder si nécessaire."""
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
        await self.page.window.destroy()

    def _show_close_dialog(self):
        has_pathless = any(d.modified and not d.path for d in self.state.docs)

        async def save_and_quit(e):
            self.page.pop_dialog()
            await self._save_all_and_quit()

        async def quit_without_save(e):
            self.page.pop_dialog()
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

    def toggle_theme(self):
        self.page.theme_mode = ft.ThemeMode.LIGHT if self.dark() else ft.ThemeMode.DARK
        self.rebuild()

    # ------------------------------------------------------------------
    # Callbacks dicts
    # ------------------------------------------------------------------
    def toggle_sidebar(self):
        self.state.sidebar_collapsed = not self.state.sidebar_collapsed
        self.rebuild()

    def toggle_toolbar(self):
        self.state.show_toolbar = not self.state.show_toolbar
        self.rebuild()

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
            "call_assistant": self.voice_ctrl.call_assistant,
            "run_ai_check": self.ai_ctrl.run_ai_check,
            "check_spelling": self.check_spelling,
            "show_emoji_picker": self._show_emoji_picker,
            "show_voice_menu": self._show_voice_menu,
            "copy_text_handler": self._copy_text_handler,
            "paste_text_handler": self._paste_text_handler,
            "cut_text_handler": self._cut_text_handler,
            "clear_text": self.clear_text,
            "undo": self.undo,
            "redo": self.redo,
        }

    def _ai_panel_callbacks(self):
        return {
            "close_ai": self.ai_ctrl.close_ai,
            "apply_correction": self.ai_ctrl.apply_correction,
        }

    # ------------------------------------------------------------------
    # Full rebuild
    # ------------------------------------------------------------------
    def rebuild(self):
        self.update_status()
        self.editor.hint_style = ft.TextStyle(
            size=16, font_family="Nunito", letter_spacing=0.2,
            color=self.c(T.L_MUTED, T.D_MUTED), italic=True)
        self.editor.text_style = ft.TextStyle(
            size=16, height=1.4, font_family="Nunito", letter_spacing=0.2,
            color=self.c(T.L_PRIMARY, T.D_PRIMARY))
        self.editor.cursor_color = self.c(T.L_ACCENT, T.D_ACCENT)
        self.editor.read_only = (self.state.mode == MODE_READ)
        self.st_mode.color = self.c(T.L_ACCENT, T.D_ACCENT)
        self.st_chars.color = self.c(T.L_TERTIARY, T.D_TERTIARY)
        self.st_words.color = self.c(T.L_TERTIARY, T.D_TERTIARY)

        layout = ft.Row(expand=True, spacing=0, controls=[
            build_sidebar(self.state, self.c, self._sidebar_callbacks()),
            ft.Column(expand=True, spacing=0, controls=[
                build_tab_bar(self.state, self.c, self._tab_bar_callbacks()),
                ft.Container(
                    expand=True, bgcolor=self.c(T.L_EDITOR, T.D_EDITOR),
                    content=ft.Column(expand=True, spacing=0, controls=[
                        c for c in [
                            build_menu_bar(self.c, self._menu_bar_callbacks()) if self.state.show_toolbar else None,
                            ft.Container(expand=True, content=self.editor),
                        ] if c is not None
                    ]),
                ),
                build_status_bar(self.c, self.st_mode, self.st_msg,
                                 self.st_chars, self.st_words),
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
