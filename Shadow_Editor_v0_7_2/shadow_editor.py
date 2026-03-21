"""
Shadow Text Editor - v0.7.2
============================
Éditeur de texte moderne avec :
  - Onglets multiples avec gestion individuelle des fichiers
  - Calculatrice intégrée (parser AST sécurisé)
  - Text-to-Speech et Speech-to-Text (non-bloquant via QThread)
  - Correcteur IA local : ministral-3:3b via Ollama (grammaire + orthographe)
  - Correcteur orthographique de base (pyspellchecker) en fallback
  - Remplacement automatique d'emojis
  - Barre d'outils de formatage (gras, italique, couleurs…)
  - Thèmes sombre / clair
  - Mode Texte / Mode Calcul / Mode Lecture (lecture seule)

Changelog v0.7.0 :
  - Correcteur IA local avec ministral-3:3b via Ollama
  - Assistant d'installation guidée (Ollama + modèle) avec barre de progression,
    vitesse de téléchargement, ETA et taille disque
  - Panneau latéral de corrections IA (QDockWidget) cliquables
  - Bouton "Tout accepter" / "Tout ignorer" / "Supprimer le modèle"
  - Score de qualité du texte 0–100
  - Raccourci F7 pour lancer l'analyse IA

Commandes PyInstaller :
pyinstaller --onefile --windowed --add-data="ressource/icon/*;ressource/icon" --add-data="ressource/spellchecker/fr.json.gz;ressource/spellchecker" --icon=ressource/icon/icon.ico shadow_editor.py

Auteur  : Arnaud
Licence : CC BY-NC-ND 4.0
Version : 0.7.0
"""

# ---------------------------------------------------------------------------
# Imports standard
# ---------------------------------------------------------------------------
import ast
import operator
import os
import sys
from datetime import datetime

# ---------------------------------------------------------------------------
# Imports tiers
# ---------------------------------------------------------------------------
import pyttsx3                          # type: ignore  (pas de stubs)
import speech_recognition as sr         # type: ignore  (pas de stubs)
from spellchecker import SpellChecker   # type: ignore  (pas de stubs)

# ---------------------------------------------------------------------------
# Imports PySide6
# ---------------------------------------------------------------------------
from PySide6.QtCore import (
    QRegularExpression,
    Qt,
    QThread,
    Signal,
)
from PySide6.QtGui import (
    QAction,
    QColor,
    QFont,
    QIcon,
    QKeySequence,
    QSyntaxHighlighter,
    QTextCharFormat,
    QTextCursor,
    QTextListFormat,
)
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import (
    QApplication,
    QColorDialog,
    QDialog,
    QDockWidget,
    QFontComboBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QStatusBar,
    QTabWidget,
    QTextEdit,
    QFileDialog,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

# ---------------------------------------------------------------------------
# Imports locaux
# ---------------------------------------------------------------------------
from phrase_random import PhrasePlaceHolder  # type: ignore
from my_emoji import My_emoji, EmojiPickerDialog    # type: ignore
from ai_checker import (                     # type: ignore
    OllamaManager,
    GrammarWorker,
    SetupDialog,
    CorrectionPanel,
    OLLAMA_MODEL,
    MODEL_SIZE_DISPLAY,
)


# ===========================================================================
# Constantes
# ===========================================================================

APP_NAME    = "Shadow Text Editor"
APP_VERSION = "0.7.2"

# Styles des thèmes
DARK_STYLE  = "QTextEdit { background-color: rgb(23,23,23); color: white; }"
LIGHT_STYLE = "QTextEdit { background-color: #FFFFFF; color: #000000; }"

# Style supplémentaire pour le mode lecture (fond légèrement différent
# pour signaler visuellement que l'édition est désactivée)
READ_STYLE_DARK  = (
    "QTextEdit { background-color: rgb(30,30,40); color: #CCCCCC; "
    "border: 1px solid #444466; }"
)
READ_STYLE_LIGHT = (
    "QTextEdit { background-color: #F0F0F8; color: #222222; "
    "border: 1px solid #9999BB; }"
)

# Police système par défaut (remplace la police non licenciée de v0.5)
DEFAULT_FONT_NAME = "Segoe UI"
DEFAULT_FONT_SIZE = 11

# Identificateurs des trois modes d'édition
MODE_TEXT = "text"
MODE_CALC = "calc"
MODE_READ = "read"


# ===========================================================================
# Opérateurs autorisés pour l'évaluation mathématique sécurisée
# ===========================================================================

_SAFE_OPERATORS: dict = {
    ast.Add:  operator.add,
    ast.Sub:  operator.sub,
    ast.Mult: operator.mul,
    ast.Div:  operator.truediv,
    ast.Pow:  operator.pow,
    ast.Mod:  operator.mod,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


# ===========================================================================
# Classe : ShadowTextEdit
# Sous-classe de QTextEdit avec menu contextuel entièrement en français
# et intégration des suggestions du correcteur orthographique.
# ===========================================================================

class ShadowTextEdit(QTextEdit):
    """
    QTextEdit personnalisé pour Shadow Editor.

    Surcharge createStandardContextMenu() pour remplacer le menu
    contextuel Qt (en anglais) par un menu 100 % français.

    Le signal `spell_suggestion_requested` est émis quand l'utilisateur
    clique droit sur un mot fautif, afin que MainWindow puisse injecter
    les suggestions de correction en tête de menu.
    """

    # Signal émis avec (mot_fautif, position_globale) lors d'un clic droit
    # sur un mot identifié comme fautif par le correcteur orthographique.
    spell_suggestion_requested = Signal(str, object)

    def __init__(self, wrong_words_ref: list, parent=None) -> None:
        """
        Parameters
        ----------
        wrong_words_ref : list
            Référence mutable [set] partagée avec MainWindow.
            Index 0 contient le set des mots fautifs courants.
            Utiliser une liste comme conteneur mutable permet de partager
            la référence sans recréer l'objet à chaque vérification.
        """
        super().__init__(parent)
        # wrong_words_ref[0] est le set des mots fautifs (partagé avec MainWindow)
        self._wrong_words_ref = wrong_words_ref

    # ------------------------------------------------------------------
    # Menu contextuel français
    # ------------------------------------------------------------------

    def contextMenuEvent(self, event) -> None:
        """
        Construit et affiche un menu contextuel entièrement en français.

        Si le curseur est positionné sur un mot fautif, les suggestions
        de correction apparaissent en tête de menu avec un séparateur.
        Le reste du menu reprend les actions standard (annuler, copier…)
        traduites manuellement.
        """
        menu = QMenu(self)
        cursor = self.cursorForPosition(event.pos())

        # -- Suggestions orthographiques (uniquement si mot fautif) ------
        cursor.select(QTextCursor.SelectionType.WordUnderCursor)
        word = cursor.selectedText()
        wrong_words: set = self._wrong_words_ref[0]

        if word and word in wrong_words:
            # Sélectionner le mot fautif pour que la correction le remplace
            self.setTextCursor(cursor)

            # Titre non cliquable indiquant le mot
            header = QAction(f'Corrections pour "{word}"', self)
            header.setEnabled(False)
            menu.addAction(header)
            menu.addSeparator()

            # Récupérer et trier les suggestions
            from spellchecker import SpellChecker  # import local évite la circularité
            # On passe par le signal pour que MainWindow fournisse le correcteur
            self.spell_suggestion_requested.emit(word, event.globalPos())
            # Le signal est traité par MainWindow.
            # On ajoute un placeholder ; MainWindow remplace ce menu s'il répond.
            # => Architecture simplifiée : on construit le menu directement ici
            #    via la référence au correcteur injectée dans __init__.
            # (voir _inject_spell_checker ci-dessous)
            if hasattr(self, "_spell"):
                suggestions = sorted(self._spell.candidates(word) or [])
                if suggestions:
                    for sug in suggestions:
                        act = QAction(sug, self)
                        # Capture explicite de `sug` pour éviter le bug de closure
                        act.triggered.connect(
                            lambda checked=False, s=sug: self._replace_word(s)
                        )
                        menu.addAction(act)
                else:
                    no_sug = QAction("Aucune suggestion disponible", self)
                    no_sug.setEnabled(False)
                    menu.addAction(no_sug)

            menu.addSeparator()

        # -- Actions standard traduites ----------------------------------
        can_undo   = self.document().isUndoAvailable()
        can_redo   = self.document().isRedoAvailable()
        has_sel    = self.textCursor().hasSelection()
        clip_empty = QApplication.clipboard().text() == ""
        read_only  = self.isReadOnly()

        act_undo = QAction("Annuler", self)
        act_undo.setShortcut(QKeySequence.StandardKey.Undo)
        act_undo.setEnabled(can_undo and not read_only)
        act_undo.triggered.connect(self.undo)
        menu.addAction(act_undo)

        act_redo = QAction("Rétablir", self)
        act_redo.setShortcut(QKeySequence.StandardKey.Redo)
        act_redo.setEnabled(can_redo and not read_only)
        act_redo.triggered.connect(self.redo)
        menu.addAction(act_redo)

        menu.addSeparator()

        act_cut = QAction("Couper", self)
        act_cut.setShortcut(QKeySequence.StandardKey.Cut)
        act_cut.setEnabled(has_sel and not read_only)
        act_cut.triggered.connect(self.cut)
        menu.addAction(act_cut)

        act_copy = QAction("Copier", self)
        act_copy.setShortcut(QKeySequence.StandardKey.Copy)
        act_copy.setEnabled(has_sel)
        act_copy.triggered.connect(self.copy)
        menu.addAction(act_copy)

        act_paste = QAction("Coller", self)
        act_paste.setShortcut(QKeySequence.StandardKey.Paste)
        act_paste.setEnabled(not clip_empty and not read_only)
        act_paste.triggered.connect(self.paste)
        menu.addAction(act_paste)

        act_delete = QAction("Supprimer", self)
        act_delete.setEnabled(has_sel and not read_only)
        act_delete.triggered.connect(
            lambda: self.textCursor().removeSelectedText()
        )
        menu.addAction(act_delete)

        menu.addSeparator()

        act_select_all = QAction("Sélectionner tout", self)
        act_select_all.setShortcut(QKeySequence.StandardKey.SelectAll)
        act_select_all.triggered.connect(self.selectAll)
        menu.addAction(act_select_all)

        menu.exec(event.globalPos())

    def _replace_word(self, replacement: str) -> None:
        """Remplace le mot actuellement sélectionné par `replacement`."""
        cursor = self.textCursor()
        if cursor.hasSelection():
            cursor.insertText(replacement)
            self.setTextCursor(cursor)

    def _inject_spell_checker(self, spell: SpellChecker) -> None:
        """
        Injecte le correcteur orthographique depuis MainWindow.
        Doit être appelé juste après la création du widget.
        """
        self._spell = spell


# ===========================================================================
# Classe : WordHighlighter
# Souligne en rouge ondulé les mots identifiés comme mal orthographiés.
# ===========================================================================

class WordHighlighter(QSyntaxHighlighter):
    """
    Sous-classe de QSyntaxHighlighter qui souligne en rouge les mots
    présents dans `words` (ensemble des mots fautifs).
    """

    def __init__(self, document, words: set) -> None:
        super().__init__(document)
        self.words: set = words
        self._error_format = QTextCharFormat()
        self._error_format.setUnderlineColor(QColor("red"))
        self._error_format.setUnderlineStyle(
            QTextCharFormat.UnderlineStyle.SpellCheckUnderline
        )

    def update_words(self, words: set) -> None:
        """Met à jour la liste de mots fautifs et relance le surlignage."""
        self.words = words
        self.rehighlight()

    def highlightBlock(self, text: str) -> None:
        """Appelé automatiquement par Qt pour chaque bloc de texte."""
        for word in self.words:
            expression = QRegularExpression(
                f"\\b{QRegularExpression.escape(word)}\\b"
            )
            it = expression.globalMatch(text)
            while it.hasNext():
                match = it.next()
                self.setFormat(
                    match.capturedStart(),
                    match.capturedLength(),
                    self._error_format,
                )


# ===========================================================================
# Classe : VoiceTypingWorker
# Thread dédié à la reconnaissance vocale (Speech-to-Text).
# ===========================================================================

class VoiceTypingWorker(QThread):
    """
    Worker QThread pour la dictée vocale Google.
    Émet `result_ready` avec le texte reconnu, ou `error_occurred` en cas
    d'échec.
    """

    result_ready   = Signal(str)
    error_occurred = Signal(str)

    def run(self) -> None:
        """Corps du thread : écoute le micro et envoie le résultat."""
        recognizer = sr.Recognizer()
        try:
            with sr.Microphone() as source:
                audio = recognizer.listen(source, timeout=8, phrase_time_limit=15)
            text = recognizer.recognize_google(audio, language="fr-FR")  # type: ignore[attr-defined]
            self.result_ready.emit(text)
        except sr.WaitTimeoutError:
            self.error_occurred.emit("⚠️ Aucune parole détectée (timeout).")
        except sr.UnknownValueError:
            self.error_occurred.emit("⚠️ Parole non reconnue.")
        except sr.RequestError as exc:
            self.error_occurred.emit(f"⚠️ Erreur service Google : {exc}")
        except Exception as exc:  # noqa: BLE001
            self.error_occurred.emit(f"⚠️ Erreur microphone : {exc}")


# ===========================================================================
# Classe : TtsWorker
# Thread dédié à la synthèse vocale (Text-to-Speech).
# ===========================================================================

class TtsWorker(QThread):
    """
    Worker QThread pour la lecture de texte à haute voix (pyttsx3).
    Évite de bloquer l'interface pendant la lecture.
    """

    error_occurred = Signal(str)

    def __init__(self, text: str, parent=None) -> None:
        super().__init__(parent)
        self._text = text

    def run(self) -> None:
        """Corps du thread : lit le texte avec pyttsx3."""
        try:
            engine = pyttsx3.init()
            engine.say(self._text)
            engine.runAndWait()
        except RuntimeError as exc:
            self.error_occurred.emit(f"⚠️ Lecture vocale : {exc}")
        except Exception as exc:  # noqa: BLE001
            self.error_occurred.emit(f"⚠️ Erreur TTS : {exc}")


# ===========================================================================
# Classe : CreditsDialog
# ===========================================================================

class CreditsDialog(QDialog):
    """Boîte de dialogue modale pour les crédits du logiciel."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Crédits")
        self.setFixedSize(600, 380)

        layout = QVBoxLayout(self)
        text_area = QTextEdit()
        text_area.setReadOnly(True)
        text_area.setMarkdown(
            "## Crédits — Shadow Text Editor\n\n"
            "### Développement\n"
            "Développé par **Arnaud** en Python avec PySide6.\n\n"
            "### Technologies utilisées\n"
            "- **Python** — python.org\n"
            "- **PySide6** — qt.io\n"
            "- **pyspellchecker** — github.com/barrust/pyspellchecker\n"
            "- **pyttsx3** — synthèse vocale hors-ligne\n"
            "- **SpeechRecognition** — reconnaissance vocale\n"
            "- **FlatIcon** — icônes UI\n\n"
            "### Licence\n"
            "CC BY-NC-ND 4.0 — Usage personnel et éducatif uniquement.\n\n"
            "---\nDéveloppé avec ❤️"
        )
        layout.addWidget(text_area)

        close_btn = QPushButton("Fermer")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)


# ===========================================================================
# Classe : HelpDialog
# ===========================================================================

class HelpDialog(QDialog):
    """Boîte de dialogue modale affichant l'aide et les raccourcis."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Aide — Raccourcis clavier")
        self.setFixedSize(500, 460)

        layout = QVBoxLayout(self)
        text_area = QTextEdit()
        text_area.setReadOnly(True)
        text_area.setMarkdown(
            "## Raccourcis clavier\n\n"
            "| Action | Raccourci |\n"
            "|---|---|\n"
            "| Nouveau fichier | Ctrl+N |\n"
            "| Ouvrir | Ctrl+O |\n"
            "| Enregistrer | Ctrl+S |\n"
            "| Enregistrer sous | Ctrl+Shift+S |\n"
            "| Imprimer | Ctrl+P |\n"
            "| Quitter | Ctrl+Q |\n"
            "| Annuler | Ctrl+Z |\n"
            "| Rétablir | Ctrl+Y |\n"
            "| Sélectionner tout | Ctrl+A |\n"
            "| Barre d'outils | Ctrl+T |\n"
            "| Shadow Assistant | F2 |\n"
            "| Lire le texte | F3 |\n"
            "| Dictée vocale Google | F4 |\n"
            "| Dictée vocale Microsoft | F5 |\n"
            "| Correcteur orthographique (basique) | F6 |\n"
            "| Correcteur IA — ministral-3:3b | F7 |\n"
            "| Sélecteur d'émojis | Ctrl+E |\n\n"
            "## Emojis (300+ disponibles)\n"
            "Tapez un code suivi d'un espace pour insérer automatiquement.\n"
            "Ou ouvrez le sélecteur avec **Ctrl+E** pour parcourir par catégorie.\n\n"
            "Exemples : `:coeur` `:feu` `:ok` `:muscle` `:sourire` `:drapeau_fr`\n"
            "`:chien` `:pizza` `:fusee` `:attention` `:coeur_brise` `:yeux_etoile`"
        )
        layout.addWidget(text_area)
        close_btn = QPushButton("Fermer")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)


# ===========================================================================
# Classe : MainWindow
# ===========================================================================

class MainWindow(QMainWindow):
    """
    Fenêtre principale du Shadow Text Editor.

    Architecture :
      - __init__           : initialise l'état puis délègue à _init_*
      - _init_state        : variables d'instance
      - _init_ui           : widgets centraux (onglets)
      - _init_status_bar   : barre de statut
      - _init_menus        : barre de menus complète
      - _init_toolbar      : barre d'outils de formatage
      - Slots              : méthodes reliées aux signaux Qt
    """

    # -----------------------------------------------------------------------
    # Initialisation
    # -----------------------------------------------------------------------

    def __init__(self) -> None:
        super().__init__()

        self._init_state()
        self._init_ui()
        self._init_status_bar()
        self._init_menus()
        self._init_toolbar()

        # Premier onglet créé après que tous les widgets existent
        self.add_new_tab()

        # Mode texte activé par défaut
        self.set_text_mode()

        # Panneau de corrections IA (dock latéral, masqué par défaut)
        self._init_correction_dock()

    # -- État interne --------------------------------------------------------

    def _init_state(self) -> None:
        """Initialise toutes les variables d'instance de l'application."""

        self.setWindowTitle(f"{APP_NAME} - v{APP_VERSION}")
        self.setWindowIcon(QIcon(self.resource_path("ressource/icon/note_icon.png")))
        self.setGeometry(100, 100, 900, 650)
        self.setMinimumSize(500, 450)

        # Correcteur orthographique (dictionnaire français)
        self.spell = SpellChecker(
            local_dictionary=self.resource_path("ressource/spellchecker/fr.json.gz")
        )

        # Conteneur mutable [set] partagé avec chaque ShadowTextEdit.
        # wrong_words_ref[0] est mis à jour à chaque vérification.
        self._wrong_words_ref: list = [set()]

        # Highlighter orthographique (recréé à chaque onglet si besoin)
        self._highlighter: WordHighlighter | None = None

        # Mode actif : MODE_TEXT | MODE_CALC | MODE_READ
        self._current_mode: str = MODE_TEXT

        # Workers threads (gardés en référence pour éviter le GC)
        self._voice_worker: VoiceTypingWorker | None = None
        self._tts_worker:   TtsWorker | None = None

        # Worker de correction IA (GrammarWorker)
        self._grammar_worker: GrammarWorker | None = None

        # Thème courant (pour l'appliquer correctement en mode lecture)
        self._current_theme_style: str = DARK_STYLE

    # -- Interface principale ------------------------------------------------

    def _init_ui(self) -> None:
        """Crée le widget central : QTabWidget avec onglets fermables."""

        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self._on_tab_changed)

        plus_btn = QPushButton("+")
        plus_btn.setFixedSize(26, 26)
        plus_btn.setToolTip("Nouvel onglet")
        plus_btn.clicked.connect(self.add_new_tab)

        corner_widget = QWidget()
        hbox = QHBoxLayout(corner_widget)
        hbox.addStretch()
        hbox.addWidget(plus_btn)
        hbox.setContentsMargins(0, 0, 4, 0)

        self.tabs.setCornerWidget(corner_widget, Qt.Corner.TopRightCorner)
        self.setCentralWidget(self.tabs)

    # -- Barre de statut -----------------------------------------------------

    def _init_status_bar(self) -> None:
        """Crée et configure la barre de statut en bas de la fenêtre."""

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        font = QFont(DEFAULT_FONT_NAME, 8)

        self._label_line  = QLabel("Ligne : 1")
        self._label_col   = QLabel("Col : 1")
        self._label_chars = QLabel("Caractères : 0")
        self._label_words = QLabel("Mots : 0")

        for lbl in (self._label_line, self._label_col,
                    self._label_chars, self._label_words):
            lbl.setFont(font)
            self.status_bar.addPermanentWidget(lbl)

    # -- Menus ---------------------------------------------------------------

    def _init_menus(self) -> None:
        """Construit l'ensemble de la barre de menus."""

        menu_bar = self.menuBar()
        self._build_file_menu(menu_bar)
        self._build_edit_menu(menu_bar)
        self._build_assistant_menu(menu_bar)
        self._build_display_menu(menu_bar)
        self._build_preference_menu(menu_bar)
        self._build_about_menu(menu_bar)

    def _build_file_menu(self, menu_bar) -> None:
        """Menu Fichier."""
        menu = menu_bar.addMenu("Fichier")
        self._add_action(menu, "Nouveau",          "new_file.png",    QKeySequence.StandardKey.New,    self.add_new_tab)
        self._add_action(menu, "Ouvrir",           "folder_open.png", QKeySequence.StandardKey.Open,   self.open_file)
        menu.addSeparator()
        self._add_action(menu, "Enregistrer",      "save.png",        QKeySequence.StandardKey.Save,   self.save_file)
        self._add_action(menu, "Enregistrer sous", "save.png",        QKeySequence.StandardKey.SaveAs, self.save_file_as)
        menu.addSeparator()
        self._add_action(menu, "Imprimer",         "printer.png",     QKeySequence("Ctrl+P"),           self.print_document)
        menu.addSeparator()
        self._add_action(menu, "Quitter",          "power-off.png",   QKeySequence("Ctrl+Q"),           self.close)

    def _build_edit_menu(self, menu_bar) -> None:
        """Menu Modifier."""
        menu = menu_bar.addMenu("Modifier")
        self._add_action(menu, "Annuler",              "undo.png",   QKeySequence.StandardKey.Undo,      self._undo)
        self._add_action(menu, "Rétablir",             "redo.png",   QKeySequence.StandardKey.Redo,      self._redo)
        menu.addSeparator()
        self._add_action(menu, "Sélectionner tout",    "select.png", QKeySequence.StandardKey.SelectAll, self._select_all)
        menu.addSeparator()
        self._add_action(menu, "Copier",               "copy.png",   QKeySequence.StandardKey.Copy,      self._copy)
        self._add_action(menu, "Couper",               "cut.png",    QKeySequence.StandardKey.Cut,       self._cut)
        self._add_action(menu, "Coller",               "paste.png",  QKeySequence.StandardKey.Paste,     self._paste)
        menu.addSeparator()
        self._add_action(menu, "Effacer la sélection", "eraser.png", QKeySequence.StandardKey.Delete,    self.delete_selection)
        self._add_action(menu, "Effacer tout",         "eraser.png", QKeySequence("Ctrl+Shift+Delete"),  self.clear_all)

    def _build_assistant_menu(self, menu_bar) -> None:
        """Menu Assistant."""
        menu = menu_bar.addMenu("Assistant")
        self._add_action(menu, "Shadow Assistant",        "chatbot.png",   QKeySequence("F2"), self.call_shadow_assistant)
        self._add_action(menu, "Lire le texte",           "talk.png",      QKeySequence("F3"), self.start_voice_reading)
        self._add_action(menu, "Dictée vocale Google",    "google.png",    QKeySequence("F4"), self.start_voice_typing)
        self._add_action(menu, "Dictée vocale Microsoft", "microsoft.png", QKeySequence("F5"), self.start_voice_typing_ms)
        menu.addSeparator()
        self._add_action(menu, "Correcteur orthographique (basique)", None, QKeySequence("F6"), self.check_spelling)
        self._add_action(menu, f"Correcteur IA — {OLLAMA_MODEL}",     None, QKeySequence("F7"), self.run_ai_grammar_check)
        menu.addSeparator()
        self._add_action(menu, "Sélecteur d'émojis",                  None, QKeySequence("Ctrl+E"), self.open_emoji_picker)

    def _build_display_menu(self, menu_bar) -> None:
        """Menu Affichage."""
        menu = menu_bar.addMenu("Affichage")

        self._toolbar_action = QAction(
            QIcon(self.resource_path("ressource/icon/tool.png")),
            "Barre d'outils", self
        )
        self._toolbar_action.setShortcut(QKeySequence("Ctrl+T"))
        self._toolbar_action.setCheckable(True)
        self._toolbar_action.setChecked(False)
        self._toolbar_action.triggered.connect(self.toggle_toolbar)
        menu.addAction(self._toolbar_action)

        menu.addSeparator()

        theme_menu = QMenu("Thème", self)
        theme_menu.setIcon(QIcon(self.resource_path("ressource/icon/theme.png")))
        self._add_action(theme_menu, "Mode Sombre", "dark.png", None, self.set_dark_theme)
        self._add_action(theme_menu, "Mode Clair",  "sun.png",  None, self.set_light_theme)
        menu.addMenu(theme_menu)

    def _build_preference_menu(self, menu_bar) -> None:
        """Menu Préférence — contient le sous-menu Mode (Texte / Calcul / Lecture)."""
        menu = menu_bar.addMenu("Préférence")

        mode_menu = QMenu("Mode", self)
        mode_menu.setIcon(QIcon(self.resource_path("ressource/icon/mode.png")))

        # Action Mode Texte
        self._text_mode_action = QAction(
            QIcon(self.resource_path("ressource/icon/text.png")), "Mode Texte", self
        )
        self._text_mode_action.setCheckable(True)
        self._text_mode_action.triggered.connect(self.set_text_mode)

        # Action Mode Calcul
        self._calc_mode_action = QAction(
            QIcon(self.resource_path("ressource/icon/calculatrice.png")), "Mode Calcul", self
        )
        self._calc_mode_action.setCheckable(True)
        self._calc_mode_action.triggered.connect(self.set_calc_mode)

        # Action Mode Lecture (nouveau)
        self._read_mode_action = QAction(
            QIcon(self.resource_path("ressource/icon/aa.png")), "Mode Lecture", self
        )
        self._read_mode_action.setCheckable(True)
        self._read_mode_action.triggered.connect(self.set_read_mode)

        mode_menu.addAction(self._text_mode_action)
        mode_menu.addAction(self._calc_mode_action)
        mode_menu.addAction(self._read_mode_action)
        menu.addMenu(mode_menu)

    def _build_about_menu(self, menu_bar) -> None:
        """Menu ? (Aide, Infos, Crédits)."""
        menu = menu_bar.addMenu("?")
        self._add_action(menu, "Aide",         "question.png", QKeySequence("F1"),     self.show_help)
        self._add_action(menu, "Informations", "info.png",     QKeySequence("Ctrl+I"), self.show_info)
        self._add_action(menu, "Crédits",      "credit.png",   None,                   self.show_credits)

    # -- Barre d'outils ------------------------------------------------------

    def _init_toolbar(self) -> None:
        """Crée la barre d'outils de formatage (masquée par défaut)."""

        self.toolbar = QToolBar("Outils de formatage")
        self.addToolBar(self.toolbar)
        self.toolbar.hide()

        # Alignement — utilise des helpers dédiés pour éviter les lambdas sur None
        self._add_tool(self.toolbar, "align-left.png",   "Aligner à gauche",   self._align_left)
        self._add_tool(self.toolbar, "align-center.png", "Aligner au centre",  self._align_center)
        self._add_tool(self.toolbar, "align-right.png",  "Aligner à droite",   self._align_right)
        self.toolbar.addSeparator()

        # Listes
        self._add_tool(self.toolbar, "bullet.png", "Ajouter une puce", self.add_bullet_list)
        self.toolbar.addSeparator()

        # Formatage de caractères
        self._action_underline = self._add_tool(self.toolbar, "underline-text.png", "Souligner",  self.toggle_underline, checkable=True)
        self._action_bold      = self._add_tool(self.toolbar, "bold-text.png",      "Gras",       self.toggle_bold,      checkable=True)
        self._action_italic    = self._add_tool(self.toolbar, "italic-text.png",    "Italique",   self.toggle_italic,    checkable=True)
        self._action_strikeout = self._add_tool(self.toolbar, "text_barre.png",     "Barré",      self.toggle_strikeout, checkable=True)
        self.toolbar.addSeparator()

        # Couleur
        self._add_tool(self.toolbar, "color.png", "Sélecteur de couleur", self.change_color)
        color_btn = QPushButton("Couleur")
        color_btn.setMenu(self._build_color_menu())
        self.toolbar.addWidget(color_btn)
        self.toolbar.addSeparator()

        # Taille de police
        self._font_size_spin = QSpinBox()
        self._font_size_spin.setRange(7, 100)
        self._font_size_spin.setValue(DEFAULT_FONT_SIZE)
        self._font_size_spin.setToolTip("Taille de la police")
        self._font_size_spin.valueChanged.connect(self.set_font_size)
        self.toolbar.addWidget(self._font_size_spin)

        # Famille de police
        self._font_combo = QFontComboBox()
        self._font_combo.setCurrentFont(QFont(DEFAULT_FONT_NAME))
        self._font_combo.setToolTip("Police")
        self._font_combo.currentFontChanged.connect(self.change_font)
        self.toolbar.addWidget(self._font_combo)

    # -----------------------------------------------------------------------
    # Helpers internes
    # -----------------------------------------------------------------------

    @staticmethod
    def resource_path(relative_path: str) -> str:
        """
        Retourne le chemin absolu vers une ressource.
        Compatible PyInstaller (_MEIPASS) et mode développement.
        """
        base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base, relative_path)

    def _add_action(self, menu, label: str, icon_name: str | None,
                    shortcut, slot) -> QAction:
        """Crée une QAction et l'ajoute au menu donné."""
        if icon_name:
            action = QAction(
                QIcon(self.resource_path(f"ressource/icon/{icon_name}")), label, self
            )
        else:
            action = QAction(label, self)
        if shortcut is not None:
            action.setShortcut(shortcut)
        action.triggered.connect(slot)
        menu.addAction(action)
        return action

    def _add_tool(self, toolbar: QToolBar, icon_name: str, tooltip: str,
                  slot, checkable: bool = False) -> QAction:
        """Crée une QAction et l'ajoute à la barre d'outils."""
        action = QAction(
            QIcon(self.resource_path(f"ressource/icon/{icon_name}")), tooltip, self
        )
        action.setCheckable(checkable)
        action.triggered.connect(slot)
        toolbar.addAction(action)
        return action

    def _build_color_menu(self) -> QMenu:
        """Construit le menu de couleurs prédéfinies."""
        menu = QMenu(self)
        colors = {
            "Noir":    Qt.GlobalColor.black,
            "Blanc":   Qt.GlobalColor.white,
            "Rouge":   Qt.GlobalColor.red,
            "Vert":    Qt.GlobalColor.green,
            "Bleu":    Qt.GlobalColor.blue,
            "Jaune":   Qt.GlobalColor.yellow,
            "Cyan":    Qt.GlobalColor.cyan,
            "Magenta": Qt.GlobalColor.magenta,
            "Gris":    Qt.GlobalColor.gray,
        }
        for name, color_val in colors.items():
            act = QAction(name, self)
            act.triggered.connect(
                lambda checked=False, c=color_val: self.apply_color(c)
            )
            menu.addAction(act)
        return menu

    def _current_editor(self) -> "ShadowTextEdit | None":
        """
        Retourne le ShadowTextEdit de l'onglet actif, ou None si l'onglet
        actif n'est pas un éditeur.
        """
        widget = self.tabs.currentWidget()
        return widget if isinstance(widget, ShadowTextEdit) else None

    def _editor_at(self, index: int) -> "ShadowTextEdit | None":
        """Retourne le ShadowTextEdit à l'index donné, ou None."""
        widget = self.tabs.widget(index)
        return widget if isinstance(widget, ShadowTextEdit) else None

    # -----------------------------------------------------------------------
    # Gestion des onglets
    # -----------------------------------------------------------------------

    def add_new_tab(self, title: str = "") -> "ShadowTextEdit":
        """
        Crée un nouvel onglet avec un ShadowTextEdit vide et le retourne.
        Le chemin de fichier et le flag de modification sont stockés
        comme propriétés Qt sur le widget.
        """
        editor = ShadowTextEdit(self._wrong_words_ref)
        editor._inject_spell_checker(self.spell)
        editor.setFont(QFont(DEFAULT_FONT_NAME, DEFAULT_FONT_SIZE))
        editor.setStyleSheet(DARK_STYLE)

        # Phrase d'accroche aléatoire
        editor.setPlaceholderText(PhrasePlaceHolder().get_random_phrase())

        # Métadonnées de l'onglet
        editor.setProperty("file_path", None)       # chemin enregistré
        editor.setProperty("is_modified", False)    # modifié depuis le dernier enregistrement

        # Appliquer le mode en cours (lecture seule si mode lecture)
        editor.setReadOnly(self._current_mode == MODE_READ)
        if self._current_mode == MODE_READ:
            editor.setStyleSheet(READ_STYLE_DARK)

        # Connexions des signaux
        editor.textChanged.connect(self._on_text_changed)
        editor.cursorPositionChanged.connect(self._update_cursor_position)

        # Insertion dans le tab widget
        tab_index = self.tabs.count()
        label = title if title else f"Sans titre {tab_index}"
        self.tabs.insertTab(tab_index, editor, label)
        self.tabs.setCurrentIndex(tab_index)

        return editor

    def close_tab(self, index: int) -> None:
        """
        Ferme l'onglet à l'index donné.

        Le dialogue de sauvegarde n'est proposé QUE si le document a été
        modifié depuis son dernier enregistrement (flag is_modified).
        Un onglet vierge (jamais touché) se ferme sans question.
        """
        editor = self._editor_at(index)
        if editor is None:
            return

        is_modified: bool = editor.property("is_modified") or False

        if is_modified:
            reply = self._ask_save_before_close()
            if reply == QMessageBox.StandardButton.Yes:
                # Sauvegarder avant de fermer
                self.tabs.setCurrentIndex(index)
                self.save_file()
                self.tabs.removeTab(index)
            elif reply == QMessageBox.StandardButton.No:
                self.tabs.removeTab(index)
            # Cancel → on ne ferme pas
        else:
            # Pas de modification → fermeture directe
            self.tabs.removeTab(index)

        # Toujours au moins un onglet ouvert
        if self.tabs.count() == 0:
            self.add_new_tab()

    def _on_tab_changed(self, index: int) -> None:
        """
        Appelé quand l'utilisateur change d'onglet.
        Met à jour la barre de statut et relie le highlighter au bon document.
        """
        editor = self._editor_at(index)
        if editor is not None:
            self._update_status_bar()
            self._update_cursor_position()
            # Reattacher le highlighter au document du nouvel onglet
            if self._wrong_words_ref[0] and self._highlighter is not None:
                self._highlighter = WordHighlighter(
                    editor.document(), self._wrong_words_ref[0]
                )

    # -----------------------------------------------------------------------
    # Gestion du flag is_modified
    # -----------------------------------------------------------------------

    def _mark_modified(self, editor: "ShadowTextEdit") -> None:
        """
        Marque un onglet comme modifié et ajoute un astérisque au titre
        de l'onglet pour signaler visuellement la modification.
        """
        if editor.property("is_modified"):
            return  # déjà marqué

        editor.setProperty("is_modified", True)
        index = self.tabs.indexOf(editor)
        if index >= 0:
            current_title = self.tabs.tabText(index)
            if not current_title.endswith(" *"):
                self.tabs.setTabText(index, current_title + " *")

    def _mark_saved(self, editor: "ShadowTextEdit", file_path: str) -> None:
        """
        Marque un onglet comme enregistré (efface le flag et l'astérisque).
        """
        editor.setProperty("is_modified", False)
        editor.setProperty("file_path", file_path)
        index = self.tabs.indexOf(editor)
        if index >= 0:
            # Titre = nom du fichier sans astérisque
            self.tabs.setTabText(index, os.path.basename(file_path))

    # -----------------------------------------------------------------------
    # Slots — barre de statut
    # -----------------------------------------------------------------------

    def _on_text_changed(self) -> None:
        """Appelé à chaque modification du texte dans l'onglet actif."""
        self._update_status_bar()
        self._check_emoji()
        self._detect_calculation()

        # Marquer l'onglet comme modifié
        editor = self._current_editor()
        if editor is not None:
            self._mark_modified(editor)

    def _update_status_bar(self) -> None:
        """Met à jour les compteurs de caractères et de mots."""
        editor = self._current_editor()
        if editor is None:
            return
        text = editor.toPlainText()
        self._label_chars.setText(f"Caractères : {len(text)}")
        self._label_words.setText(f"Mots : {len(text.split()) if text.strip() else 0}")

    def _update_cursor_position(self) -> None:
        """Met à jour l'affichage de la ligne et de la colonne."""
        editor = self._current_editor()
        if editor is None:
            return
        cursor = editor.textCursor()
        self._label_line.setText(f"Ligne : {cursor.blockNumber() + 1}")
        self._label_col.setText(f"Col : {cursor.columnNumber() + 1}")

    # -----------------------------------------------------------------------
    # Slots — délégation vers l'onglet actif (edit menu)
    # -----------------------------------------------------------------------

    def _undo(self)       -> None:
        editor = self._current_editor()
        if editor: editor.undo()

    def _redo(self)       -> None:
        editor = self._current_editor()
        if editor: editor.redo()

    def _select_all(self) -> None:
        editor = self._current_editor()
        if editor: editor.selectAll()

    def _copy(self)       -> None:
        editor = self._current_editor()
        if editor: editor.copy()

    def _cut(self)        -> None:
        editor = self._current_editor()
        if editor: editor.cut()

    def _paste(self)      -> None:
        editor = self._current_editor()
        if editor: editor.paste()

    def delete_selection(self) -> None:
        """Supprime le texte sélectionné dans l'onglet actif."""
        editor = self._current_editor()
        if editor:
            editor.textCursor().removeSelectedText()
            self.status_bar.showMessage("Sélection supprimée.", 3000)

    def clear_all(self) -> None:
        """Efface tout le contenu de l'onglet actif."""
        editor = self._current_editor()
        if editor:
            editor.clear()
            self.status_bar.showMessage("Texte effacé.", 3000)

    # -----------------------------------------------------------------------
    # Slots — Fichier
    # -----------------------------------------------------------------------

    def open_file(self) -> None:
        """Ouvre un fichier dans un nouvel onglet."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Ouvrir un fichier", "",
            "Fichiers texte (*.txt);;Tous les fichiers (*)"
        )
        if not file_path:
            return

        content = self._read_file_safe(file_path)
        if content is None:
            QMessageBox.critical(
                self, "Erreur",
                f"Impossible de lire le fichier :\n{file_path}"
            )
            return

        editor = self.add_new_tab(title=os.path.basename(file_path))
        # Bloquer temporairement le signal textChanged pour éviter de marquer
        # l'onglet comme "modifié" lors du chargement initial
        editor.blockSignals(True)
        editor.setPlainText(content)
        editor.blockSignals(False)

        # Marquer comme NON modifié (vient d'être chargé)
        editor.setProperty("file_path", file_path)
        editor.setProperty("is_modified", False)

        index = self.tabs.currentIndex()
        self.tabs.setTabText(index, os.path.basename(file_path))
        self._update_status_bar()

    def save_file(self) -> None:
        """
        Enregistre l'onglet actif dans son fichier associé.
        Si aucun fichier n'est encore associé, délègue à save_file_as().
        """
        editor = self._current_editor()
        if editor is None:
            return

        file_path = editor.property("file_path")
        if file_path:
            self._write_file(editor, file_path)
        else:
            self.save_file_as()

    def save_file_as(self) -> None:
        """Ouvre la boîte de dialogue et enregistre dans un nouveau fichier."""
        editor = self._current_editor()
        if editor is None:
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Enregistrer le fichier", "",
            "Fichiers texte (*.txt);;Tous les fichiers (*)"
        )
        if not file_path:
            return

        self._write_file(editor, file_path)

    def _write_file(self, editor: "ShadowTextEdit", file_path: str) -> None:
        """Écrit le contenu dans le fichier, met à jour le titre et le flag."""
        try:
            with open(file_path, "w", encoding="utf-8") as fh:
                fh.write(editor.toPlainText())
            # Réinitialiser le flag de modification
            self._mark_saved(editor, file_path)
            stamp = datetime.now().strftime("Enregistré le %d/%m/%Y à %Hh%M")
            self.status_bar.showMessage(stamp, 5000)
        except OSError as exc:
            QMessageBox.critical(self, "Erreur d'enregistrement", str(exc))

    @staticmethod
    def _read_file_safe(file_path: str) -> "str | None":
        """Lit un fichier en essayant UTF-8 puis Latin-1."""
        for encoding in ("utf-8", "latin-1"):
            try:
                with open(file_path, "r", encoding=encoding) as fh:
                    return fh.read()
            except UnicodeDecodeError:
                continue
            except OSError:
                return None
        return None

    def print_document(self) -> None:
        """Ouvre la boîte de dialogue d'impression."""
        editor = self._current_editor()
        if editor is None:
            return
        printer = QPrinter()
        dialog = QPrintDialog(printer, self)
        if dialog.exec() == QPrintDialog.DialogCode.Accepted:
            editor.print_(printer)

    # -----------------------------------------------------------------------
    # Slots — Formatage de texte
    # -----------------------------------------------------------------------

    def _apply_format(self, fmt: QTextCharFormat) -> None:
        """Applique un QTextCharFormat à la sélection ou au curseur courant."""
        editor = self._current_editor()
        if editor is None:
            return
        cursor = editor.textCursor()
        if cursor.hasSelection():
            cursor.mergeCharFormat(fmt)
        else:
            editor.mergeCurrentCharFormat(fmt)

    def toggle_bold(self) -> None:
        """Bascule le gras sur la sélection."""
        editor = self._current_editor()
        if editor is None:
            return
        fmt = QTextCharFormat()
        current = editor.textCursor().charFormat().fontWeight()
        fmt.setFontWeight(
            QFont.Weight.Normal if current == QFont.Weight.Bold else QFont.Weight.Bold
        )
        self._apply_format(fmt)

    def toggle_italic(self) -> None:
        """Bascule l'italique sur la sélection."""
        editor = self._current_editor()
        if editor is None:
            return
        fmt = QTextCharFormat()
        fmt.setFontItalic(not editor.textCursor().charFormat().fontItalic())
        self._apply_format(fmt)

    def toggle_underline(self) -> None:
        """Bascule le soulignement sur la sélection."""
        editor = self._current_editor()
        if editor is None:
            return
        fmt = QTextCharFormat()
        fmt.setFontUnderline(not editor.textCursor().charFormat().fontUnderline())
        self._apply_format(fmt)

    def toggle_strikeout(self) -> None:
        """Bascule le texte barré sur la sélection."""
        editor = self._current_editor()
        if editor is None:
            return
        fmt = QTextCharFormat()
        fmt.setFontStrikeOut(not editor.textCursor().charFormat().fontStrikeOut())
        self._apply_format(fmt)

    def change_font(self, font: QFont) -> None:
        """Change la police pour la sélection ou les prochains caractères."""
        fmt = QTextCharFormat()
        fmt.setFont(font)
        self._apply_format(fmt)

    def set_font_size(self, size: int) -> None:
        """Change la taille de police."""
        fmt = QTextCharFormat()
        fmt.setFontPointSize(float(size))
        self._apply_format(fmt)

    def apply_color(self, color) -> None:
        """Applique une couleur prédéfinie."""
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        self._apply_format(fmt)

    def change_color(self) -> None:
        """Ouvre le sélecteur de couleur et applique la couleur choisie."""
        editor = self._current_editor()
        if editor is None:
            return
        color = QColorDialog.getColor(parent=self)
        if color.isValid():
            fmt = QTextCharFormat()
            fmt.setForeground(color)
            self._apply_format(fmt)

    def add_bullet_list(self) -> None:
        """Insère une liste à puces."""
        editor = self._current_editor()
        if editor is None:
            return
        list_fmt = QTextListFormat()
        list_fmt.setStyle(QTextListFormat.Style.ListDisc)
        editor.textCursor().createList(list_fmt)

    def _align_left(self) -> None:
        """Aligne le texte à gauche dans l'onglet actif."""
        editor = self._current_editor()
        if editor is not None:
            editor.setAlignment(Qt.AlignmentFlag.AlignLeft)

    def _align_center(self) -> None:
        """Aligne le texte au centre dans l'onglet actif."""
        editor = self._current_editor()
        if editor is not None:
            editor.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def _align_right(self) -> None:
        """Aligne le texte à droite dans l'onglet actif."""
        editor = self._current_editor()
        if editor is not None:
            editor.setAlignment(Qt.AlignmentFlag.AlignRight)

    # -----------------------------------------------------------------------
    # Slots — Affichage / Thèmes
    # -----------------------------------------------------------------------

    def toggle_toolbar(self) -> None:
        """Affiche ou masque la barre d'outils."""
        if self.toolbar.isVisible():
            self.toolbar.hide()
        else:
            self.toolbar.show()

    def set_dark_theme(self) -> None:
        """Applique le thème sombre à tous les onglets."""
        self._current_theme_style = DARK_STYLE
        self._apply_theme_to_all()
        self.status_bar.showMessage("Mode sombre activé.", 3000)

    def set_light_theme(self) -> None:
        """Applique le thème clair à tous les onglets."""
        self._current_theme_style = LIGHT_STYLE
        self._apply_theme_to_all()
        self.status_bar.showMessage("Mode clair activé.", 3000)

    def _apply_theme_to_all(self) -> None:
        """
        Applique le stylesheet correct à tous les onglets en tenant
        compte du mode courant (le mode lecture a son propre style).
        """
        for i in range(self.tabs.count()):
            widget = self.tabs.widget(i)
            if isinstance(widget, ShadowTextEdit):
                if self._current_mode == MODE_READ:
                    # En mode lecture, on utilise le style lecture
                    style = (
                        READ_STYLE_DARK
                        if self._current_theme_style == DARK_STYLE
                        else READ_STYLE_LIGHT
                    )
                else:
                    style = self._current_theme_style
                widget.setStyleSheet(style)

    # -----------------------------------------------------------------------
    # Slots — Modes (Texte / Calcul / Lecture)
    # -----------------------------------------------------------------------

    def set_text_mode(self) -> None:
        """
        Active le mode texte : édition normale, sans calcul automatique.
        Réactive l'édition si on sort du mode lecture.
        """
        self._current_mode = MODE_TEXT

        # Mettre à jour les cases à cocher du menu
        self._text_mode_action.setChecked(True)
        self._calc_mode_action.setChecked(False)
        self._read_mode_action.setChecked(False)

        # Réactiver l'édition sur tous les onglets
        self._set_all_editors_read_only(False)

        # Restaurer le thème normal
        self._apply_theme_to_all()

        self.status_bar.showMessage("Mode texte activé.", 2000)

    def set_calc_mode(self) -> None:
        """
        Active le mode calcul : une ligne terminée par '=' est évaluée
        automatiquement et le résultat est inséré à la suite.
        """
        self._current_mode = MODE_CALC

        self._text_mode_action.setChecked(False)
        self._calc_mode_action.setChecked(True)
        self._read_mode_action.setChecked(False)

        # Le mode calcul reste éditable
        self._set_all_editors_read_only(False)
        self._apply_theme_to_all()

        self.status_bar.showMessage(
            "Mode calcul activé. Terminez une ligne par '=' pour calculer.", 3000
        )

    def set_read_mode(self) -> None:
        """
        Active le mode lecture : le texte est figé en lecture seule.
        L'utilisateur peut lire et copier mais pas modifier.
        Le style visuel change légèrement pour signaler cet état.
        """
        self._current_mode = MODE_READ

        self._text_mode_action.setChecked(False)
        self._calc_mode_action.setChecked(False)
        self._read_mode_action.setChecked(True)

        # Rendre tous les onglets en lecture seule
        self._set_all_editors_read_only(True)

        # Appliquer le style lecture
        self._apply_theme_to_all()

        self.status_bar.showMessage(
            "Mode lecture activé. Le texte est en lecture seule.", 3000
        )

    def _set_all_editors_read_only(self, read_only: bool) -> None:
        """Passe tous les onglets en mode lecture seule ou éditable."""
        for i in range(self.tabs.count()):
            widget = self.tabs.widget(i)
            if isinstance(widget, ShadowTextEdit):
                widget.setReadOnly(read_only)

    # -----------------------------------------------------------------------
    # Slots — Mode Calcul (logique)
    # -----------------------------------------------------------------------

    def _detect_calculation(self) -> None:
        """
        En mode calcul, si la ligne courante se termine par '=',
        évalue l'expression et insère le résultat à la suite.
        """
        if self._current_mode != MODE_CALC:
            return

        editor = self._current_editor()
        if editor is None:
            return

        cursor = editor.textCursor()
        cursor.select(QTextCursor.SelectionType.LineUnderCursor)
        line = cursor.selectedText().strip()

        if not line.endswith("="):
            return

        expression = line[:-1].strip()
        result = self._eval_expression_safe(expression)

        cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock)
        cursor.insertText(f" {result}")
        editor.setTextCursor(cursor)

    @staticmethod
    def _eval_expression_safe(expression: str) -> str:
        """
        Évalue une expression mathématique via ast.parse().
        Aucun accès aux builtins ou au système — 100 % sécurisé.
        Opérateurs : + - * / ** % et parenthèses.
        """
        def _eval(node):
            if isinstance(node, ast.Constant):
                if isinstance(node.value, (int, float)):
                    return node.value
                raise ValueError("Type non numérique")
            if isinstance(node, ast.BinOp):
                op_fn = _SAFE_OPERATORS.get(type(node.op))
                if op_fn is None:
                    raise ValueError(f"Opérateur non supporté : {node.op}")
                return op_fn(_eval(node.left), _eval(node.right))
            if isinstance(node, ast.UnaryOp):
                op_fn = _SAFE_OPERATORS.get(type(node.op))
                if op_fn is None:
                    raise ValueError(f"Opérateur unaire non supporté")
                return op_fn(_eval(node.operand))
            raise ValueError(f"Nœud AST non supporté : {type(node)}")

        try:
            tree = ast.parse(expression, mode="eval")
            result = _eval(tree.body)
            if isinstance(result, float) and result.is_integer():
                return str(int(result))
            return str(result)
        except ZeroDivisionError:
            return "Erreur : division par zéro"
        except Exception:
            return "Erreur de calcul"

    # -----------------------------------------------------------------------
    # Slots — Correcteur orthographique
    # -----------------------------------------------------------------------

    def check_spelling(self) -> None:
        """
        Vérifie l'orthographe du texte de l'onglet actif.
        Surligne les mots fautifs et met à jour wrong_words_ref[0].
        """
        editor = self._current_editor()
        if editor is None:
            return

        text = editor.toPlainText()
        wrong = self.spell.unknown(text.split())

        # Mettre à jour le conteneur partagé (utilisé par ShadowTextEdit)
        self._wrong_words_ref[0] = wrong

        if wrong:
            self._highlighter = WordHighlighter(editor.document(), wrong)
            self.status_bar.showMessage(f"{len(wrong)} faute(s) détectée(s).", 6000)
        else:
            if self._highlighter is not None:
                self._highlighter.update_words(set())
            self.status_bar.showMessage("Aucune faute détectée. 💪", 4000)

    # -----------------------------------------------------------------------
    # Slots — Emojis
    # -----------------------------------------------------------------------

    def _check_emoji(self) -> None:
        """
        Vérifie si le dernier mot tapé est un code emoji.
        Si oui, remplace le code par l'emoji correspondant.
        """
        editor = self._current_editor()
        if editor is None:
            return

        cursor = editor.textCursor()
        cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
        block_text = cursor.selectedText()
        words = block_text.split()

        if not words:
            return

        last_word = words[-1]
        emoji_char = My_emoji.emoji_dictionnary.get(last_word)
        if emoji_char is None:
            return

        # Remplacer uniquement la dernière occurrence dans le bloc courant
        block_cursor = editor.textCursor()
        block_cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
        new_block = block_cursor.selectedText().rsplit(last_word, 1)
        block_cursor.insertText(emoji_char.join(new_block))

    def open_emoji_picker(self) -> None:
        """
        Ouvre le sélecteur visuel d'émojis (Ctrl+E).
        L'émoji sélectionné est inséré à la position du curseur.
        """
        editor = self._current_editor()
        if editor is None:
            return

        dialog = EmojiPickerDialog(self)
        dialog.emoji_selected.connect(
            lambda char: editor.textCursor().insertText(char)
        )
        dialog.exec()

    # -----------------------------------------------------------------------
    # Slots — Assistant vocal
    # -----------------------------------------------------------------------

    def call_shadow_assistant(self) -> None:
        """Présentation vocale de Shadow Assistant + insertion dans l'éditeur."""
        editor = self._current_editor()
        if editor is None:
            return

        message = "Bonjour, je suis Shadow Assistant. Comment puis-je vous aider ?"

        cursor = editor.textCursor()
        fmt = QTextCharFormat()
        fmt.setForeground(QColor("#0096D6"))
        cursor.insertText(message, fmt)

        fmt.setForeground(QColor("white"))
        cursor.insertText("\n", fmt)
        editor.setTextCursor(cursor)

        self._tts_worker = TtsWorker(message, parent=self)
        self._tts_worker.error_occurred.connect(
            lambda msg: self.status_bar.showMessage(msg, 3000)
        )
        self._tts_worker.start()

    def start_voice_reading(self) -> None:
        """
        Lit le contenu de l'onglet actif à haute voix via pyttsx3.
        Exécuté dans un thread séparé.
        """
        editor = self._current_editor()
        if editor is None:
            return

        text = editor.toPlainText() or editor.placeholderText()
        if not text:
            self.status_bar.showMessage("Rien à lire.", 2000)
            return

        if self._tts_worker is not None and self._tts_worker.isRunning():
            self.status_bar.showMessage("⚠️ Lecture déjà en cours.", 2000)
            return

        self.status_bar.showMessage("Lecture en cours…")
        self._tts_worker = TtsWorker(text, parent=self)
        self._tts_worker.finished.connect(
            lambda: self.status_bar.showMessage("Lecture terminée.", 2000)
        )
        self._tts_worker.error_occurred.connect(
            lambda msg: self.status_bar.showMessage(msg, 3000)
        )
        self._tts_worker.start()

    def start_voice_typing(self) -> None:
        """
        Active la dictée vocale Google dans un QThread séparé.
        """
        if self._voice_worker is not None and self._voice_worker.isRunning():
            self.status_bar.showMessage("⚠️ Dictée déjà en cours.", 2000)
            return

        self.status_bar.showMessage("🎤 Parlez maintenant…")
        self._voice_worker = VoiceTypingWorker(parent=self)
        self._voice_worker.result_ready.connect(self._insert_voice_text)
        self._voice_worker.error_occurred.connect(
            lambda msg: self.status_bar.showMessage(msg, 4000)
        )
        self._voice_worker.finished.connect(self._on_voice_finished)
        self._voice_worker.start()

    def _insert_voice_text(self, text: str) -> None:
        """Insère le texte reconnu par la dictée vocale."""
        editor = self._current_editor()
        if editor is None:
            return
        editor.textCursor().insertText(text)
        self.status_bar.showMessage("Dictée terminée.", 3000)

    def _on_voice_finished(self) -> None:
        """Nettoyage après fin du thread de dictée vocale."""
        self._voice_worker = None

    def start_voice_typing_ms(self) -> None:
        """Active la dictée vocale Windows (Win+H)."""
        try:
            import pyautogui  # type: ignore
            pyautogui.hotkey("win", "h")
        except ImportError:
            self.status_bar.showMessage("⚠️ pyautogui non installé.", 3000)
        except Exception as exc:  # noqa: BLE001
            self.status_bar.showMessage(f"⚠️ {exc}", 3000)

    # -- Panneau de corrections IA (QDockWidget) -------------------------

    def _init_correction_dock(self) -> None:
        """
        Crée le panneau latéral de corrections IA sous forme de QDockWidget.
        Masqué par défaut, s'affiche automatiquement lors d'une analyse.

        Note : en v0.7.1, CorrectionPanel gère "tout accepter / ignorer"
        en interne par section. Les seuls signaux exposés sont
        apply_correction et delete_model_requested.
        """
        self._correction_panel = CorrectionPanel()

        # Connexions des signaux du panneau (v0.7.1)
        self._correction_panel.apply_correction.connect(self._apply_ai_correction)
        self._correction_panel.delete_model_requested.connect(self._delete_ai_model)

        # Encapsuler dans un QDockWidget (panneau ancrable)
        self._dock = QDockWidget("Corrections IA", self)
        self._dock.setWidget(self._correction_panel)
        self._dock.setAllowedAreas(
            Qt.DockWidgetArea.RightDockWidgetArea |
            Qt.DockWidgetArea.LeftDockWidgetArea
        )
        self._dock.setMinimumWidth(260)
        self._dock.setMaximumWidth(420)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._dock)
        self._dock.hide()  # masqué au démarrage

    # -----------------------------------------------------------------------
    # Slots — Correcteur IA (ministral-3:3b via Ollama)
    # -----------------------------------------------------------------------

    def run_ai_grammar_check(self) -> None:
        """
        Point d'entrée principal du correcteur IA (F7).

        Flux :
          1. Vérifier qu'Ollama est installé et que le modèle est disponible.
          2. Si non → ouvrir SetupDialog.
          3. Si oui → lancer GrammarWorker dans un QThread.
          4. Afficher les résultats dans le CorrectionPanel (dock latéral).
        """
        editor = self._current_editor()
        if editor is None:
            return

        text = editor.toPlainText().strip()
        if not text:
            self.status_bar.showMessage("Rien à analyser.", 2000)
            return

        # -- Vérification rapide de l'état d'Ollama ----------------------
        if not OllamaManager.is_ollama_installed():
            self._open_setup_dialog()
            return

        if not OllamaManager.is_server_running():
            self.status_bar.showMessage("Démarrage d'Ollama…")
            OllamaManager.start_server()
            # Réessayer dans 2 secondes
            from PySide6.QtCore import QTimer
            QTimer.singleShot(2000, self.run_ai_grammar_check)
            return

        if not OllamaManager.is_model_available():
            self._open_setup_dialog()
            return

        # -- Éviter deux analyses en parallèle ---------------------------
        if self._grammar_worker is not None and self._grammar_worker.isRunning():
            self.status_bar.showMessage("⚠️ Analyse déjà en cours.", 2000)
            return

        # -- Lancer l'analyse --------------------------------------------
        self._dock.show()
        self._correction_panel.set_loading(f"Analyse avec {OLLAMA_MODEL}…")

        self._grammar_worker = GrammarWorker(text, parent=self)
        self._grammar_worker.corrections_ready.connect(self._on_corrections_ready)
        self._grammar_worker.suggestions_ready.connect(self._on_suggestions_ready)
        self._grammar_worker.score_ready.connect(self._on_score_ready)
        self._grammar_worker.error_occurred.connect(self._on_grammar_error)
        self._grammar_worker.status_message.connect(
            lambda msg: self.status_bar.showMessage(msg)
        )
        # Stocker les résultats intermédiaires
        self._pending_score:       int  = 100
        self._pending_corrections: list = []
        self._pending_suggestions: list = []
        self._grammar_worker.start()

    def _open_setup_dialog(self) -> None:
        """Ouvre l'assistant d'installation Ollama + modèle."""
        dialog = SetupDialog(self)
        dialog.setup_complete.connect(
            lambda: self.status_bar.showMessage(
                f"✅ {OLLAMA_MODEL} prêt ! Appuyez sur F7 pour analyser.", 4000
            )
        )
        dialog.exec()

    def _on_corrections_ready(self, corrections: list) -> None:
        """Reçoit la liste des corrections depuis GrammarWorker."""
        self._pending_corrections = corrections

    def _on_suggestions_ready(self, suggestions: list) -> None:
        """Reçoit la liste des suggestions depuis GrammarWorker."""
        self._pending_suggestions = suggestions

    def _on_score_ready(self, score: int) -> None:
        """
        Reçoit le score et affiche l'ensemble des résultats.
        C'est le dernier signal émis par GrammarWorker — on appelle
        set_results() ici pour afficher corrections + suggestions + score
        en une seule passe.
        """
        self._correction_panel.set_results(
            self._pending_corrections,
            self._pending_suggestions,
            score,
        )
        n_c = len(self._pending_corrections)
        n_s = len(self._pending_suggestions)
        if n_c == 0 and n_s == 0:
            self.status_bar.showMessage("✅ Aucune erreur détectée. Score : 100/100", 4000)
        else:
            parts = []
            if n_c:
                parts.append(f"{n_c} correction{'s' if n_c != 1 else ''}")
            if n_s:
                parts.append(f"{n_s} suggestion{'s' if n_s != 1 else ''}")
            self.status_bar.showMessage(
                f"🔵 {' et '.join(parts)} proposée(s). Score : {score}/100", 5000
            )

    def _on_grammar_error(self, message: str) -> None:
        """Affiche une erreur du correcteur IA."""
        self._correction_panel.set_error(message)
        self.status_bar.showMessage(f"⚠️ {message}", 5000)

    def _apply_ai_correction(self, original: str, correction: str) -> None:
        """
        Remplace la première occurrence de `original` par `correction`
        dans l'onglet actif.
        Utilise QTextCursor.find() pour une recherche précise dans le document.
        """
        editor = self._current_editor()
        if editor is None:
            return

        # Chercher le mot exact dans le document
        document = editor.document()
        cursor = document.find(original)

        if not cursor.isNull():
            cursor.insertText(correction)
            self.status_bar.showMessage(
                f'"{original}" → "{correction}"', 3000
            )
        else:
            self.status_bar.showMessage(
                f'⚠️ "{original}" introuvable dans le texte.', 3000
            )

    def _accept_all_corrections(self) -> None:
        """
        Accepte toutes les corrections.
        Appelé programmatiquement si besoin — les boutons globaux du panneau
        appellent directement _sec_corrections.accept_all() en interne.
        """
        self._correction_panel._sec_corrections.accept_all()  # type: ignore[attr-defined]
        self.status_bar.showMessage("Toutes les corrections ont été appliquées.", 3000)

    def _ignore_all_corrections(self) -> None:
        """
        Ignore toutes les corrections et ferme le panneau.
        Appelé programmatiquement si besoin.
        """
        self._correction_panel.clear()
        self._dock.hide()
        self.status_bar.showMessage("Corrections ignorées.", 2000)

    def _delete_ai_model(self) -> None:
        """Supprime le modèle ministral-3:3b après confirmation."""
        reply = QMessageBox.question(
            self,
            "Supprimer le modèle IA",
            f"Supprimer {OLLAMA_MODEL} ({MODEL_SIZE_DISPLAY}) du disque ?\n"
            "Il faudra le retélécharger pour utiliser le correcteur IA.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            ok, msg = OllamaManager.delete_model()
            if ok:
                self._correction_panel.clear()
                self._dock.hide()
                self.status_bar.showMessage(f"🗑 {msg}", 4000)
            else:
                self.status_bar.showMessage(f"⚠️ {msg}", 4000)

    def show_help(self) -> None:
        """Affiche la fenêtre d'aide."""
        HelpDialog(self).exec()

    def show_credits(self) -> None:
        """Affiche la fenêtre de crédits."""
        CreditsDialog(self).exec()

    def show_info(self) -> None:
        """Affiche les informations sur l'application."""
        QMessageBox.information(
            self, "Informations",
            f"{APP_NAME}\nVersion {APP_VERSION}\n\n"
            "Éditeur de texte moderne développé avec Python et PySide6.\n"
            "Licence : CC BY-NC-ND 4.0",
        )

    # -----------------------------------------------------------------------
    # Événements Qt
    # -----------------------------------------------------------------------

    def closeEvent(self, event) -> None:
        """
        À la fermeture de l'application, propose de sauvegarder uniquement
        les onglets qui ont été réellement modifiés (flag is_modified).
        """
        unsaved_indices = []
        for i in range(self.tabs.count()):
            widget = self.tabs.widget(i)
            if isinstance(widget, ShadowTextEdit) and widget.property("is_modified"):
                unsaved_indices.append(i)

        if unsaved_indices:
            n = len(unsaved_indices)
            reply = QMessageBox.question(
                self, "Quitter",
                f"{n} onglet(s) contiennent des modifications non enregistrées.\n"
                "Voulez-vous les enregistrer avant de quitter ?",
                QMessageBox.StandardButton.Yes  |
                QMessageBox.StandardButton.No   |
                QMessageBox.StandardButton.Cancel,
            )
            if reply == QMessageBox.StandardButton.Yes:
                for i in unsaved_indices:
                    self.tabs.setCurrentIndex(i)
                    self.save_file()
                event.accept()
            elif reply == QMessageBox.StandardButton.No:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()

    # -----------------------------------------------------------------------
    # Utilitaires internes
    # -----------------------------------------------------------------------

    def _ask_save_before_close(self) -> QMessageBox.StandardButton:
        """
        Demande à l'utilisateur s'il souhaite sauvegarder avant de fermer
        un onglet modifié.
        """
        return QMessageBox.question(
            self, "Onglet modifié",
            "Cet onglet contient des modifications non enregistrées.\n"
            "Voulez-vous les enregistrer ?",
            QMessageBox.StandardButton.Yes  |
            QMessageBox.StandardButton.No   |
            QMessageBox.StandardButton.Cancel,
        )


# ===========================================================================
# Point d'entrée
# ===========================================================================

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())
