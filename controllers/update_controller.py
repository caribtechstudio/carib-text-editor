"""
controllers/update_controller.py — Orchestration de la mise à jour.

Sépare nettement les trois responsabilités :

  * `models/updater` connaît GitHub, les empreintes et les signatures, et
    ignore tout de l'interface ;
  * `views/dialogs/update_dialog` dessine, et ne décide rien ;
  * ce contrôleur enchaîne les étapes, et c'est le seul à savoir sur quel
    thread il se trouve.

Règle de threading : tout ce qui touche au réseau part dans un thread
démon ; tout ce qui touche à l'interface repasse par `page.run_thread`.
"""

import logging
import threading
import time

from core.constants import APP_VERSION, RELEASES_URL
from core.theme import T
from models import updater

log = logging.getLogger(__name__)


class UpdateController:
    """Recherche, télécharge et installe les mises à jour."""

    def __init__(self, page, c, services, app):
        self._page = page
        self._c = c
        self._snack = services.show_snack
        self._app = app

        self.prefs = updater.UpdatePrefs.load()
        self._busy = False
        self._cancel = threading.Event()
        self._progress = None

    # ==================================================================
    # Réglages
    # ==================================================================
    @property
    def enabled(self) -> bool:
        return self.prefs.enabled is True

    def set_enabled(self, value: bool) -> None:
        self.prefs.enabled = bool(value)
        self.prefs.save()
        log.info("Recherche de mise a jour : %s",
                 "activee" if value else "desactivee")

    # ==================================================================
    # Démarrage
    # ==================================================================
    def maybe_check_on_startup(self) -> None:
        """Appelé une fois, après le premier rendu.

        Ne déclenche **aucune** connexion tant que l'utilisateur n'a pas
        répondu à la demande d'autorisation.
        """
        if not updater.GITHUB_REPO:
            return

        if self.prefs.enabled is None:
            self._ask_consent()
            return

        if self.prefs.due():
            self._check(manual=False)

    def _ask_consent(self) -> None:
        from views.dialogs.update_dialog import show_update_consent

        def decided(accepted: bool):
            self.set_enabled(accepted)
            if accepted:
                self._check(manual=False)

        show_update_consent(self._page, self._c, decided)

    # ==================================================================
    # Vérification
    # ==================================================================
    def check_now(self) -> None:
        """Recherche déclenchée par l'utilisateur (options, palette)."""
        if not updater.GITHUB_REPO:
            self._snack("Aucun dépôt de mise à jour n'est configuré.",
                        self._c(T.L_WARNING, T.D_WARNING))
            return
        # Une vérification manuelle vaut acceptation, et lève l'oubli
        # éventuel d'une version précédemment ignorée.
        if self.prefs.enabled is None:
            self.set_enabled(True)
        self.prefs.skipped_version = ""
        self.prefs.save()
        self._snack("Recherche de mise à jour…")
        self._check(manual=True)

    def _check(self, *, manual: bool) -> None:
        if self._busy:
            return
        self._busy = True

        def work():
            try:
                info = updater.check(APP_VERSION)
            except updater.UpdateError as exc:
                log.warning("Recherche de mise a jour echouee : %s", exc.detail)
                self._on_ui(lambda: self._check_failed(exc, manual))
                return
            except Exception as exc:                       # filet de sécurité
                log.exception("Erreur inattendue pendant la recherche.")
                self._on_ui(lambda: self._check_failed(
                    updater.UpdateError("Recherche de mise à jour impossible.",
                                        str(exc)), manual))
                return

            # La date n'est mise à jour que sur une vérification réussie :
            # une coupure réseau ne doit pas faire sauter un jour entier.
            self.prefs.last_check = time.time()
            self.prefs.save()
            self._on_ui(lambda: self._check_done(info, manual))

        threading.Thread(target=work, name="carib-update-check",
                         daemon=True).start()

    def _check_failed(self, exc, manual: bool) -> None:
        self._busy = False
        # Un échec silencieux au démarrage est volontaire : ne pas pouvoir
        # joindre GitHub n'est pas un problème que l'utilisateur doit régler.
        if manual:
            self._snack(exc.user_message, self._c(T.L_ERROR, T.D_ERROR))

    def _check_done(self, info, manual: bool) -> None:
        self._busy = False

        if info is None:
            if manual:
                self._snack(f"Carib {APP_VERSION} est à jour.")
            return

        if not manual and info.version == self.prefs.skipped_version:
            log.info("Version %s ignoree par l'utilisateur.", info.version)
            return

        self._offer(info)

    # ==================================================================
    # Proposition
    # ==================================================================
    def _offer(self, info) -> None:
        from views.dialogs.update_dialog import show_update_available

        def skip():
            self.prefs.skipped_version = info.version
            self.prefs.save()
            self._snack(f"La version {info.version} ne sera plus proposée.")

        def later():
            self._snack("Mise à jour reportée. "
                        "Vous la retrouverez dans Options ▸ Mises à jour.")

        show_update_available(
            self._page, self._c, info,
            current_version=APP_VERSION,
            on_now=lambda: self._start_download(info),
            on_later=later,
            on_skip=skip)

    # ==================================================================
    # Téléchargement
    # ==================================================================
    def _start_download(self, info) -> None:
        from views.dialogs.update_dialog import UpdateProgressDialog

        if self._busy:
            return
        self._busy = True
        self._cancel.clear()

        self._progress = UpdateProgressDialog(
            self._page, self._c, on_cancel=self._cancel.set)
        self._progress.show()

        def on_progress(received, total):
            dialog = self._progress
            if dialog is not None:
                self._on_ui(lambda: dialog.progress(received, total))

        def work():
            try:
                path = updater.download(info, on_progress=on_progress,
                                        cancel=self._cancel)
            except updater.UpdateCancelled:
                log.info("Telechargement annule par l'utilisateur.")
                self._on_ui(lambda: self._download_ended(
                    None, "Mise à jour annulée."))
                return
            except updater.UpdateError as exc:
                log.error("Telechargement echoue : %s", exc.detail)
                self._on_ui(lambda: self._download_ended(
                    None, exc.user_message, error=True))
                return
            except Exception as exc:
                log.exception("Erreur inattendue pendant le telechargement.")
                self._on_ui(lambda: self._download_ended(
                    None, f"Le téléchargement a échoué : {exc}", error=True))
                return

            self._on_ui(lambda: self._download_ended(path, ""))

        threading.Thread(target=work, name="carib-update-download",
                         daemon=True).start()

    def _download_ended(self, path, message, *, error=False) -> None:
        self._busy = False
        if self._progress is not None:
            self._progress.close()
            self._progress = None

        if path is None:
            if message:
                self._snack(message,
                            self._c(T.L_ERROR, T.D_ERROR) if error else None)
            return

        self._confirm_install(path)

    # ==================================================================
    # Installation
    # ==================================================================
    def _confirm_install(self, path: str) -> None:
        from views.dialogs.update_dialog import show_ready_to_install

        has_unsaved = any(d.modified for d in self._app.state.docs)

        def install():
            try:
                updater.launch_installer(path)
            except updater.UpdateError as exc:
                self._snack(exc.user_message, self._c(T.L_ERROR, T.D_ERROR))
                return
            # L'installeur ne peut pas remplacer un fichier verrouillé :
            # Carib doit rendre la main immédiatement.
            self._page.run_task(self._app.shutdown_and_destroy)

        def cancel():
            self._snack("L'installeur est prêt dans "
                        f"{updater.download_dir()}.")

        show_ready_to_install(self._page, self._c,
                              has_unsaved=has_unsaved,
                              on_install=install, on_cancel=cancel)

    # ==================================================================
    # Utilitaires
    # ==================================================================
    def open_releases_page(self) -> None:
        self._page.launch_url(RELEASES_URL)

    def _on_ui(self, fn) -> None:
        """Ramène `fn` sur le thread d'interface."""
        try:
            self._page.run_thread(fn)
        except Exception:
            log.exception("Retour sur le thread d'interface impossible.")
