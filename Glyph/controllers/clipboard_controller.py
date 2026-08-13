"""
controllers/clipboard_controller.py — Copier, couper, coller, effacer.

Extrait d'`AppController`, qui portait 1 283 lignes et une douzaine de
responsabilités distinctes.

Toutes les opérations passent par `Document.apply_change`, ce qui les rend
annulables en une seule étape — auparavant un collage pouvait se retrouver
fusionné avec la frappe qui le précédait.
"""

import flet as ft

from constants import UI_FONT_STRONG

from theme import T


class ClipboardController:
    """Opérations de presse-papier sur le document courant."""

    def __init__(self, page, clipboard, editor, tab_ctrl, editor_ctrl,
                 get_selection_fn, get_cursor_fn, c, show_snack, rebuild_fn,
                 update_status_fn):
        self._page = page
        self._clipboard = clipboard
        self._editor = editor
        self._tab = tab_ctrl
        self._editor_ctrl = editor_ctrl
        self._get_selection = get_selection_fn
        self._get_cursor = get_cursor_fn
        self._c = c
        self._snack = show_snack
        self._rebuild = rebuild_fn
        self._update_status = update_status_fn

    # ------------------------------------------------------------------
    # Lecture
    # ------------------------------------------------------------------
    async def copy(self):
        self._tab.save_content()
        d = self._tab.cur_doc()
        if not d or not d.content.strip():
            self._snack("Rien à copier.")
            return

        sel = self._get_selection()
        if sel:
            await self._clipboard.set(d.content[sel[0]:sel[1]])
            self._snack("Sélection copiée.")
        else:
            await self._clipboard.set(d.content)
            self._snack("Document copié.")

    # ------------------------------------------------------------------
    # Écriture
    # ------------------------------------------------------------------
    async def paste(self):
        clip = await self._clipboard.get()
        if not clip:
            self._snack("Presse-papier vide.")
            return

        self._tab.save_content()
        self._editor_ctrl.force_snapshot()
        d = self._tab.cur_doc()
        if not d:
            return

        sel = self._get_selection()
        if sel:
            new_text = d.content[:sel[0]] + clip + d.content[sel[1]:]
            cursor = sel[0] + len(clip)
        else:
            pos = min(self._get_cursor(), len(d.content))
            new_text = d.content[:pos] + clip + d.content[pos:]
            cursor = pos + len(clip)

        self._commit(d, new_text, cursor)
        self._snack("Texte collé.")

    async def cut(self):
        self._tab.save_content()
        self._editor_ctrl.force_snapshot()
        d = self._tab.cur_doc()
        if not d or not d.content.strip():
            self._snack("Rien à couper.")
            return

        sel = self._get_selection()
        if sel:
            await self._clipboard.set(d.content[sel[0]:sel[1]])
            new_text = d.content[:sel[0]] + d.content[sel[1]:]
            cursor = sel[0]
            self._snack("Sélection coupée.")
        else:
            await self._clipboard.set(d.content)
            new_text, cursor = "", 0
            self._snack("Document coupé.")

        self._commit(d, new_text, cursor)

    def _commit(self, d, new_text: str, cursor: int):
        """Applique une modification en une étape annulable et recale le curseur."""
        d.apply_change(new_text)
        d.modified = True
        self._editor.value = d.content
        try:
            self._editor.selection = ft.TextSelection(
                base_offset=cursor, extent_offset=cursor)
        except (AttributeError, TypeError):
            pass
        self._editor_ctrl.reset_snapshot_tracking()
        self._update_status()
        self._rebuild()

    # ------------------------------------------------------------------
    # Effacement
    # ------------------------------------------------------------------
    def clear(self):
        """Efface tout le document, après confirmation."""
        self._tab.save_content()
        d = self._tab.cur_doc()
        if not d or not d.content.strip():
            self._snack("L'éditeur est déjà vide.")
            return

        # On capture l'onglet visé : l'utilisateur peut changer d'onglet
        # pendant que la confirmation est affichée.
        target_idx = self._tab.state.idx
        target_doc = d
        title = d.title or "Sans titre"
        c = self._c

        def confirm(e):
            self._page.pop_dialog()
            docs = self._tab.state.docs
            if target_idx >= len(docs) or docs[target_idx] is not target_doc:
                self._snack("L'onglet a été fermé entre-temps.",
                            c(T.L_WARNING, T.D_WARNING))
                return
            target_doc.apply_change("")
            target_doc.modified = True
            if self._tab.state.idx == target_idx:
                self._editor.value = ""
            self._update_status()
            self._rebuild()
            self._snack("Contenu effacé — Ctrl+Z pour annuler.",
                        c(T.L_WARNING, T.D_WARNING))

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Effacer le contenu", size=16,
                          font_family=UI_FONT_STRONG, weight=ft.FontWeight.W_700),
            content=ft.Text(
                f"Tout le texte de « {title} » sera supprimé.\n"
                "L'action reste annulable avec Ctrl+Z.",
                size=14, color=c(T.L_SECONDARY, T.D_SECONDARY)),
            actions=[
                ft.TextButton("Annuler", on_click=lambda e: self._page.pop_dialog()),
                ft.Button("Effacer", bgcolor=c(T.L_ERROR, T.D_ERROR),
                          color="#FFFFFF", on_click=confirm),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self._page.show_dialog(dlg)
