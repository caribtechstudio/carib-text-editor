"""
controllers/view_controller.py — Réglages d'affichage.

Extrait d'`AppController` : zoom, thème, mode d'édition, et les bascules de
confort (barre d'outils, barre latérale, coloration, numéros de ligne,
aperçu Markdown).

Tous ces réglages partagent la même mécanique — modifier `EditorState`,
redessiner, persister — et n'ont rien à voir avec l'orchestration des
contrôleurs. Les regrouper rend explicite ce qui relève de la présentation.
"""

import flet as ft

from constants import MODE_READ, TOOLBAR_HEIGHT, EDITOR_FONT
from models.scheduler import scheduler
from models.syntax import detect_language
from theme import T

#: Taille de police de référence, à 100 % de zoom.
BASE_TEXT_SIZE = 16
ZOOM_MIN, ZOOM_MAX, ZOOM_STEP = 50, 200, 10

#: Clé d'ordonnancement du retour d'animation après un zoom.
_ZOOM_TASK = "view.zoom_settle"


class ViewController:
    """Zoom, thème, modes et bascules d'affichage."""

    def __init__(self, page, state, editor, c, tab_ctrl, services,
                 zoom_widget, editor_wrap, sidebar, toolbar_wrap,
                 build_sidebar_fn, build_toolbar_fn, autocomplete_ctrl,
                 refresh_layer_fn=None):
        self._page = page
        self.state = state
        self.editor = editor
        self._c = c
        self._tab = tab_ctrl
        self._svc = services
        self._snack = services.show_snack
        self._rebuild = services.rebuild
        #: Rafraîchit la seule couche de texte (voir AppController).
        self._refresh_layer = refresh_layer_fn or services.rebuild
        self._save = services.save_session

        # Widgets pilotés directement, sans reconstruire l'arbre.
        self._st_zoom = zoom_widget
        self._editor_wrap = editor_wrap
        self._sidebar = sidebar
        self._toolbar_wrap = toolbar_wrap
        self._build_sidebar = build_sidebar_fn
        self._build_toolbar = build_toolbar_fn
        self._ac = autocomplete_ctrl

        self._ctrl_pressed = False

    # ==================================================================
    # Mode d'édition
    # ==================================================================
    def set_mode(self, mode: str):
        self.state.mode = mode
        self.editor.read_only = (mode == MODE_READ)
        self._svc.update_status()
        self._snack({"text": "Mode texte", "calc": "Mode calcul",
                     "read": "Mode lecture"}.get(mode, ""))
        self._rebuild()
        self._save()

    # ==================================================================
    # Zoom
    # ==================================================================
    def text_size(self) -> int:
        return round(BASE_TEXT_SIZE * self.state.zoom_level / 100)

    def zoom_in(self):
        if self.state.zoom_level >= ZOOM_MAX:
            self._snack(f"Zoom maximum atteint ({ZOOM_MAX} %)")
            return
        self.state.zoom_level = min(ZOOM_MAX, self.state.zoom_level + ZOOM_STEP)
        self._apply_zoom(direction=1)
        self._save()

    def zoom_out(self):
        if self.state.zoom_level <= ZOOM_MIN:
            self._snack(f"Zoom minimum atteint ({ZOOM_MIN} %)")
            return
        self.state.zoom_level = max(ZOOM_MIN, self.state.zoom_level - ZOOM_STEP)
        self._apply_zoom(direction=-1)
        self._save()

    def zoom_reset(self):
        if self.state.zoom_level == 100:
            return
        self.state.zoom_level = 100
        self._apply_zoom()
        self._save()

    def _apply_zoom(self, direction: int = 0):
        size = self.text_size()
        self.editor.text_size = size
        self.editor.text_style = ft.TextStyle(
            size=size, height=1.4, font_family=EDITOR_FONT, letter_spacing=0.2,
            color=(self.editor.text_style.color if self.editor.text_style
                   else self._c(T.L_PRIMARY, T.D_PRIMARY)))
        self.editor.hint_style = ft.TextStyle(
            size=size, font_family=EDITOR_FONT, letter_spacing=0.2,
            color=self._c(T.L_MUTED, T.D_MUTED), italic=True)

        self._st_zoom.value = f"{self.state.zoom_level} %"
        self._st_zoom.color = self._c(T.L_TERTIARY, T.D_TERTIARY)

        if direction and self._editor_wrap is not None:
            # Léger dépassement puis retour : le zoom devient perceptible
            # même quand l'écart de taille est d'un seul pixel.
            self._editor_wrap.scale = ft.Scale(scale=1.0)
            self._page.update()
            self._editor_wrap.scale = ft.Scale(scale=1.03 if direction > 0 else 0.97)
            self._page.update()

            def settle():
                self._editor_wrap.scale = ft.Scale(scale=1.0)
                self._page.update()

            scheduler.schedule(_ZOOM_TASK, 0.2, settle)
        else:
            self._page.update()

        # Les couches de spans sont dessinées à une taille fixe : elles se
        # décaleraient du texte réel si on ne les redessinait pas. La
        # coloration syntaxique était oubliée dans cette liste — zoomer dans
        # un fichier de code décalait donc les couleurs du texte. On redessine
        # désormais la couche dans tous les cas : c'est devenu assez peu cher
        # pour ne plus avoir à choisir.
        self._refresh_layer()

    # --- Ctrl + molette ---
    def set_ctrl_pressed(self, pressed: bool):
        self._ctrl_pressed = pressed

    @staticmethod
    def _is_ctrl_held() -> bool:
        """État réel de Ctrl (Windows uniquement — sans effet ailleurs)."""
        try:
            import ctypes
            return bool(ctypes.windll.user32.GetAsyncKeyState(0x11) & 0x8000)
        except (AttributeError, OSError, ImportError):
            return False

    def on_editor_scroll(self, e: ft.ScrollEvent):
        if not (self._ctrl_pressed or self._is_ctrl_held()):
            return
        if e.scroll_delta.y < 0:
            self.zoom_in()
        elif e.scroll_delta.y > 0:
            self.zoom_out()

    # ==================================================================
    # Bascules
    # ==================================================================
    def toggle_theme(self):
        self._page.theme_mode = (ft.ThemeMode.LIGHT
                                 if self._page.theme_mode == ft.ThemeMode.DARK
                                 else ft.ThemeMode.DARK)
        self._rebuild()
        self._save()

    def toggle_auto_save(self):
        self.state.auto_save = not self.state.auto_save
        self._announce("Sauvegarde automatique", self.state.auto_save)
        self._rebuild()
        self._save()

    def toggle_autocomplete(self):
        self.state.ac_enabled = not self.state.ac_enabled
        if not self.state.ac_enabled:
            self._ac.dismiss()
        self._announce("Autocomplétion", self.state.ac_enabled)
        self._save()

    def toggle_syntax(self):
        self.state.syntax_enabled = not self.state.syntax_enabled
        self._announce("Coloration syntaxique", self.state.syntax_enabled)
        self._rebuild()
        self._save()

    def toggle_line_numbers(self):
        self.state.show_line_numbers = not self.state.show_line_numbers
        if self.state.show_line_numbers:
            # Avertissement honnête : Flet enroule toujours les lignes longues
            # et n'expose aucune métrique de mise en page, donc la
            # numérotation se décale sous une ligne plus large que la fenêtre.
            self._snack("Numéros de ligne activés — ils comptent les lignes "
                        "réelles, pas les retours automatiques.")
        else:
            self._snack("Numéros de ligne désactivés")
        self._rebuild()
        self._save()

    def toggle_md_preview(self):
        d = self._tab.cur_doc()
        language = detect_language(d.path if d else None, d.title if d else "")
        if not self.state.md_preview and (language is None
                                          or language.name != "markdown"):
            self._snack("L'aperçu ne s'applique qu'aux fichiers Markdown (.md).",
                        self._c(T.L_WARNING, T.D_WARNING))
            return
        self.state.md_preview = not self.state.md_preview
        self._rebuild()
        self._save()

    def toggle_toolbar(self):
        self.state.show_toolbar = not self.state.show_toolbar
        self.apply_toolbar()
        self._page.update()
        self._save()

    def apply_toolbar(self):
        """Aligne le conteneur persistant sur l'état, sans tout reconstruire."""
        if self.state.show_toolbar:
            self._toolbar_wrap.content = self._build_toolbar()
            self._toolbar_wrap.height = TOOLBAR_HEIGHT
            self._toolbar_wrap.opacity = 1.0
        else:
            self._toolbar_wrap.height = 0
            self._toolbar_wrap.opacity = 0.0

    def toggle_sidebar(self):
        self.state.sidebar_collapsed = not self.state.sidebar_collapsed
        self.apply_sidebar()
        self._page.update()
        self._save()

    def apply_sidebar(self):
        self._sidebar.width = 56 if self.state.sidebar_collapsed else 240
        self._sidebar.content = self._build_sidebar()

    def _announce(self, label: str, enabled: bool):
        self._snack(f"{label} {'activée' if enabled else 'désactivée'}")
