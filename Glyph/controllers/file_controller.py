"""
controllers/file_controller.py — Opérations fichier (ouvrir, sauver, renommer, imprimer).
"""

import os
from datetime import datetime

from theme import T
from models.file_manager import read_file, write_file, rename_file_on_disk
from models.print_manager import print_document, WIN32_PRINT
from views.dialogs.rename_dialog import show_rename_dialog


class FileController:
    """Orchestre les opérations de fichiers."""

    def __init__(self, page, state, editor, c, file_picker,
                 tab_ctrl, show_snack, rebuild_fn):
        self._page = page
        self.state = state
        self.editor = editor
        self._c = c
        self._file_picker = file_picker
        self._tab = tab_ctrl
        self._snack = show_snack
        self._rebuild = rebuild_fn
        self._st_msg = None          # sera défini par AppController
        self._save_session = None    # sera défini par AppController
        self._refresh_tab_bar = None # sera défini par AppController

    async def open_file(self, e=None):
        result = await self._file_picker.pick_files(
            dialog_title="Ouvrir un fichier",
            allowed_extensions=["txt"],
            allow_multiple=False,
        )
        if not result:
            return
        fp = result[0].path
        content = read_file(fp)
        if content is None:
            self._snack("Impossible de lire le fichier.",
                         self._c(T.L_ERROR, T.D_ERROR))
            return
        self._tab.save_content()
        self._tab.add_tab(title=os.path.basename(fp), content=content, path=fp)
        if self._save_session:
            self._save_session()

    async def save_file(self, e=None):
        d = self._tab.cur_doc()
        if not d:
            return
        self._tab.save_content()
        if d.path:
            self._do_save(d)
        else:
            await self.save_file_as()

    async def save_file_as(self, e=None):
        d = self._tab.cur_doc()
        if not d:
            return
        self._tab.save_content()
        path = await self._file_picker.save_file(
            dialog_title="Enregistrer le fichier",
            file_name=(d.title + ".txt"),
            allowed_extensions=["txt"],
        )
        if not path:
            return
        d.path = path
        d.title = os.path.basename(path)
        self._do_save(d)

    def _do_save(self, d):
        try:
            write_file(d.path, d.content)
            d.modified = False
            if self._st_msg:
                self._st_msg.value = datetime.now().strftime("Enregistré à %Hh%M")
            self._snack(
                datetime.now().strftime("Enregistré le %d/%m/%Y à %Hh%M"),
                self._c(T.L_SUCCESS, T.D_SUCCESS),
            )
            self._rebuild()
            if self._save_session:
                self._save_session()
        except OSError as exc:
            self._snack(f"Erreur : {exc}", self._c(T.L_ERROR, T.D_ERROR))

    def auto_save(self):
        """Sauvegarde automatique silencieuse — feedback dans la barre de statut.

        - Documents avec chemin : sauvegarde sur disque.
        - Documents sans chemin : sauvegarde uniquement la session (contenu temporaire).
        """
        d = self._tab.cur_doc()
        if not d or not d.modified:
            return

        self._tab.save_content()

        if d.path:
            # Sauvegarde classique sur disque
            try:
                write_file(d.path, d.content)
                d.modified = False
                if self._st_msg:
                    self._st_msg.value = datetime.now().strftime("Enregistré à %Hh%M")
                    self._st_msg.color = self._c(T.L_ACCENT, T.D_ACCENT)
                if self._refresh_tab_bar:
                    self._refresh_tab_bar()
                self._page.update()
            except OSError:
                if self._st_msg:
                    self._st_msg.value = "Échec de la sauvegarde auto"
                    self._page.update()

        # Toujours sauvegarder la session (même pour les docs sans chemin)
        if self._save_session:
            self._save_session()

    def has_unsaved_docs(self):
        """Vérifie si au moins un document a été modifié."""
        return any(d.modified for d in self.state.docs)

    def rename_current_file(self, e=None):
        d = self._tab.cur_doc()
        if not d:
            return

        def do_rename(new_name):
            old_path = d.path
            d.title = new_name
            if old_path:
                try:
                    d.path = rename_file_on_disk(old_path, new_name)
                    self._snack(f"Renommé en {new_name}",
                                 self._c(T.L_SUCCESS, T.D_SUCCESS))
                except OSError as exc:
                    self._snack(f"Erreur : {exc}",
                                 self._c(T.L_ERROR, T.D_ERROR))
            else:
                self._snack(f"Renommé en {new_name}",
                             self._c(T.L_SUCCESS, T.D_SUCCESS))
            self._rebuild()

        def do_rename_and_save_session(new_name):
            do_rename(new_name)
            if self._save_session:
                self._save_session()

        show_rename_dialog(self._page, self._c, d, {"do_rename": do_rename_and_save_session})

    def print_file(self, e=None):
        self._tab.save_content()
        d = self._tab.cur_doc()
        if not d:
            return
        text = d.content
        if not text.strip():
            self._snack("Rien à imprimer.", self._c(T.L_WARNING, T.D_WARNING))
            return
        if not WIN32_PRINT:
            self._snack("pip install pywin32 requis pour imprimer.",
                         self._c(T.L_WARNING, T.D_WARNING))
            return
        page = self._page
        c = self._c
        snack = self._snack
        print_document(
            d.title or "Sans titre",
            text,
            on_success=lambda: page.run_thread(
                lambda: snack("Impression terminée.", c(T.L_SUCCESS, T.D_SUCCESS))
            ),
            on_error=lambda msg: page.run_thread(
                lambda: snack(f"Erreur : {msg}", c(T.L_ERROR, T.D_ERROR))
            ),
        )
