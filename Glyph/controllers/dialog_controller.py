"""
controllers/dialog_controller.py — Toutes les boîtes de dialogue.

Extrait d'`AppController` : emoji, voix, aide, options, aller à la ligne,
récupération après crash, confirmations de fermeture.

Ces méthodes partageaient un même motif — construire un `AlertDialog`,
brancher deux ou trois rappels, appeler `page.show_dialog` — sans jamais
interagir entre elles. Les rassembler libère l'orchestrateur d'environ
trois cents lignes de construction d'interface.
"""

import os

import flet as ft

from constants import UI_FONT_STRONG

from models import recovery
from theme import T


class DialogController:
    """Construit et affiche les boîtes de dialogue de l'application."""

    def __init__(self, page, state, c, tab_ctrl, file_picker, services, app):
        self._page = page
        self.state = state
        self._c = c
        self._tab = tab_ctrl
        self._file_picker = file_picker
        self._svc = services
        self._snack = services.show_snack
        self._rebuild = services.rebuild
        #: Certaines actions (fermeture, récupération) ont besoin de
        #: l'orchestrateur : elles touchent à plusieurs contrôleurs.
        self._app = app

    def _close(self, e=None):
        self._page.pop_dialog()

    # ==================================================================
    # Dialogues simples
    # ==================================================================
    def show_emoji_picker(self):
        from views.dialogs.emoji_picker import show_emoji_picker

        def insert_emoji(ch):
            d = self._tab.cur_doc()
            if not d:
                return
            pos = self._svc.get_cursor()
            d.apply_change(d.content[:pos] + ch + d.content[pos:])
            d.modified = True
            self._app.editor.value = d.content
            self.state.cursor = pos + len(ch)
            self._rebuild()

        show_emoji_picker(self._page, self._c, {"insert_emoji": insert_emoji})

    def show_voice_menu(self):
        from views.dialogs.voice_dialog import show_voice_menu
        voice = self._app.voice_ctrl
        show_voice_menu(self._page, self._c, {
            "read_text": voice.read_text,
            "voice_typing": voice.voice_typing,
            "voice_ms": voice.voice_ms,
        })

    def show_help(self):
        from views.dialogs.help_dialog import show_help
        show_help(self._page, self._c)

    def show_options(self):
        from views.dialogs.info_dialog import show_credits, show_info
        from views.dialogs.options_dialog import show_options
        app = self._app
        show_options(self._page, self._c, app.dark, {
            "set_mode": app.set_mode,
            "toggle_theme": app.toggle_theme,
            "toggle_auto_save": app.toggle_auto_save,
            "is_auto_save": lambda: self.state.auto_save,
            "toggle_autocomplete": app.toggle_autocomplete,
            "is_autocomplete": lambda: self.state.ac_enabled,
            "show_model_manager": app._show_ai_setup,
            "show_help": self.show_help,
            "show_info": lambda: show_info(self._page, self._c),
            "show_credits": lambda: show_credits(self._page, self._c),
        })

    # ==================================================================
    # Aller à la ligne
    # ==================================================================
    def show_goto_line(self):
        d = self._tab.cur_doc()
        if not d:
            return
        total = d.content.count("\n") + 1

        def go(e=None):
            raw = (field.value or "").strip()
            self._close()
            if raw.isdigit():
                self._app.goto_line(max(1, min(int(raw), total)))

        field = ft.TextField(
            hint_text=f"Numéro de ligne (1 – {total})", autofocus=True,
            text_size=13, border_radius=6,
            border_color=self._c(T.L_BORDER, T.D_BORDER), on_submit=go)

        self._page.show_dialog(ft.AlertDialog(
            title=ft.Text("Aller à la ligne", size=16,
                          font_family=UI_FONT_STRONG, weight=ft.FontWeight.W_700),
            content=ft.Container(width=300, content=field),
            actions=[
                ft.TextButton("Annuler", on_click=self._close),
                ft.Button("Aller", bgcolor=self._c(T.L_ACCENT, T.D_ACCENT),
                          color="#FFFFFF", on_click=go),
            ],
            actions_alignment=ft.MainAxisAlignment.END))

    # ==================================================================
    # Récupération après arrêt anormal
    # ==================================================================
    def show_recovery(self, documents=None):
        documents = documents or recovery.load()
        if not documents:
            self._snack("Aucun document à récupérer.")
            return

        age = recovery.age_label()
        listing = "\n".join(
            f"  • {d.get('title') or 'Sans titre'} "
            f"({len(d.get('content', ''))} caractères)" for d in documents[:8])
        if len(documents) > 8:
            listing += f"\n  … et {len(documents) - 8} autre(s)"

        def restore(e):
            self._close()
            self._app.restore_recovered(documents)

        def discard(e):
            self._close()
            recovery.clear()
            self._app._pending_recovery = []
            self._snack("Documents récupérables supprimés.")

        self._page.show_dialog(ft.AlertDialog(
            modal=True,
            title=ft.Text("Récupération après interruption", size=16,
                          font_family=UI_FONT_STRONG, weight=ft.FontWeight.W_700),
            content=ft.Container(width=460, content=ft.Text(
                f"Glyph s'est arrêté sans enregistrer{' — ' + age if age else ''}.\n"
                f"Les documents suivants ont été retrouvés :\n\n{listing}\n\n"
                "Ils seront rouverts dans de nouveaux onglets ; à vous de les "
                "enregistrer où vous le souhaitez.",
                size=13, color=self._c(T.L_SECONDARY, T.D_SECONDARY))),
            actions=[
                ft.TextButton("Ignorer", on_click=self._close),
                ft.TextButton("Supprimer définitivement", on_click=discard),
                ft.Button("Récupérer", bgcolor=self._c(T.L_ACCENT, T.D_ACCENT),
                          color="#FFFFFF", on_click=restore),
            ],
            actions_alignment=ft.MainAxisAlignment.END))

    # ==================================================================
    # Fermeture
    # ==================================================================
    def confirm_quit(self):
        """Documents modifiés au moment de quitter."""
        modified = [d for d in self.state.docs if d.modified]
        detail = "\n".join(f"  • {d.title or 'Sans titre'}"
                           f"{' (nouveau)' if not d.path else ''}" for d in modified)
        note = ("\n\nLes documents marqués (nouveau) demanderont un emplacement."
                if any(not d.path for d in modified) else "")

        async def save_and_quit(e):
            self._close()
            await self._app.save_all_and_quit()

        async def quit_anyway(e):
            self._close()
            await self._app.shutdown_and_destroy()

        self._page.show_dialog(ft.AlertDialog(
            modal=True,
            title=ft.Text("Modifications non enregistrées", size=16,
                          font_family=UI_FONT_STRONG, weight=ft.FontWeight.W_700),
            content=ft.Text(f"Les documents suivants ont été modifiés :\n{detail}{note}",
                            size=14, color=self._c(T.L_SECONDARY, T.D_SECONDARY)),
            actions=[
                ft.TextButton("Annuler", on_click=self._close),
                ft.TextButton("Quitter sans enregistrer", on_click=quit_anyway),
                ft.Button("Enregistrer et quitter",
                          bgcolor=self._c(T.L_ACCENT, T.D_ACCENT),
                          color="#FFFFFF", on_click=save_and_quit),
            ],
            actions_alignment=ft.MainAxisAlignment.END))

    def confirm_close_tab(self, idx: int):
        docs = self.state.docs
        if not (0 <= idx < len(docs)):
            return
        d = docs[idx]
        if not d.modified:
            self._tab.close_tab(idx)
            return

        from models.file_manager import write_file

        async def save_and_close(e):
            self._close()
            self._tab.save_content()
            if not d.path:
                path = await self._file_picker.save_file(
                    dialog_title=f"Enregistrer « {d.title or 'Sans titre'} »",
                    file_name=d.title if "." in d.title else d.title + ".txt")
                if not path:
                    return
                if "." not in os.path.basename(path):
                    path += ".txt"
                d.path = path
                d.title = os.path.basename(path)
            try:
                mtime, size = write_file(d.path, d.content,
                                         encoding=d.encoding, newline=d.newline)
                d.mark_saved(mtime, size)
            except OSError as exc:
                self._snack(f"Échec : {exc}", self._c(T.L_ERROR, T.D_ERROR))
                return
            self._tab.close_tab(idx)

        def close_without_save(e):
            self._close()
            d.modified = False
            self._tab.close_tab(idx)

        hint = "" if d.path else " Ce document n'a jamais été enregistré."
        self._page.show_dialog(ft.AlertDialog(
            modal=True,
            title=ft.Text("Fermer l'onglet", size=16, font_family=UI_FONT_STRONG,
                          weight=ft.FontWeight.W_700),
            content=ft.Text(f"« {d.title or 'Sans titre'} » a été modifié.{hint}",
                            size=14, color=self._c(T.L_SECONDARY, T.D_SECONDARY)),
            actions=[
                ft.TextButton("Annuler", on_click=self._close),
                ft.TextButton("Fermer sans enregistrer", on_click=close_without_save),
                ft.Button("Enregistrer", bgcolor=self._c(T.L_ACCENT, T.D_ACCENT),
                          color="#FFFFFF", on_click=save_and_close),
            ],
            actions_alignment=ft.MainAxisAlignment.END))
