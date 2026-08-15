"""
controllers/file_controller.py — Ouvrir, enregistrer, renommer, imprimer.

L'enregistrement respecte désormais l'encodage et les fins de ligne
d'origine du fichier, et vérifie qu'il n'a pas été modifié en dehors de
Carib avant de l'écraser.
"""

import os
from datetime import datetime

from models.file_manager import (BinaryFileError, FileTooLargeError, load_file,
                                 rename_file_on_disk, write_file)
from core.theme import T
from views.dialogs.rename_dialog import show_rename_dialog
from views.dialogs._common import modern_dialog, primary_button, secondary_button

#: Extensions proposées à l'ouverture. Carib n'était limité qu'au .txt, ce qui
#: le rendait inutilisable pour des notes Markdown, des journaux ou du JSON.
TEXT_EXTENSIONS = [
    "txt", "md", "markdown", "log", "csv", "tsv", "json", "yaml", "yml",
    "ini", "cfg", "conf", "xml", "html", "css", "js", "ts", "py", "sql",
    "sh", "bat", "env", "toml", "rst", "tex",
]


class FileController:
    """Orchestre les opérations de fichiers."""

    def __init__(self, page, state, editor, c, file_picker, tab_ctrl, services):
        self._page = page
        self.state = state
        self.editor = editor
        self._c = c
        self._file_picker = file_picker
        self._tab = tab_ctrl
        # Toutes les dépendances applicatives arrivent ici, d'un bloc :
        # plus aucun champ à renseigner après construction.
        self._svc = services
        self._snack = services.show_snack
        self._rebuild = services.rebuild

    # ------------------------------------------------------------------
    # Ouverture
    # ------------------------------------------------------------------
    async def open_file(self, e=None):
        result = await self._file_picker.pick_files(
            dialog_title="Ouvrir un fichier",
            allowed_extensions=TEXT_EXTENSIONS,
            allow_multiple=True,
        )
        if not result:
            return

        self._tab.save_content()
        opened = 0
        for picked in result:
            if self._open_one(picked.path):
                opened += 1

        if opened:
            self._svc.save_session()

    def _open_one(self, path: str) -> bool:
        """Ouvre un fichier dans un nouvel onglet. Retourne True si réussi."""
        loaded = self._load_or_report(path)
        if loaded is None:
            return False

        self._svc.push_recent(path)

        self._tab.add_tab_from_file(os.path.basename(path), loaded, path)
        if not loaded.confident:
            self._snack(
                f"Encodage de « {os.path.basename(path)} » incertain "
                f"({loaded.encoding}). Vérifiez les accents avant d'enregistrer.",
                self._c(T.L_WARNING, T.D_WARNING),
            )
        return True

    def _load_or_report(self, path: str):
        """Charge un fichier, en expliquant clairement tout échec."""
        try:
            return load_file(path)
        except FileTooLargeError as exc:
            self._snack(str(exc), self._c(T.L_WARNING, T.D_WARNING))
        except BinaryFileError:
            self._snack(f"« {os.path.basename(path)} » n'est pas un fichier texte.",
                        self._c(T.L_WARNING, T.D_WARNING))
        except OSError as exc:
            self._snack(f"Impossible de lire le fichier : {exc}",
                        self._c(T.L_ERROR, T.D_ERROR))
        return None

    # ------------------------------------------------------------------
    # Enregistrement
    # ------------------------------------------------------------------
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

        suggested = d.title if "." in d.title else f"{d.title}.txt"
        path = await self._file_picker.save_file(
            dialog_title="Enregistrer le fichier",
            file_name=suggested,
            allowed_extensions=TEXT_EXTENSIONS,
        )
        if not path:
            return
        if "." not in os.path.basename(path):
            path += ".txt"

        d.path = path
        d.title = os.path.basename(path)
        self._do_save(d, skip_conflict_check=True)

    def _do_save(self, d, skip_conflict_check: bool = False):
        """Écrit le document, après contrôle de modification externe."""
        if not skip_conflict_check and self._has_external_change(d):
            self._confirm_overwrite(d)
            return
        self._write(d)

    def _write(self, d, announce: bool = True):
        try:
            mtime, size = write_file(d.path, d.content,
                                     encoding=d.encoding, newline=d.newline)
        except OSError as exc:
            self._snack(f"Échec de l'enregistrement : {exc}",
                        self._c(T.L_ERROR, T.D_ERROR))
            return False

        d.mark_saved(mtime, size)
        self._svc.push_recent(d.path)
        self._svc.set_status_message(datetime.now().strftime("Enregistré à %Hh%M"))
        if announce:
            self._snack(datetime.now().strftime("Enregistré le %d/%m/%Y à %Hh%M"),
                        self._c(T.L_SUCCESS, T.D_SUCCESS))
        self._rebuild()
        self._svc.save_session()
        return True

    @staticmethod
    def _has_external_change(d) -> bool:
        from models.file_manager import file_changed_on_disk
        return bool(d.path) and file_changed_on_disk(d.path, d.mtime, d.size)

    def _confirm_overwrite(self, d):
        """Le fichier a changé sur le disque : ne jamais écraser en silence."""
        import flet as ft
        c = self._c

        def overwrite(e):
            self._page.pop_dialog()
            self._write(d)

        def reload_from_disk(e):
            self._page.pop_dialog()
            loaded = self._load_or_report(d.path)
            if loaded is None:
                return
            d.content = loaded.text
            d.encoding, d.newline = loaded.encoding, loaded.newline
            d.mark_saved(loaded.mtime, loaded.size)
            self.editor.value = d.content
            self._rebuild()
            self._snack("Fichier rechargé depuis le disque.")

        content = ft.Container(width=470, content=ft.Text(
                f"« {d.title} » a été modifié par un autre programme depuis "
                "son ouverture.\n\nÉcraser remplacera ces changements par "
                "votre version. Recharger abandonnera vos modifications.",
                size=14, color=c(T.L_SECONDARY, T.D_SECONDARY)))
        dlg = modern_dialog(
            self._page, c, "Le fichier a changé sur le disque", content,
            subtitle="Choisissez la version à conserver", modal=True,
            actions=[
                secondary_button("Annuler", c, lambda e: self._page.pop_dialog()),
                ft.TextButton("Recharger du disque", on_click=reload_from_disk),
                primary_button("Écraser", c, overwrite, "disk"),
            ],
        )
        self._page.show_dialog(dlg)

    def auto_save(self):
        """Sauvegarde silencieuse. Ne déclenche jamais de dialogue bloquant.

        Volontairement **sans** `save_content()` : cette méthode s'exécute sur
        un thread de travail, et recopier `editor.value` dans le document
        actif depuis là pouvait écrire le texte de l'onglet quitté par-dessus
        celui de l'onglet courant si l'utilisateur changeait d'onglet au même
        instant. Le document est déjà à jour — `on_text_changed` l'écrit à
        chaque frappe, sur le thread d'interface.
        """
        d = self._tab.cur_doc()
        if not d or not d.modified:
            return

        if d.path:
            # En cas de conflit externe on s'abstient : l'auto-save ne doit
            # jamais écraser le travail d'un autre programme sans arbitrage.
            if self._has_external_change(d):
                self._svc.set_status_message(
                    "Auto-save suspendue — fichier modifié ailleurs")
                self._page.update()
            else:
                try:
                    mtime, size = write_file(d.path, d.content,
                                             encoding=d.encoding, newline=d.newline)
                    d.mark_saved(mtime, size)
                    self._svc.set_status_message(
                        datetime.now().strftime("Enregistré à %Hh%M"),
                        self._c(T.L_ACCENT, T.D_ACCENT))
                    self._svc.refresh_tab_bar()
                    self._page.update()
                except OSError:
                    self._svc.set_status_message("Échec de la sauvegarde auto")
                    self._page.update()

        self._svc.save_session()

    def has_unsaved_docs(self) -> bool:
        return any(d.modified for d in self.state.docs)

    # ------------------------------------------------------------------
    # Renommage et impression
    # ------------------------------------------------------------------
    def rename_current_file(self, e=None):
        d = self._tab.cur_doc()
        if not d:
            return

        def do_rename(new_name):
            new_name = (new_name or "").strip()
            if not new_name:
                return
            if d.path:
                try:
                    d.path = rename_file_on_disk(d.path, new_name)
                    d.title = os.path.basename(d.path)
                    self._snack(f"Renommé en {d.title}",
                                self._c(T.L_SUCCESS, T.D_SUCCESS))
                except OSError as exc:
                    self._snack(str(exc), self._c(T.L_ERROR, T.D_ERROR))
                    return
            else:
                d.title = new_name
                self._snack(f"Renommé en {new_name}",
                            self._c(T.L_SUCCESS, T.D_SUCCESS))
            self._rebuild()
            self._svc.save_session()

        show_rename_dialog(self._page, self._c, d, {"do_rename": do_rename})

    def print_file(self, e=None):
        self._tab.save_content()
        d = self._tab.cur_doc()
        if not d:
            return
        if not d.content.strip():
            self._snack("Rien à imprimer.", self._c(T.L_WARNING, T.D_WARNING))
            return

        # Import différé : le module d'impression tire `webbrowser` et
        # `tempfile`, inutiles au démarrage.
        from models.print_manager import print_document

        page, c, snack = self._page, self._c, self._snack
        print_document(
            d.title or "Sans titre", d.content,
            on_success=lambda: page.run_thread(
                lambda: snack("Aperçu d'impression ouvert.",
                              c(T.L_SUCCESS, T.D_SUCCESS))),
            on_error=lambda msg: page.run_thread(
                lambda: snack(f"Erreur : {msg}", c(T.L_ERROR, T.D_ERROR))),
        )
