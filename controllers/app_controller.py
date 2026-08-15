"""
controllers/app_controller.py — Orchestrateur : relie modèles, vues et contrôleurs.

Le presse-papier (`clipboard_controller`), l'expérience IA
(`ai_ux_controller`) et le catalogue de commandes (`command_registry`) ont
été extraits d'ici. Il reste le câblage des contrôleurs, la mise en page et
les réglages d'affichage — encore volumineux, mais d'une seule nature.

Le découpage n'est pas terminé : zoom, session et gestion des dialogues
mériteraient le même traitement.

Démarrage en deux temps
-----------------------
La coquille de l'application (fenêtre, éditeur vide, barre latérale) est
peinte **immédiatement**, puis la restauration de session, le serveur IPC et
le dictionnaire orthographique sont lancés une fois la première image
affichée. L'utilisateur voit Carib en quelques centaines de millisecondes au
lieu d'attendre la relecture de tous ses onglets sur le disque.
"""

import os
import threading

import flet as ft

from core.constants import (APP_FULL_NAME, APP_NAME, APP_VERSION, EDITOR_FONT, ICON_XS, MODE_READ,
                       TOOLBAR_HEIGHT, UI_FONT, UI_FONT_STRONG, MOTION_NORMAL,
                       MOTION_PANEL, resource_path,
                       svg_icon)
from models.document import Document
from models.editor_state import EditorState
from models import recovery, startup_probe
from models.scheduler import scheduler
from models.llm.manager import LLMManager
from models.llm.registry import is_local
from models.spell_checker import SpellCheckerWrapper
from models.syntax import detect_language, highlight, language_label
from models.text_utils import count_words, line_col_at_cursor
from models.voice_manager import VoiceManager
from core.phrase_random import PhrasePlaceHolder
from core.theme import T

from views.ai_panel import build_ai_panel
from views.command_bar import build_command_bar
from views.command_palette import build_command_palette
from views.diff_view import build_diff_actions, build_diff_spans, diff_stats
from views.editor_area import create_editor
from views.ghost_text import build_ghost_hint, build_ghost_spans
from views.menu_bar import build_menu_bar
from views.search_bar import build_highlight_spans, build_search_bar
from views.sidebar import build_sidebar
from views.status_bar import build_ai_badge, build_status_bar
from views.syntax_view import build_line_gutter, build_syntax_spans
from views.tab_bar import build_tab_bar

from controllers.ai_controller import AIController
from controllers.notifier import Notifier
from controllers.app_services import AppServices
from controllers.ai_ux_controller import AIUXController
from controllers.autocomplete_controller import AutocompleteController
from controllers.clipboard_controller import ClipboardController
from controllers.dialog_controller import DialogController
from controllers.dialog_guard import install_dialog_guard
from controllers.editor_controller import EditorController
from controllers.file_controller import FileController
from controllers.keyboard_controller import KeyboardController
from controllers.search_controller import SearchController
from controllers.session_controller import SessionController
from controllers.tab_controller import TabController
from controllers.update_controller import UpdateController
from controllers.view_controller import ViewController
from controllers.voice_controller import VoiceController

#: Délai avant de recompter les mots. Compter à chaque frappe impose un
#: parcours complet du document — imperceptible sur 10 lignes, ruineux sur
#: 50 000 caractères.
_WORD_COUNT_DELAY = 0.35

#: Cles d'ordonnancement propres a ce controleur.
_WORD_COUNT_TASK = "app.word_count"


class AppController:
    """Point central de l'application."""

    def __init__(self, page: ft.Page, startup_paths=None):
        self.page = page
        self._startup_paths = list(startup_paths or [])
        self._configure_page()
        #: Les notifications passent toutes par là : une seule vivante à la
        #: fois, et jamais laissée derrière soi dans la pile de dialogues.
        self._notifier = Notifier(page, self.c)
        self._exiting = False

        # ---------------- Modèles ----------------
        self.state = EditorState()
        self.session_ctrl = SessionController(
            page, self.state,
            get_editor_value=lambda: self.editor.value if self.editor else None,
            is_dark=self.dark)
        self.session_ctrl.apply_settings()
        if not self.state.docs:
            self.state.docs.append(Document())

        self.spell = SpellCheckerWrapper(
            resource_path("ressource/spellchecker/fr.json.gz"))
        self.voice = VoiceManager()
        self.ph = PhrasePlaceHolder()
        self.llm = LLMManager()
        #: Documents récupérables détectés au démarrage — lus **avant** que
        #: le journal ne se remette à écrire, sinon on les effacerait.
        self._pending_recovery = recovery.load()
        self._recovery = recovery.RecoveryJournal(lambda: self.state.docs)

        # ---------------- Services Flet ----------------
        self.file_picker = ft.FilePicker()
        self.clipboard = ft.Clipboard()
        page.services.append(self.file_picker)
        page.services.append(self.clipboard)

        # ---------------- Widgets de statut ----------------
        self._build_status_widgets()

        # ---------------- Éditeur ----------------
        self.editor = create_editor(
            self.c, self.ph.get_random_phrase(),
            self._on_text_changed, self._on_selection_change,
        )

        self._build_persistent_containers()

        self._tray = None

        self._build_controllers()
        self._wire_controllers()

        page.on_keyboard_event = self._on_keyboard
        page.window.prevent_close = True
        page.window.on_event = self._on_window_event

        self._update_recent_list()
        self.update_status()
        self.rebuild()

        # Tout ce qui touche au disque ou au réseau attend la première image.
        page.run_task(self._deferred_start)

    # ==================================================================
    # Démarrage
    # ==================================================================
    def _configure_page(self):
        p = self.page
        p.title = f"{APP_FULL_NAME} — v{APP_VERSION}"
        if p.theme_mode != ft.ThemeMode.DARK:
            p.theme_mode = ft.ThemeMode.LIGHT
        p.padding = 0
        p.spacing = 0
        p.window = ft.Window(width=1280, height=820, min_width=1100, min_height=700,
                             icon=resource_path("ressource/icon/icon.ico"))
        p.fonts = {
            # Les clés sont les noms de famille utilisés partout ailleurs :
            # elles viennent de `constants` pour qu'un renommage ne puisse pas
            # laisser une vue réclamer une fonte non enregistrée.
            EDITOR_FONT: "Font/Nunito/static/Nunito-Regular.ttf",
            UI_FONT: "Font/Nunito/static/Nunito-SemiBold.ttf",
            UI_FONT_STRONG: "Font/Nunito/static/Nunito-Bold.ttf",
        }
        dialog_shape = ft.RoundedRectangleBorder(radius=18)
        p.theme = ft.Theme(
            font_family=UI_FONT,
            use_material3=True,
            scaffold_bgcolor=T.L_BG,
            hover_color=T.L_HOVER,
            focus_color=ft.Colors.with_opacity(0.14, T.L_ACCENT),
            dialog_theme=ft.DialogTheme(
                bgcolor=T.L_SURFACE, elevation=18, shape=dialog_shape,
                shadow_color=ft.Colors.with_opacity(0.24, ft.Colors.BLACK),
                barrier_color=ft.Colors.with_opacity(0.38, "#17171D"),
                actions_padding=ft.Padding(20, 12, 20, 16),
            ),
        )
        p.dark_theme = ft.Theme(
            font_family=UI_FONT,
            use_material3=True,
            scaffold_bgcolor=T.D_BG,
            hover_color=T.D_HOVER,
            focus_color=ft.Colors.with_opacity(0.18, T.D_ACCENT),
            dialog_theme=ft.DialogTheme(
                bgcolor=T.D_SURFACE, elevation=22, shape=dialog_shape,
                shadow_color=ft.Colors.with_opacity(0.55, ft.Colors.BLACK),
                barrier_color=ft.Colors.with_opacity(0.62, ft.Colors.BLACK),
                actions_padding=ft.Padding(20, 12, 20, 16),
            ),
        )
        p.bgcolor = T.L_BG
        #: Un clic répété sur un bouton de menu ne doit pas empiler dix
        #: copies du même dialogue.
        install_dialog_guard(p)

    async def _deferred_start(self):
        """Travaux différés, exécutés après le premier rendu."""
        # Le journal existe déjà (installé dans carib.py) ; on lui rattache
        # maintenant la boucle asyncio de Flet et le dialogue d'erreur, qui
        # ont tous deux besoin de la page.
        import asyncio

        from core import logging_setup
        logging_setup.set_ui_reporter(self._report_crash)
        try:
            logging_setup.install_asyncio_handler(asyncio.get_running_loop())
        except RuntimeError:
            pass

        restored = self._apply_session_tabs()
        self.session_ctrl.release()

        if self._startup_paths:
            # open_paths reconstruit déjà l'interface s'il ouvre quelque chose.
            restored = self.open_paths(self._startup_paths) or restored

        from models.ipc_server import start_ipc_server
        start_ipc_server(self._on_ipc_paths_received)

        # Le dictionnaire se charge en tâche de fond : F6 n'attendra pas.
        self.spell.preload()

        if self.state.stay_resident:
            self._start_tray()

        # Journal de récupération : borne la perte à 15 s en cas de crash.
        self._recovery.start()

        # Reconstruire l'arbre complet ne sert que si le contenu a changé.
        # Sans cette condition, chaque lancement payait deux fois la
        # construction de l'interface — environ 1,5 s de trop.
        if restored:
            self.update_status()
            self.rebuild()

        # La restauration a pu émettre plusieurs notifications d'affilée :
        # on repart d'une pile de dialogues propre avant de proposer, le cas
        # échéant, la récupération.
        self._notifier.prune()

        # Une session précédente s'est-elle terminée anormalement ?
        self._offer_recovery_if_needed()

        # Mise à jour en dernier : la proposition ne doit jamais passer
        # devant une récupération de documents.
        self.update_ctrl.maybe_check_on_startup()

    # ------------------------------------------------------------------
    # Rapport d'erreur
    # ------------------------------------------------------------------
    def _report_crash(self, title: str, message: str, log_file: str):
        """Affiche une erreur inattendue — appelé depuis n'importe quel thread.

        Une seule fenêtre par session : `logging_setup` s'en assure. Le but
        n'est pas d'excuser le défaut, mais de donner à l'utilisateur de quoi
        le signaler utilement.
        """
        def show():
            from views.dialogs.error_dialog import show_crash_report
            try:
                show_crash_report(self.page, self.c, title, message, log_file,
                                  clipboard=self.clipboard)
            except Exception:
                # Si même le dialogue échoue, le journal reste la trace.
                pass

        try:
            self.page.run_thread(show)
        except Exception:
            pass

    # ==================================================================
    # Construction
    # ==================================================================
    def _build_status_widgets(self):
        muted = self.c(T.L_TERTIARY, T.D_TERTIARY)
        self.st_mode = ft.Text("Mode Texte", size=11.5,
                               color=self.c(T.L_ACCENT, T.D_ACCENT),
                               font_family=UI_FONT_STRONG,
                               weight=ft.FontWeight.W_600)
        self.st_msg = ft.Text("", size=11.5, color=muted, expand=True)
        self.st_chars = ft.Text("0 car.", size=11.5, color=muted)
        self.st_words = ft.Text("0 mots", size=11.5, color=muted)
        zoom_label = f"{self.state.zoom_level} %"
        self.st_zoom = ft.Text(zoom_label, size=11.5, color=muted)
        self.toolbar_zoom = ft.Text(
            zoom_label, size=11.5, width=42, text_align=ft.TextAlign.CENTER,
            font_family=UI_FONT_STRONG, color=muted)
        self.st_pos = ft.Text("Ln 1, Col 1", size=11.5, color=muted)
        self.st_encoding = ft.Text("UTF-8 · LF", size=11.5, color=muted)

    def _build_persistent_containers(self):
        """Conteneurs réutilisés d'un rendu à l'autre, pour de vraies animations."""
        self._sidebar = ft.Container(
            width=52, clip_behavior=ft.ClipBehavior.HARD_EDGE,
            animate=ft.Animation(250, ft.AnimationCurve.EASE_OUT_CUBIC))
        self._toolbar_wrap = ft.Container(
            height=TOOLBAR_HEIGHT, opacity=1.0,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT_CUBIC),
            animate_opacity=ft.Animation(200, ft.AnimationCurve.EASE_OUT_CUBIC))
        self._ac_popup_wrap = ft.Container(expand=True, visible=False)
        self._tab_bar_wrap = ft.Container()
        # Zones remplacées en place à chaque rafraîchissement, plutôt que
        # recréées : Flutter conserve alors l'état et les animations.
        self._search_bar_wrap = ft.Container(
            visible=False, opacity=0.0, offset=ft.Offset(0, -0.12),
            animate_opacity=ft.Animation(MOTION_NORMAL, ft.AnimationCurve.EASE_OUT),
            animate_offset=ft.Animation(MOTION_NORMAL, ft.AnimationCurve.EASE_OUT))
        self._status_wrap = ft.Container()
        self._ai_panel_wrap = ft.Container(
            width=0, opacity=0.0, clip_behavior=ft.ClipBehavior.HARD_EDGE,
            animate=ft.Animation(MOTION_PANEL, ft.AnimationCurve.EASE_OUT_CUBIC),
            animate_opacity=ft.Animation(MOTION_NORMAL, ft.AnimationCurve.EASE_OUT))
        self._overlay_wrap = ft.Container(expand=True, visible=False)
        self._center_column = None
        self._editor_backdrop = None
        self._mounted = False
        self._editor_wrap = ft.Container(
            expand=True, scale=ft.Scale(scale=1.0),
            animate_scale=ft.Animation(250, ft.AnimationCurve.EASE_OUT_CUBIC))
        self._scroll_detector = ft.GestureDetector(
            expand=True, on_scroll=lambda e: self.view_ctrl.on_editor_scroll(e))

        self._build_editor_subtree()
        self._reset_region_signatures()

        self._recent_chevron_img = svg_icon(
            "angle-circle-right", size=ICON_XS, color=self.c(T.L_MUTED, T.D_MUTED))
        self._recent_expandable = ft.Container(
            height=0, clip_behavior=ft.ClipBehavior.HARD_EDGE,
            animate=ft.Animation(300, ft.AnimationCurve.EASE_OUT_CUBIC),
            content=ft.Container(
                opacity=0.0,
                animate_opacity=ft.Animation(260, ft.AnimationCurve.EASE_OUT_CUBIC),
                content=ft.Column(spacing=1, controls=[])))
        self._recent_expanded_height = 0

    def _build_editor_subtree(self):
        """Monte **une fois pour toutes** l'arbre qui entoure l'éditeur.

        Le rendu précédent recréait, à chaque rafraîchissement, le `Stack` et
        le `Container` qui contiennent le `TextField`. Côté Flutter, un
        contrôle qui change de parent est détruit puis reconstruit : il perd
        son focus, sa sélection et la position de son curseur. C'est
        exactement ce qui se produisait à chaque suggestion d'autocomplétion,
        c'est-à-dire à chaque frappe.

        Ici, la position de l'éditeur dans l'arbre ne change plus jamais.
        Seules varient des **propriétés** : les spans de la couche colorée, la
        visibilité de la gouttière, celle de l'aperçu Markdown. Flutter garde
        alors le champ de saisie intact, curseur compris.
        """
        # Couche de spans (coloration, recherche, diff, texte fantôme).
        self._span_text = ft.Text(spans=[], selectable=False)
        self._span_layer = ft.Container(
            expand=True, padding=ft.Padding(40, 36, 40, 36), visible=False,
                                        content=self._span_text)

        self._editor_stack = ft.Stack(expand=True, controls=[
            self._span_layer,
            ft.Container(expand=True, content=self.editor),
        ])

        # Gouttière de numéros de ligne — masquée, pas retirée.
        self._gutter_wrap = ft.Container(visible=False)

        # Aperçu Markdown — le contrôle vit en permanence, seule sa valeur change.
        self._md_view = ft.Markdown(
            "", selectable=True,
            extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
            # L'aperçu montre le **document**, pas l'interface : son corps de
            # texte reste en Regular, comme l'éditeur, alors que le thème de la
            # page est passé en SemiBold pour l'interface.
            md_style_sheet=ft.MarkdownStyleSheet(
                p_text_style=ft.TextStyle(font_family=EDITOR_FONT)),
            on_tap_link=lambda e: self.page.launch_url(e.data))
        self._md_divider = ft.Container(width=1, visible=False)
        self._md_wrap = ft.Container(
            visible=False, padding=ft.Padding(40, 36, 40, 36),
            content=ft.Column(expand=True, scroll=ft.ScrollMode.AUTO,
                              controls=[self._md_view]))

        self._editor_row = ft.Row(expand=True, spacing=0, controls=[
            self._gutter_wrap,
            ft.Container(expand=True, content=ft.Stack(
                expand=True, controls=[self._editor_stack, self._ac_popup_wrap])),
            self._md_divider,
            self._md_wrap,
        ])

        self._editor_wrap.content = self._editor_row
        self._scroll_detector.content = self._editor_wrap

    def _reset_region_signatures(self):
        """Empreintes des zones persistantes — voir `_refresh_regions`."""
        self._sig_toolbar = None
        self._sig_search = None
        self._sig_sidebar = None
        self._sig_tabs = None
        self._sig_status = None
        self._sig_ai_panel = None
        self._sig_gutter = None
        #: Incrémenté quand le disque a changé sous l'arborescence (fichier
        #: enregistré, renommé, ouvert) : l'empreinte seule ne le verrait pas.
        self._sidebar_epoch = 0
        #: Dernière tokenisation retenue — (langage, longueur, empreinte).
        self._hl_key = None
        self._hl_segments: list = []

    def _build_services(self) -> AppServices:
        """Rassemble ce que l'application offre à ses contrôleurs.

        Les rappels sont résolus **à l'appel** : `auto_save` peut donc
        référencer `FileController`, construit plus tard.
        """
        return AppServices(
            rebuild=self.rebuild,
            update_status=self.update_status,
            show_snack=self.show_snack,
            set_status_message=self.set_status_message,
            refresh_tab_bar=self._refresh_tab_bar,
            flush_typing=self.flush_typing,
            get_cursor=self._get_cursor_pos,
            get_selection=self._get_selection,
            save_session=self._save_session,
            push_recent=self._push_recent_and_update,
            auto_save=lambda: self.file_ctrl.auto_save(),
        )

    def _build_controllers(self):
        page = self.page
        self.services = self._build_services()
        svc = self.services

        # Les bornes sont résolues à l'appel : `editor_ctrl` et `search_ctrl`
        # n'existent pas encore ici.
        self.tab_ctrl = TabController(
            self.state, self.editor, self.ph, svc,
            on_leave_document=lambda: self._leave_document(),
            on_enter_document=lambda: self._enter_document())
        self.ac_ctrl = AutocompleteController(
            self.state, self.editor, self.tab_ctrl.cur_doc, self.rebuild, page,
            refresh_fn=self._refresh_ghost,
            llm_ready_fn=lambda: self.llm.is_task_enabled("autocomplete"),
            manager=self.llm)
        self.editor_ctrl = EditorController(
            self.state, self.editor, self.tab_ctrl.cur_doc, page, svc,
            autocomplete_ctrl=self.ac_ctrl)
        self.file_ctrl = FileController(
            page, self.state, self.editor, self.c, self.file_picker,
            self.tab_ctrl, svc)
        self.ai_ctrl = AIController(
            page, self.state, self.editor, self.c, self.tab_ctrl,
            self.show_snack, self.rebuild, clipboard=self.clipboard,
            manager=self.llm, get_selection_fn=self._get_selection,
            request_consent_fn=self._request_cloud_consent,
            open_setup_fn=self._show_ai_setup)
        self.voice_ctrl = VoiceController(
            page, self.voice, self.editor, self.c, self.tab_ctrl, svc)
        self.search_ctrl = SearchController(
            self.state, self.editor, self.state.search, self.tab_ctrl,
            self.update_status, self.rebuild, page, show_snack=self.show_snack,
            refresh_layer=self.refresh_editor)
        self.clip_ctrl = ClipboardController(
            page, self.clipboard, self.editor, self.tab_ctrl, self.editor_ctrl,
            self._get_selection, self._get_cursor_pos, self.c,
            self.show_snack, self.rebuild, self.update_status)
        self.dialog_ctrl = DialogController(
            page, self.state, self.c, self.tab_ctrl, self.file_picker, svc, self)
        self.update_ctrl = UpdateController(page, self.c, svc, self)
        self.ux_ctrl = AIUXController(
            page, self.state, self.editor, self.tab_ctrl, self.ai_ctrl,
            self.rebuild, self.show_snack, self._get_selection,
            self._get_cursor_pos)
        self.view_ctrl = ViewController(
            page, self.state, self.editor, self.c, self.tab_ctrl, svc,
            zoom_widget=self.st_zoom, toolbar_zoom_widget=self.toolbar_zoom,
            editor_wrap=self._editor_wrap,
            sidebar=self._sidebar, toolbar_wrap=self._toolbar_wrap,
            build_sidebar_fn=lambda: build_sidebar(self.state, self.c,
                                                   self._sidebar_callbacks()),
            build_toolbar_fn=lambda: build_menu_bar(self.c,
                                                    self._menu_bar_callbacks()),
            autocomplete_ctrl=self.ac_ctrl,
            refresh_layer_fn=self.refresh_editor)
        self.kb_ctrl = KeyboardController(
            page, self.c, self.tab_ctrl, self.file_ctrl, self.ai_ctrl,
            self.voice_ctrl, self.check_spelling, self._show_emoji_picker,
            self._request_close, toggle_toolbar=self.toggle_toolbar,
            undo=self.undo, redo=self.redo, search_ctrl=self.search_ctrl,
            zoom_in=self.zoom_in, zoom_out=self.zoom_out, set_mode=self.set_mode,
            autocomplete_ctrl=self.ac_ctrl, ai_ux=self.ux_ctrl,
            goto_line=self.show_goto_line,
            close_tab=lambda: self._confirm_close_tab(self.state.idx),
            show_help_fn=self._show_help,
            toggle_md_preview=self.toggle_md_preview,
            zoom_reset=self.zoom_reset)

    def _wire_controllers(self):
        # Il ne reste qu'une dépendance à câbler après coup : le catalogue de
        # commandes référence tous les contrôleurs, il ne peut donc être
        # construit qu'une fois tous présents.
        self.ux_ctrl.commands = self._build_command_registry()

    # ==================================================================
    # Session — déléguée à SessionController
    # ==================================================================
    def _save_session(self):
        self.session_ctrl.save()

    def _apply_session_settings(self):
        self.session_ctrl.apply_settings()

    def _apply_session_tabs(self) -> bool:
        restored, missing = self.session_ctrl.restore_tabs()
        if restored:
            self.tab_ctrl.sync_editor()
        if missing:
            self.show_snack(f"{missing} fichier(s) introuvable(s) — "
                            "contenu restauré depuis la session.")
        return restored

    # ==================================================================
    # Ouverture de fichiers
    # ==================================================================
    def _open_file_by_path(self, fp: str):
        if not os.path.isfile(fp):
            self.show_snack(f"Fichier introuvable : {fp}",
                            self.c(T.L_WARNING, T.D_WARNING))
            return
        loaded = self.file_ctrl._load_or_report(fp)
        if loaded is None:
            return
        self.state.push_recent(fp)
        self.tab_ctrl.add_tab_from_file(os.path.basename(fp), loaded, fp)
        self._update_recent_list()
        self._save_session()

    def _on_ipc_paths_received(self, paths):
        """Appelé depuis le thread IPC quand une autre instance envoie des chemins."""
        async def _open():
            # L'instance peut etre cachee en mode resident : on la ramene.
            self._restore_window()
            self.open_paths(paths)
        self.page.run_task(_open)

    def _open_recent(self, path: str):
        self._open_file_by_path(path)
        self.rebuild()

    # ==================================================================
    # Espace de travail (dossier ouvert)
    # ==================================================================
    async def open_workspace(self, e=None):
        """Ouvre un dossier dans la barre latérale."""
        path = await self.file_picker.get_directory_path(
            dialog_title="Ouvrir un dossier comme espace de travail")
        if not self.session_ctrl.open_workspace(path):
            return
        # Déplier la barre latérale, sinon l'arborescence resterait invisible.
        self.state.sidebar_collapsed = False
        self.rebuild()
        self._save_session()

    def close_workspace(self):
        self.session_ctrl.close_workspace()
        self.rebuild()
        self._save_session()

    def toggle_workspace_dir(self, path: str):
        self.session_ctrl.toggle_workspace_dir(path)
        self.rebuild()

    # ==================================================================
    # Ouverture depuis le système (double-clic, « Ouvrir avec », dépôt sur
    # l'icône ou la barre des tâches — tous passent par argv puis l'IPC)
    # ==================================================================
    def open_paths(self, paths):
        """Ouvre une liste de chemins : les dossiers deviennent l'espace de travail.

        Ouvrir cent onglets parce qu'on a déposé un dossier ne rendrait
        service à personne ; l'arborescence est la bonne réponse.
        """
        opened = 0
        for path in paths:
            if not path:
                continue
            if os.path.isdir(path):
                self.state.workspace_path = path
                self.state.workspace_expanded_dirs = set()
                self.state.sidebar_collapsed = False
                opened += 1
            elif os.path.isfile(path):
                loaded = self.file_ctrl._load_or_report(path)
                if loaded is None:
                    continue
                self.state.push_recent(path)
                self.tab_ctrl.add_tab_from_file(os.path.basename(path),
                                                loaded, path)
                opened += 1

        if opened:
            self._update_recent_list()
            self.rebuild()
            self._save_session()
        return opened

    # ==================================================================
    # Thème
    # ==================================================================
    def dark(self) -> bool:
        return self.page.theme_mode == ft.ThemeMode.DARK

    def c(self, light, dark):
        return dark if self.dark() else light

    def set_status_message(self, text: str, color=None):
        """Message transitoire de la barre d'état.

        Les contrôleurs passent par ici plutôt que d'écrire dans le widget :
        `FileController` n'a pas à connaître la vue.
        """
        self.st_msg.value = text
        self.st_msg.color = color or self.c(T.L_TERTIARY, T.D_TERTIARY)

    def show_snack(self, msg, color=None):
        """Notification transitoire — voir `controllers/notifier.py`."""
        self._notifier.show(msg, color)

    # ==================================================================
    # Statut
    # ==================================================================
    def update_status(self):
        d = self.tab_ctrl.cur_doc()
        if not d:
            return
        text = d.content

        # len() est en O(1) : on peut l'afficher à chaque frappe.
        self.st_chars.value = f"{len(text)} car."
        self.st_mode.value = {"text": "Mode Texte", "calc": "Mode Calcul",
                              "read": "Mode Lecture"}.get(self.state.mode, "Mode Texte")

        line, col = line_col_at_cursor(text, self.state.cursor)
        self.st_pos.value = f"Ln {line}, Col {col}"

        newline_label = {"\r\n": "CRLF", "\n": "LF", "\r": "CR"}.get(d.newline, "LF")
        encoding_label = d.encoding.upper().replace("-SIG", " BOM")
        lang_label = language_label(self._current_language(d))
        self.st_encoding.value = f"{lang_label} · {encoding_label} · {newline_label}"
        self.st_encoding.color = (self.c(T.L_WARNING, T.D_WARNING)
                                  if not d.encoding_confident
                                  else self.c(T.L_TERTIARY, T.D_TERTIARY))

        self._schedule_word_count(text)
        self._update_status_message(d, text)

    def _schedule_word_count(self, text: str):
        """Recompte les mots après une pause — jamais pendant la frappe."""
        scheduler.cancel(_WORD_COUNT_TASK)

        if len(text) < 20_000:
            # Assez court pour être compté immédiatement sans lag perceptible.
            self.st_words.value = f"{count_words(text)} mots"
            return

        self.st_words.value = "… mots"

        def compute():
            total = count_words(text)

            def apply():
                self.st_words.value = f"{total} mots"
                if self._mounted:
                    self.page.update(self._status_wrap)
                else:
                    self.page.update()

            self.page.run_thread(apply)

        scheduler.schedule(_WORD_COUNT_TASK, _WORD_COUNT_DELAY, compute)

    def _update_status_message(self, d, text: str):
        search = self.state.search
        if search.visible and search.query:
            if search.matches:
                match = search.current_match()
                ctx = self._search_context(text, match) if match else ""
                self.st_msg.value = (
                    f"Recherche : {search.current_index + 1}/{search.total}"
                    + (f"  —  {ctx}" if ctx else " résultat(s)"))
                self.st_msg.color = self.c(T.L_ACCENT, T.D_ACCENT)
            else:
                self.st_msg.value = f"Recherche : aucun résultat pour « {search.query} »"
                self.st_msg.color = self.c(T.L_WARNING, T.D_WARNING)
        elif d.modified:
            self.st_msg.value = "Modifications non enregistrées"
            self.st_msg.color = self.c(T.L_WARNING, T.D_WARNING)
        else:
            if self.st_msg.value == "Modifications non enregistrées":
                self.st_msg.value = ""
            self.st_msg.color = self.c(T.L_TERTIARY, T.D_TERTIARY)

    @staticmethod
    def _search_context(text: str, match: tuple[int, int]) -> str:
        start, end = match
        line_num = text.count("\n", 0, start) + 1
        ctx_start, ctx_end = max(0, start - 20), min(len(text), end + 20)
        before = text[ctx_start:start].replace("\n", " ")
        after = text[end:ctx_end].replace("\n", " ")
        prefix = "..." if ctx_start > 0 else ""
        suffix = "..." if ctx_end < len(text) else ""
        return f"Ligne {line_num} : {prefix}{before}[{text[start:end]}]{after}{suffix}"

    # ==================================================================
    # Événements éditeur
    # ==================================================================
    def _on_selection_change(self, e):
        sel = e.control.selection
        self.state.selection = None
        if sel is None:
            return
        if sel.start is not None:
            self.state.cursor = sel.start
        if not sel.is_collapsed:
            self.state.selection = (min(sel.start, sel.end), max(sel.start, sel.end))
        line, col = line_col_at_cursor(self.editor.value or "", self.state.cursor)
        self.st_pos.value = f"Ln {line}, Col {col}"

    def _on_text_changed(self, e):
        self.editor_ctrl.on_text_changed(e)

    def _get_selection(self):
        return self.state.selection

    def _get_cursor_pos(self) -> int:
        d = self.tab_ctrl.cur_doc()
        length = len(d.content) if d else 0
        return max(0, min(self.state.cursor, length))

    def _update_ac_hint(self):
        """Rappel de raccourci affiche tant qu'une suggestion est proposee."""
        if not self.state.ac_ghost:
            self._ac_popup_wrap.visible = False
            self._ac_popup_wrap.content = None
            return
        hint = build_ghost_hint(self.c, self.state.ac_ghost)
        self._ac_popup_wrap.content = hint.content if hint else None
        self._ac_popup_wrap.alignment = ft.Alignment(1, 1)
        self._ac_popup_wrap.visible = hint is not None

    def refresh_editor(self):
        """Rafraîchit la **seule** zone d'édition — chemin de la frappe.

        `rebuild()` remet à jour toute l'ossature : barre latérale (qui lit le
        disque quand un dossier est ouvert), barre d'outils, onglets, barre
        d'état, panneau IA. Le rappeler à chaque suggestion d'autocomplétion,
        donc à chaque caractère tapé, revenait à reconstruire l'application
        entière entre deux touches — c'est l'origine des à-coups et des
        blocages.

        Ici on ne touche qu'à la couche de texte, et on ne pousse au client
        que ce sous-arbre : le reste de l'interface n'est même pas comparé.
        """
        if not self._mounted:
            self.rebuild()
            return
        self._refresh_editor_layer(self._zoom_text_size())
        self.page.update(self._scroll_detector)

    def flush_typing(self):
        """Envoie au client les seules zones que la frappe fait bouger.

        `page.update()` recalcule la différence sur **tout** l'arbre de
        contrôles : barre latérale, arborescence du dossier ouvert, barre
        d'outils, panneau IA. Appelé à chaque caractère, il faisait payer la
        totalité de l'interface pour un compteur qui passe de 41 à 42.
        """
        if not self._mounted:
            self.page.update()
            return
        self.page.update(self._scroll_detector, self._status_wrap)

    def _refresh_ghost(self):
        """Rappel de rafraîchissement d'`AutocompleteController`.

        Pendant la frappe, `EditorController` enverra l'état au client une
        fois la touche entièrement traitée (`flush_typing`). Envoyer ici en
        plus ferait comparer deux fois le même sous-arbre pour un seul
        caractère — et ce sous-arbre contient la couche de spans, qui peut en
        compter des milliers sur un fichier coloré.
        """
        if not self._mounted:
            self.rebuild()
            return
        if self.ac_ctrl.typing:
            self._refresh_editor_layer(self._zoom_text_size())
            return
        self.refresh_editor()

    async def _on_keyboard(self, e):
        self.view_ctrl.set_ctrl_pressed(e.ctrl)
        await self.kb_ctrl.on_keyboard_event(e)

    # ==================================================================
    # Affichage — délégué à ViewController
    #
    # Ces méthodes restent exposées ici parce que la palette de commandes,
    # la barre d'outils et le clavier les référencent par leur nom.
    # ==================================================================
    def set_mode(self, mode):
        self.view_ctrl.set_mode(mode)

    def zoom_in(self):
        self.view_ctrl.zoom_in()

    def zoom_out(self):
        self.view_ctrl.zoom_out()

    def zoom_reset(self):
        self.view_ctrl.zoom_reset()

    def toggle_theme(self):
        self.view_ctrl.toggle_theme()

    def toggle_auto_save(self):
        self.view_ctrl.toggle_auto_save()

    def toggle_autocomplete(self):
        self.view_ctrl.toggle_autocomplete()

    def toggle_syntax(self):
        self.view_ctrl.toggle_syntax()

    def toggle_line_numbers(self):
        self.view_ctrl.toggle_line_numbers()

    def toggle_md_preview(self):
        self.view_ctrl.toggle_md_preview()

    def toggle_toolbar(self):
        self.view_ctrl.toggle_toolbar()

    def toggle_sidebar(self):
        self.view_ctrl.toggle_sidebar()

    def _zoom_text_size(self) -> int:
        return self.view_ctrl.text_size()

    # ==================================================================
    # Undo / Redo
    # ==================================================================
    def undo(self, e=None):
        self.tab_ctrl.save_content()
        self.editor_ctrl.force_snapshot()
        d = self.tab_ctrl.cur_doc()
        if not d:
            return
        result = d.undo()
        if result is None:
            self.show_snack("Rien à annuler.")
            return
        self.editor.value = result
        d.modified = True
        self.editor_ctrl.reset_snapshot_tracking()
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
        self.editor_ctrl.reset_snapshot_tracking()
        self.update_status()
        self.page.update()

    # ==================================================================
    # Orthographe
    # ==================================================================
    def check_spelling(self, e=None):
        self.tab_ctrl.save_content()
        d = self.tab_ctrl.cur_doc()
        if not d or not d.content.strip():
            self.show_snack("Rien à vérifier.")
            return

        self.show_snack("Vérification orthographique…")
        content = d.content

        def worker():
            wrong = self.spell.check(content)

            def report():
                if not self.spell.ready:
                    self.show_snack(self.spell.load_error or "Correcteur indisponible.",
                                    self.c(T.L_WARNING, T.D_WARNING))
                elif wrong:
                    self.show_snack(
                        f"{len(wrong)} mot(s) inconnu(s) : "
                        f"{', '.join(sorted(wrong)[:8])}",
                        self.c(T.L_WARNING, T.D_WARNING))
                else:
                    self.show_snack("Aucune faute détectée.",
                                    self.c(T.L_SUCCESS, T.D_SUCCESS))

            self.page.run_thread(report)

        threading.Thread(target=worker, daemon=True).start()

    # ==================================================================
    # Récupération après arrêt anormal
    # ==================================================================
    def _offer_recovery_if_needed(self):
        """Le journal survit à une fermeture propre = la session a planté."""
        if self._pending_recovery:
            self.dialog_ctrl.show_recovery(self._pending_recovery)

    def show_recovery(self, e=None):
        self.dialog_ctrl.show_recovery(self._pending_recovery or None)

    def restore_recovered(self, documents):
        """Rouvre les documents retrouvés, volontairement **sans chemin** :
        écraser automatiquement le fichier d'origine serait le pire service
        à rendre à l'utilisateur."""
        from models.document import Document as Doc

        restored = 0
        for entry in documents:
            content = entry.get("content") or ""
            if not content:
                continue
            title = entry.get("title") or "Récupéré"
            self.state.docs.append(Doc(
                title=f"{title} (récupéré)", content=content, path=None,
                modified=True, encoding=entry.get("encoding", "utf-8"),
                newline=entry.get("newline", "\n")))
            restored += 1

        if restored:
            self.state.idx = len(self.state.docs) - 1
            self.tab_ctrl.sync_editor()

        recovery.clear()
        self._pending_recovery = []
        self.rebuild()
        self.show_snack(
            f"{restored} document(s) récupéré(s) — pensez à les enregistrer.",
            self.c(T.L_SUCCESS, T.D_SUCCESS))

    # ==================================================================
    # Aller à la ligne
    # ==================================================================
    def show_goto_line(self):
        self.dialog_ctrl.show_goto_line()

    def goto_line(self, line: int):
        d = self.tab_ctrl.cur_doc()
        if not d:
            return
        pos = 0
        for _ in range(line - 1):
            nxt = d.content.find("\n", pos)
            if nxt == -1:
                break
            pos = nxt + 1
        self.state.cursor = pos
        try:
            self.editor.selection = ft.TextSelection(base_offset=pos, extent_offset=pos)
        except (AttributeError, TypeError):
            pass
        self.editor.focus()
        self.update_status()
        self.page.update()

    # ==================================================================
    # IA
    # ==================================================================
    def _show_ai_setup(self, e=None):
        from views.dialogs.ai_setup_dialog import show_ai_setup
        show_ai_setup(self.page, self.c, self.llm, on_changed=self.rebuild)

    def _request_cloud_consent(self, on_accept):
        from views.dialogs.ai_setup_dialog import show_cloud_consent
        show_cloud_consent(self.page, self.c, self.llm, on_accept)

    def _build_ai_badge(self):
        provider, _ = self.llm.resolve("edit")
        return build_ai_badge(
            self.c, self.llm.status_label(),
            is_local=bool(provider) and is_local(provider),
            warning=self.llm.over_budget(),
            on_click=self._show_ai_setup)

    def is_document_private(self) -> bool:
        d = self.tab_ctrl.cur_doc()
        return bool(d) and self.state.doc_private.get(id(d), False)

    def toggle_document_private(self):
        """Force le traitement local pour ce document seulement."""
        d = self.tab_ctrl.cur_doc()
        if not d:
            return
        key = id(d)
        now = not self.state.doc_private.get(key, False)
        self.state.doc_private[key] = now
        self.llm.document_private = now
        self.show_snack(
            f"« {d.title or 'Sans titre'} » : traitement local uniquement."
            if now else
            f"« {d.title or 'Sans titre'} » suit de nouveau le reglage global.")
        self.rebuild()

    def _sync_document_privacy(self):
        """Aligne le manager sur le document actif (change d'onglet)."""
        self.llm.document_private = self.is_document_private()

    def _toggle_privacy_mode(self):
        self.llm.privacy_mode = not self.llm.privacy_mode
        self.llm.save()
        self.show_snack("Mode confidentiel "
                        + ("activé — traitement local uniquement."
                           if self.llm.privacy_mode else "désactivé."))
        self.rebuild()

    # ==================================================================
    # Fichiers récents
    # ==================================================================
    def _push_recent_and_update(self, path: str):
        self.state.push_recent(path)
        self._update_recent_list()
        # Un fichier vient d'être écrit ou ouvert : l'arborescence du dossier
        # de travail peut avoir changé, son listage mémorisé ne vaut plus.
        self.invalidate_sidebar()

    def _update_recent_list(self):
        files = self.state.recent_files
        if files:
            items = []
            for path in files:
                name = os.path.basename(path)
                display = name if len(name) <= 22 else name[:19] + "…"
                items.append(ft.Container(
                    padding=ft.Padding(44, 5, 12, 5), border_radius=6,
                    bgcolor=ft.Colors.TRANSPARENT, ink=True, tooltip=path,
                    on_click=lambda e, p=path: self._open_recent(p),
                    content=ft.Row(spacing=8, controls=[
                        svg_icon("document", size=ICON_XS,
                                 color=self.c(T.L_MUTED, T.D_MUTED)),
                        ft.Text(display, size=12, expand=True, font_family=UI_FONT,
                                color=self.c(T.L_SECONDARY, T.D_SECONDARY),
                                overflow=ft.TextOverflow.ELLIPSIS),
                    ])))
        else:
            items = [ft.Container(
                padding=ft.Padding(44, 5, 12, 5),
                content=ft.Text("Aucun fichier récent", size=12, italic=True,
                                font_family=UI_FONT,
                                color=self.c(T.L_MUTED, T.D_MUTED)))]

        self._recent_expandable.content.content.controls = items
        self._recent_expanded_height = max(len(files), 1) * 28
        if self.state.recent_expanded:
            self._recent_expandable.height = self._recent_expanded_height

    def _toggle_recent_expanded(self):
        self.state.recent_expanded = not self.state.recent_expanded
        expanded = self.state.recent_expanded
        self._recent_chevron_img.src = ("icon/angle-circle-down.svg" if expanded
                                        else "icon/angle-circle-right.svg")
        self._recent_expandable.height = self._recent_expanded_height if expanded else 0
        self._recent_expandable.content.opacity = 1.0 if expanded else 0.0
        self.page.update()

    # ==================================================================
    # Dialogues — délégués à DialogController
    # ==================================================================
    def _show_emoji_picker(self):
        self.dialog_ctrl.show_emoji_picker()

    def _show_voice_menu(self):
        self.dialog_ctrl.show_voice_menu()

    def _show_help(self):
        self.dialog_ctrl.show_help()

    def _show_options(self):
        self.dialog_ctrl.show_options()

    # ==================================================================
    # Palette de commandes
    # ==================================================================
    def _build_command_registry(self):
        # Le catalogue vit dans son propre module : c'est une table de
        # données, pas de la logique d'orchestration.
        from controllers.command_registry import build_commands
        return build_commands(self)

    # ==================================================================
    # Fermeture
    # ==================================================================
    async def _on_window_event(self, e):
        if e.type == ft.WindowEventType.CLOSE:
            await self._request_close()

    # ==================================================================
    # Instance résidente
    # ==================================================================
    def _start_tray(self) -> bool:
        """Installe l'icône de notification si le mode résident est actif."""
        if self._tray is not None:
            return self._tray.active
        if not self.state.stay_resident:
            return False

        from models.tray import TrayIcon
        self._tray = TrayIcon(
            f"{APP_NAME} — actif en arrière-plan",
            resource_path("ressource/icon/icon.ico"),
            on_show=lambda: self.page.run_thread(self._restore_window),
            on_quit=lambda: self.page.run_task(self._quit_from_tray),
        )
        return self._tray.start()

    def _hide_to_tray(self):
        """Cache la fenêtre au lieu de quitter : le prochain lancement est instantané."""
        window = self.page.window
        window.visible = False
        window.skip_task_bar = True
        self.page.update()
        # La session est écrite maintenant : le processus survit, mais rien ne
        # garantit qu'il survivra à un arrêt brutal de la machine.
        self._save_session_now()

    def _restore_window(self):
        window = self.page.window
        window.skip_task_bar = False
        window.visible = True
        window.minimized = False
        self.page.update()
        window.to_front()

    async def _quit_from_tray(self):
        """« Quitter » depuis le menu de l'icône — fermeture complète."""
        self._restore_window()
        await self._request_close(force_quit=True)

    def toggle_stay_resident(self):
        self.state.stay_resident = not self.state.stay_resident
        if self.state.stay_resident:
            if self._start_tray():
                self.show_snack("Carib restera actif en arrière-plan — "
                                "les lancements suivants seront instantanés.")
            else:
                # Sans icône de notification, l'application deviendrait un
                # processus invisible et inaccessible : on refuse.
                self.state.stay_resident = False
                self.show_snack("Mode résident indisponible sur ce système.",
                                self.c(T.L_WARNING, T.D_WARNING))
        else:
            if self._tray:
                self._tray.stop()
                self._tray = None
            self.show_snack("Carib quittera complètement à la fermeture.")
        self._save_session()

    # ==================================================================
    # Fermeture
    # ==================================================================
    async def _request_close(self, force_quit: bool = False):
        # Mode résident : on se cache, sans rien perdre ni rien demander.
        if not force_quit and self.state.stay_resident and self._start_tray():
            self._hide_to_tray()
            return

        if self.file_ctrl.has_unsaved_docs():
            # Rien n'est démonté tant que l'utilisateur n'a pas tranché.
            # L'ancienne version appelait `_clean_exit()` **avant** de poser la
            # question : annuler la fermeture laissait alors une application
            # sans ordonnanceur — plus de sauvegarde automatique, plus
            # d'instantané d'annulation, plus de journal de récupération.
            self.dialog_ctrl.confirm_quit()
            return

        await self.shutdown_and_destroy()

    async def shutdown_and_destroy(self):
        """Unique sortie du processus : on démonte, puis on ferme la fenêtre."""
        self._clean_exit()
        await self.page.window.destroy()

    def _save_session_now(self):
        self.session_ctrl.save_now()

    def _clean_exit(self):
        """Fermeture volontaire : le journal de récupération n'a plus lieu d'être.

        C'est précisément sa disparition qui permet de distinguer, au
        prochain démarrage, un arrêt normal d'un plantage.

        L'ordre compte, et c'est lui qui rend la fermeture immédiate :

          1. **Couper d'abord les producteurs de travail.** Une requête au
             modèle, une réindexation du dictionnaire ou une sauvegarde
             automatique déjà lancée s'exécutent sur l'exécuteur de la page —
             que Flet attend à l'arrêt. Les annuler avant tout supprime
             l'attente au lieu de la subir.
          2. **Écrire ensuite**, une seule fois : la session était sérialisée
             deux fois quand on passait par « Enregistrer et quitter ».
          3. **Arrêter l'ordonnanceur en dernier**, sinon `flush_pending`
             n'aurait plus personne pour écrire la session en attente.
        """
        if self._exiting:
            # Idempotent : `_request_close` puis `save_all_and_quit` passent
            # tous deux par ici.
            return
        self._exiting = True

        # 1 — plus rien ne doit démarrer de nouveau travail
        self.ac_ctrl.shutdown()
        self._recovery.stop()
        self._notifier.shutdown()
        cancel_llm = getattr(self.llm, "cancel_all", None)
        if callable(cancel_llm):
            try:
                cancel_llm()
            except Exception:
                pass
        try:
            from models.ipc_server import stop_ipc_server
            stop_ipc_server()
        except Exception:
            pass

        # 2 — écritures finales
        recovery.clear()
        self._save_session_now()

        # 3 — plus aucune tâche différée ne se réveillera
        scheduler.stop()

        if self._tray:
            self._tray.stop()
            self._tray = None

    async def save_all_and_quit(self):
        from models.file_manager import write_file
        self.tab_ctrl.save_content()

        for d in self.state.docs:
            if not d.modified:
                continue
            if not d.path:
                path = await self.file_picker.save_file(
                    dialog_title=f"Enregistrer « {d.title} » avant de quitter",
                    file_name=d.title if "." in d.title else d.title + ".txt")
                if not path:
                    self.show_snack("Fermeture annulée.")
                    self.rebuild()
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
                self.show_snack(f"Échec pour « {d.title} » : {exc}",
                                self.c(T.L_ERROR, T.D_ERROR))
                self.rebuild()
                return

        await self.shutdown_and_destroy()

    def _confirm_close_tab(self, idx):
        self.dialog_ctrl.confirm_close_tab(idx)

    # ==================================================================
    # Dictionnaires de callbacks
    # ==================================================================
    def _sidebar_callbacks(self):
        d = self.tab_ctrl.cur_doc()
        return {
            "toggle_sidebar": self.toggle_sidebar,
            "open_workspace": lambda e=None: self.page.run_task(self.open_workspace),
            "close_workspace": self.close_workspace,
            "toggle_dir": self.toggle_workspace_dir,
            "active_path": d.path if d else None,
            "open_path": self._open_recent,
            "open_file": self.file_ctrl.open_file,
            "save_file": self.file_ctrl.save_file,
            "save_file_as": self.file_ctrl.save_file_as,
            "add_tab": self._new_tab,
            "rename_file": self.file_ctrl.rename_current_file,
            "print_file": self.file_ctrl.print_file,
            "show_help": self._show_help,
            "show_options": self._show_options,
            "open_recent": self._open_recent,
            "toggle_recent_expanded": self._toggle_recent_expanded,
            "open_command_bar": self.ux_ctrl.open_command_bar,
            "recent_chevron": self._recent_chevron_img,
            "recent_expandable": self._recent_expandable,
        }

    def _tab_bar_callbacks(self):
        return {
            "switch_tab": self._switch_tab,
            "close_tab": self._confirm_close_tab,
            "add_tab": self._new_tab,
            "open_command_bar": self.ux_ctrl.open_command_bar,
        }

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
            "show_model_manager": self._show_ai_setup,
            "show_emoji_picker": self._show_emoji_picker,
            "show_voice_menu": self._show_voice_menu,
            "copy_text_handler": lambda e: self.page.run_task(self.clip_ctrl.copy),
            "paste_text_handler": lambda e: self.page.run_task(self.clip_ctrl.paste),
            "cut_text_handler": lambda e: self.page.run_task(self.clip_ctrl.cut),
            "clear_text": self.clip_ctrl.clear,
            "undo": self.undo,
            "redo": self.redo,
            "toggle_search": self.search_ctrl.toggle_search,
            "zoom_in": self.zoom_in,
            "zoom_out": self.zoom_out,
            "zoom_widget": self.toolbar_zoom,
            "set_mode": self.set_mode,
            "open_command_bar": self.ux_ctrl.open_command_bar,
        }

    def _ai_panel_callbacks(self):
        return {
            "close_ai": self.ai_ctrl.close_ai,
            "apply_correction": self.ai_ctrl.apply_correction,
            "dismiss_correction": self.ai_ctrl.dismiss_correction,
            "replace_with_result": self.ai_ctrl.replace_with_result,
            "copy_result": self.ai_ctrl.copy_result,
            "review_inline": self.ux_ctrl.review_from_ai_panel,
        }

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
            "toggle_replace": self.search_ctrl.toggle_replace,
            "on_replacement_change": self.search_ctrl.on_replacement_change,
            "replace_current": self.search_ctrl.replace_current,
            "replace_all": self.search_ctrl.replace_all,
        }

    def _leave_document(self):
        """À appeler **avant** de quitter le document actif.

        Fige la salve de frappe en cours : sans cela, la dernière rafale de
        caractères tapée avant un changement d'onglet disparaissait de
        l'historique d'annulation.

        Les contrôleurs sont testés avant usage : `TabController` est
        construit avant eux, et la restauration de session peut activer un
        onglet pendant le démarrage.
        """
        if getattr(self, "editor_ctrl", None):
            self.editor_ctrl.force_snapshot()
        if getattr(self, "ac_ctrl", None):
            self.ac_ctrl.dismiss()

    def _enter_document(self):
        """À appeler **après** être arrivé sur un autre document.

        Tout ce qui décrit « où en est l'utilisateur » se rapporte au
        document quitté : curseur, sélection, surlignage de recherche,
        dictionnaire d'autocomplétion. Laisser ces valeurs en place faisait
        travailler les commandes suivantes sur des positions appartenant à
        un autre texte.
        """
        self.state.selection = None
        self.state.cursor = 0
        self._sync_document_privacy()
        if getattr(self, "search_ctrl", None):
            self.search_ctrl.on_tab_switch()
        d = self.tab_ctrl.cur_doc()
        if d and d.content and getattr(self, "ac_ctrl", None):
            # Réindexation différée : elle parcourt tout le document, et n'a
            # aucune raison de retenir le changement d'onglet.
            self.ac_ctrl.refresh_dictionary_soon(d.content)

    def _switch_tab(self, idx):
        # Les bornes sont appliquées par TabController lui-même.
        self.tab_ctrl.switch_tab(idx)
        self._save_session()

    def _new_tab(self, *_):
        """Nouvel onglet (bouton « + », Ctrl+N, palette de commandes)."""
        self.tab_ctrl.add_tab()

    def _refresh_tab_bar(self):
        self._tab_bar_wrap.content = build_tab_bar(self.state, self.c,
                                                   self._tab_bar_callbacks())

    # ==================================================================
    # Rendu
    # ==================================================================
    def rebuild(self):
        """Rafraîchit l'interface **sans reconstruire l'arbre de contrôles**.

        L'ancienne version faisait `page.controls.clear()` puis `page.add()` à
        chaque collage, changement d'onglet ou résultat IA : Flutter jetait
        tout l'arbre et le recréait, ce qui interrompait les animations en
        cours et faisait clignoter la barre latérale.

        Désormais l'arbre est monté une seule fois, et seuls les contenus des
        conteneurs persistants sont remplacés.
        """
        self.update_status()
        size = self._zoom_text_size()
        self._style_editor(size)

        if not self._mounted:
            self._mount()

        self._refresh_regions(size)
        self.page.update()

    def _mount(self):
        """Monte l'arbre une fois pour toutes."""
        self._center_column = ft.Column(expand=True, spacing=0, controls=[
            self._toolbar_wrap,
            self._search_bar_wrap,
            self._scroll_detector,
        ])

        layout = ft.Row(expand=True, spacing=0, controls=[
            self._sidebar,
            ft.Column(expand=True, spacing=0, controls=[
                self._tab_bar_wrap,
                ft.Container(expand=True, bgcolor=self.c(T.L_EDITOR, T.D_EDITOR),
                             content=self._center_column),
                self._status_wrap,
            ]),
            self._ai_panel_wrap,
        ])
        self._editor_backdrop = layout.controls[1].controls[1]

        root = ft.Stack(expand=True, controls=[layout, self._overlay_wrap])

        self.page.controls.clear()
        self.page.add(ft.Container(
            content=root, expand=True, opacity=0,
            animate_opacity=ft.Animation(400, ft.AnimationCurve.EASE_OUT)))
        self.page.update()
        self.page.controls[0].opacity = 1
        self._mounted = True

        startup_probe.mark("4_premiere_image")

    def _refresh_regions(self, size: int):
        """Met à jour chaque zone persistante — **si son contenu a changé**.

        Chaque zone porte une empreinte de ce dont son contenu dépend
        réellement. Reconstruire la barre latérale alors que ni le thème, ni
        le dossier ouvert, ni le fichier actif n'ont bougé ne produit qu'un
        arbre identique au précédent, au prix d'une relecture du disque et de
        plusieurs centaines de contrôles à comparer.

        Le bénéfice ne se limite pas au chemin rapide : même un `rebuild()`
        complet (changement d'onglet, résultat IA, enregistrement) ne
        reconstruit désormais que ce qui a effectivement changé.
        """
        self.page.bgcolor = self.c(T.L_BG, T.D_BG)
        self._apply_toolbar()
        self._apply_search_bar()
        self._apply_sidebar()
        self._apply_tab_bar()
        self._apply_status_bar()
        self._apply_ai_panel()

        if self._editor_backdrop is not None:
            self._editor_backdrop.bgcolor = self.c(T.L_EDITOR, T.D_EDITOR)

        self._refresh_editor_layer(size)
        self._refresh_overlays()

    # --- Zones persistantes, une par empreinte ------------------------

    def _apply_toolbar(self):
        sig = (self.dark(), self.state.show_toolbar)
        if sig == self._sig_toolbar:
            return
        self._sig_toolbar = sig
        self.view_ctrl.apply_toolbar()

    def _apply_search_bar(self):
        s = self.state.search
        # Volontairement **sans** la requête : reconstruire la barre à chaque
        # caractère détruisait le champ de saisie, donc son focus.
        sig = (self.dark(), s.visible, s.replace_visible, s.case_sensitive,
               s.whole_word, s.use_regex)
        if sig == self._sig_search:
            return
        self._sig_search = sig

        if s.visible:
            opening = not self._search_bar_wrap.visible
            bar, _, counter = build_search_bar(self.c, s,
                                               self._search_bar_callbacks())
            self.search_ctrl.counter_ref = counter
            self._search_bar_wrap.content = bar
            self._search_bar_wrap.visible = True
            if opening:
                self._search_bar_wrap.opacity = 0.0
                self._search_bar_wrap.offset = ft.Offset(0, -0.12)
                self.page.update(self._search_bar_wrap)
            self._search_bar_wrap.opacity = 1.0
            self._search_bar_wrap.offset = ft.Offset(0, 0)
        else:
            self._search_bar_wrap.visible = False
            self._search_bar_wrap.opacity = 0.0
            self._search_bar_wrap.offset = ft.Offset(0, -0.12)
            self._search_bar_wrap.content = None
            self.search_ctrl.counter_ref = None

    def _apply_sidebar(self):
        d = self.tab_ctrl.cur_doc()
        sig = (self.dark(), self.state.sidebar_collapsed, self.state.sidebar_key,
               self.state.workspace_path,
               tuple(sorted(self.state.workspace_expanded_dirs)),
               self.state.recent_expanded, tuple(self.state.recent_files),
               d.path if d else None, self._sidebar_epoch)
        if sig == self._sig_sidebar:
            return
        self._sig_sidebar = sig
        self.view_ctrl.apply_sidebar()

    def invalidate_sidebar(self):
        """Le disque a changé sous l'arborescence : la relire au prochain rendu."""
        from models import workspace
        workspace.invalidate_cache()
        self._sidebar_epoch += 1

    def _apply_tab_bar(self):
        sig = (self.dark(), self.state.idx,
               tuple((d.title, d.modified) for d in self.state.docs))
        if sig == self._sig_tabs:
            return
        self._sig_tabs = sig
        self._tab_bar_wrap.content = build_tab_bar(self.state, self.c,
                                                   self._tab_bar_callbacks())

    def _apply_status_bar(self):
        # Les compteurs (`st_chars`, `st_pos`…) sont des contrôles persistants
        # mis à jour en place par `update_status` : seule l'ossature de la
        # barre et le badge IA dépendent d'autre chose.
        provider, _ = self.llm.resolve("edit")
        sig = (self.dark(), self.llm.status_label(),
               bool(provider) and is_local(provider), self.llm.over_budget())
        if sig == self._sig_status:
            return
        self._sig_status = sig
        self._status_wrap.content = build_status_bar(
            self.c, self.st_mode, self.st_msg, self.st_chars, self.st_words,
            self.st_zoom, st_pos=self.st_pos, st_encoding=self.st_encoding,
            ai_badge=self._build_ai_badge())

    def _apply_ai_panel(self):
        # Le panneau lit une vingtaine de champs d'état ; plutôt que de tous
        # les énumérer — et d'en oublier un —, on ne saute la reconstruction
        # que dans le cas qui compte : panneau fermé, et déjà fermé au rendu
        # précédent. C'est celui de la frappe.
        showing = bool(self.state.show_ai)
        sig = (showing, self.dark())
        if not showing and sig == self._sig_ai_panel:
            return
        was_showing = self._ai_panel_wrap.width == 380
        self._sig_ai_panel = sig
        if showing:
            self._ai_panel_wrap.content = build_ai_panel(
                self.state, self.c, self._ai_panel_callbacks())
            if not was_showing:
                self._ai_panel_wrap.width = 0
                self._ai_panel_wrap.opacity = 0.0
                self.page.update(self._ai_panel_wrap)
            self._ai_panel_wrap.width = 380
            self._ai_panel_wrap.opacity = 1.0
        else:
            self._ai_panel_wrap.width = 0
            self._ai_panel_wrap.opacity = 0.0

    def _style_editor(self, size: int):
        self.editor.text_size = size
        self.editor.hint_style = ft.TextStyle(
            size=size, font_family=EDITOR_FONT, letter_spacing=0.2,
            color=self.c(T.L_MUTED, T.D_MUTED), italic=True)
        self.editor.cursor_color = self.c(T.L_ACCENT, T.D_ACCENT)
        self.editor.selection_color = ft.Colors.with_opacity(
            0.45, self.c(T.L_HL_CURRENT, T.D_HL_CURRENT))
        if not self.state.diff_active:
            self.editor.read_only = (self.state.mode == MODE_READ)

        self.st_zoom.value = f"{self.state.zoom_level} %"
        for widget in (self.st_chars, self.st_words, self.st_zoom, self.st_pos):
            widget.color = self.c(T.L_TERTIARY, T.D_TERTIARY)
        self.st_mode.color = self.c(T.L_ACCENT, T.D_ACCENT)

    def _current_language(self, doc=None):
        """Langage du document courant, ou None si la coloration est coupée."""
        if not self.state.syntax_enabled:
            return None
        d = doc or self.tab_ctrl.cur_doc()
        if not d:
            return None
        return detect_language(d.path, d.title)

    def _refresh_editor_layer(self, size: int):
        """Met à jour la couche de texte posée sous l'éditeur.

        Une seule couche de spans peut être affichée à la fois. L'ordre de
        priorité est celui de l'attention de l'utilisateur : une revue de
        modification prime sur une recherche, qui prime sur la coloration.

        Rien n'est reconstruit ici : on remplace les **spans** d'un `ft.Text`
        qui, lui, ne bouge jamais de l'arbre (voir `_build_editor_subtree`).
        """
        d = self.tab_ctrl.cur_doc()
        text = d.content if d else ""
        search = self.state.search

        spans = None

        if self.state.diff_active:
            start, end = self.state.diff_range
            end = min(end, len(text))
            start = max(0, min(start, end))
            spans = build_diff_spans(text[:start], self.ux_ctrl.diff_segments(),
                                     text[end:], self.c, size)

        elif search.visible and search.matches:
            spans = build_highlight_spans(text, search.matches,
                                          search.current_index, self.c, size)

        else:
            segments = self._syntax_segments(text, d)
            ghost = self.state.ac_ghost
            if ghost:
                # La suggestion n'existe que dans cette couche : elle ne peut
                # pas se retrouver enregistrée dans le fichier par accident.
                spans = build_ghost_spans(text, self._get_cursor_pos(), ghost,
                                          self.c, size, segments=segments,
                                          dark=self.dark())
            elif segments:
                spans = build_syntax_spans(text, segments, self.c, size,
                                           self.dark())

        if spans is None:
            # Aucune couche : l'éditeur affiche son propre texte, en opaque.
            self.editor.text_style = ft.TextStyle(
                size=size, height=1.4, font_family=EDITOR_FONT, letter_spacing=0.2,
                color=self.c(T.L_PRIMARY, T.D_PRIMARY))
            self._span_layer.visible = False
            self._span_text.spans = []
        else:
            self.editor.text_style = ft.TextStyle(
                size=size, height=1.4, font_family=EDITOR_FONT, letter_spacing=0.2,
                color=ft.Colors.TRANSPARENT)
            self._span_text.spans = spans
            self._span_layer.visible = True

        self._refresh_gutter(text, size)
        self._refresh_markdown_preview(text)
        self._update_ac_hint()

    def _syntax_segments(self, text: str, doc):
        """Segments colorés du document, mémorisés d'un rendu à l'autre.

        La tokenisation parcourt jusqu'à 120 000 caractères d'expressions
        régulières. Elle était refaite à chaque rafraîchissement, y compris
        quand le texte n'avait pas changé d'un caractère — deux ou trois fois
        par frappe. L'empreinte du texte suffit à l'éviter : `hash` d'une
        chaîne Python est mémorisé par l'objet lui-même, donc gratuit ici.
        """
        language = self._current_language(doc)
        if language is None or not text:
            return []

        key = (id(language), len(text), hash(text))
        if key == self._hl_key:
            return self._hl_segments

        self._hl_key = key
        self._hl_segments = highlight(text, language)
        return self._hl_segments

    def _refresh_gutter(self, text: str, size: int):
        """Gouttière de numéros de ligne, redessinée seulement si nécessaire."""
        if not self.state.show_line_numbers:
            if self._sig_gutter is not None:
                self._gutter_wrap.visible = False
                self._gutter_wrap.content = None
                self._sig_gutter = None
            return

        line, _ = line_col_at_cursor(text, self.state.cursor)
        sig = (text.count("\n"), line, size, self.dark())
        if sig != self._sig_gutter:
            self._sig_gutter = sig
            self._gutter_wrap.content = build_line_gutter(
                text, self.c, size, current_line=line)
        self._gutter_wrap.visible = True

    def _refresh_markdown_preview(self, text: str):
        """Aperçu Markdown : le contrôle reste monté, seule sa valeur change."""
        active = self.state.md_preview
        self._md_divider.visible = active
        self._md_wrap.visible = active
        # `expand` est retiré en même temps que la visibilité : un panneau
        # masqué mais toujours « extensible » réclamerait la moitié de la
        # largeur à la rangée, et l'éditeur s'afficherait à droite d'un vide.
        self._md_wrap.expand = True if active else None
        if not active:
            return

        self._md_divider.bgcolor = self.c(T.L_BORDER, T.D_BORDER)
        self._md_wrap.bgcolor = self.c(T.L_SIDEBAR, T.D_SIDEBAR)
        self._md_view.code_theme = (ft.MarkdownCodeTheme.ATOM_ONE_DARK
                                    if self.dark()
                                    else ft.MarkdownCodeTheme.ATOM_ONE_LIGHT)
        value = text or "*Rien à prévisualiser.*"
        if self._md_view.value != value:
            self._md_view.value = value

    def _refresh_overlays(self):
        """Met à jour la couche superposée (Ctrl+K, palette, actions de diff)."""
        overlays = []

        if self.state.diff_active:
            added, removed = diff_stats(self.ux_ctrl.diff_segments())
            overlays.append(build_diff_actions(self.c, added, removed, {
                "accept": self.ux_ctrl.accept_diff,
                "reject": self.ux_ctrl.reject_diff,
            }))

        if self.state.kbar_visible:
            provider, model = self.llm.resolve("edit")
            provider_label = (model if provider
                              else "Aucune IA configurée — ouvrez les options IA")
            overlays.append(build_command_bar(
                self.state, self.c, {
                    "on_query_change": self.ux_ctrl.on_kbar_change,
                    "on_submit": self.ux_ctrl.submit_command_bar,
                    "on_close": self.ux_ctrl.close_command_bar,
                    "run_mode": self.ux_ctrl.run_mode_from_bar,
                },
                self.ux_ctrl.scope_label(), provider_label))

        if self.state.palette_visible:
            overlays.append(build_command_palette(
                self.state, self.c, self.ux_ctrl.commands, {
                    "on_query_change": self.ux_ctrl.on_palette_change,
                    "on_close": self.ux_ctrl.close_palette,
                    "run": self.ux_ctrl.run_command,
                }))

        if not overlays:
            self._overlay_wrap.visible = False
            self._overlay_wrap.content = None
            return

        self._overlay_wrap.visible = True
        self._overlay_wrap.content = (overlays[0] if len(overlays) == 1
                                      else ft.Stack(expand=True, controls=overlays))
