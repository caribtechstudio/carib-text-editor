"""
ai_checker.py — Module de correction IA pour Shadow Text Editor v0.7.1
======================================================================
Fournit l'ensemble du système de correction grammaticale et orthographique
basé sur Ollama + ministral-3:3b en local.

Composants :
  - OllamaManager       : détection, installation et gestion d'Ollama/modèle
  - OllamaInstallWorker : téléchargement d'Ollama dans un QThread
  - ModelPullWorker     : pull du modèle ministral-3:3b dans un QThread
  - GrammarWorker       : appel REST à l'API Ollama dans un QThread
  - SetupDialog         : assistant d'installation guidée avec progression
  - _BaseItem           : widget de base pour corrections et suggestions
  - CorrectionItem      : widget d'une correction individuelle
  - SuggestionItem      : widget d'une suggestion individuelle
  - _SectionWidget      : section pliable avec compteur dynamique
  - CorrectionPanel     : panneau latéral avec corrections + suggestions

Changelog v0.7.1 :
  - Nouveau prompt robuste (règles strictes + section suggestions)
  - Section "suggestions" séparée des "corrections" dans le panneau
  - Boutons "Appliquer" ET "Ignorer" sur chaque item individuel
  - Animation de collapse sur "Ignorer"
  - Compteurs dynamiques dans les titres de section
  - Boutons globaux par section (✓ Corrections / ✗ Corrections / etc.)

Dépendances Python : requests
Dépendances système : Ollama >= 0.13.1

Auteur  : Arnaud
Licence : CC BY-NC-ND 4.0
Version : 0.7.1
"""

# ---------------------------------------------------------------------------
# Imports standard
# ---------------------------------------------------------------------------
import json
import os
import platform
import re
import shutil
import subprocess
import tempfile
import urllib.request

# ---------------------------------------------------------------------------
# Imports tiers
# ---------------------------------------------------------------------------
try:
    import requests as _requests          # type: ignore[import-untyped]
    REQUESTS_AVAILABLE = True
except ImportError:
    _requests = None       # type: ignore[assignment]
    REQUESTS_AVAILABLE = False

# ---------------------------------------------------------------------------
# Imports PySide6
# ---------------------------------------------------------------------------
from PySide6.QtCore import (
    Qt,
    QThread,
    QTimer,
    Signal,
)
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


# ===========================================================================
# Constantes
# ===========================================================================

#: Nom exact du modèle sur Ollama (https://ollama.com/library/ministral-3:3b)
OLLAMA_MODEL = "ministral-3:3b"

#: Taille approximative affichée à l'utilisateur
MODEL_SIZE_DISPLAY = "3.0 GB"

#: Endpoints de l'API REST locale d'Ollama
OLLAMA_API_URL    = "http://localhost:11434/api/generate"
OLLAMA_HEALTH_URL = "http://localhost:11434/"
OLLAMA_LIST_URL   = "http://localhost:11434/api/tags"

#: URLs d'installation d'Ollama selon la plateforme
OLLAMA_DOWNLOAD_URLS = {
    "Windows": "https://ollama.com/download/OllamaSetup.exe",
    "Darwin":  "https://ollama.com/download/Ollama-darwin.zip",
    "Linux":   "https://ollama.com/install.sh",
}

#: Timeout pour les appels API (secondes)
API_TIMEOUT = 120


# ===========================================================================
# Prompt système v0.7.1
# Basé sur le prompt d'Arnaud, adapté au format JSON pour les corrections
# cliquables, avec section "suggestions" optionnelle séparée.
# ===========================================================================

GRAMMAR_SYSTEM_PROMPT = """Tu es un correcteur linguistique expert en français.
Analyse le texte fourni et retourne UNIQUEMENT un JSON valide, sans texte avant ni après.

RÈGLES DE CORRECTION (priorité absolue) :
- Corrige toutes les fautes d'orthographe, de conjugaison, d'accords et de ponctuation
- Rétablis la cohérence temporelle si un temps brise la logique grammaticale (ex: "il mangeas" -> "il mangea")
- NE reformule PAS : zéro synonyme de remplacement, zéro réorganisation si la syntaxe est correcte
- NE rajoute et NE supprime aucun mot, sauf si strictement nécessaire pour corriger une faute
- Respecte la mise en page originale (paragraphes, tirets de dialogue, majuscules intentionnelles)
- Ne touche pas aux noms propres, acronymes, mots étrangers intentionnels

SUGGESTIONS (secondaires, uniquement si vraiment pertinent) :
- Propose un synonyme UNIQUEMENT si un mot est répété plus de 2 fois ou est particulièrement banal
- Propose une reformulation UNIQUEMENT si une phrase est grammaticalement correcte mais maladroite (redondance évidente, longueur excessive)
- Maximum 3 suggestions par texte, ne pas suggérer si le texte est déjà bon

FORMAT JSON OBLIGATOIRE :
{
  "corrections": [
    {
      "original": "texte fautif exact tel qu'il apparait dans le texte source",
      "correction": "version corrigée",
      "type": "orthographe|grammaire|conjugaison|accord|ponctuation",
      "explication": "raison courte en 8 mots maximum"
    }
  ],
  "suggestions": [
    {
      "original": "texte original exact tel qu'il apparait dans le texte source",
      "suggestion": "version améliorée proposée",
      "type": "synonyme|reformulation",
      "explication": "raison courte en 8 mots maximum"
    }
  ],
  "score": 0
}

Si le texte est correct : {"corrections": [], "suggestions": [], "score": 100}
Reponds UNIQUEMENT avec ce JSON. Rien d'autre. Pas d'introduction, pas de commentaire."""


# ===========================================================================
# Classe : OllamaManager
# ===========================================================================

class OllamaManager:
    """Classe utilitaire statique pour la détection et la gestion d'Ollama."""

    @staticmethod
    def is_ollama_installed() -> bool:
        """Retourne True si la commande ollama est disponible dans le PATH."""
        return shutil.which("ollama") is not None

    @staticmethod
    def is_server_running() -> bool:
        """Retourne True si le serveur Ollama répond sur localhost:11434."""
        if not REQUESTS_AVAILABLE or _requests is None:
            return False
        try:
            r = _requests.get(OLLAMA_HEALTH_URL, timeout=3)
            return r.status_code == 200
        except Exception:
            return False

    @staticmethod
    def start_server() -> bool:
        """Lance le serveur Ollama en arrière-plan. Retourne True si OK."""
        try:
            if platform.system() == "Windows":
                subprocess.Popen(
                    ["ollama", "serve"],
                    creationflags=subprocess.CREATE_NO_WINDOW,  # type: ignore[attr-defined]
                )
            else:
                subprocess.Popen(
                    ["ollama", "serve"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            return True
        except FileNotFoundError:
            return False

    @staticmethod
    def is_model_available() -> bool:
        """Retourne True si ministral-3:3b est présent dans les modèles Ollama."""
        if not REQUESTS_AVAILABLE or _requests is None:
            return False
        try:
            r     = _requests.get(OLLAMA_LIST_URL, timeout=5)
            data  = r.json()
            names = [m.get("name", "") for m in data.get("models", [])]
            return any(OLLAMA_MODEL in n or n in OLLAMA_MODEL for n in names)
        except Exception:
            return False

    @staticmethod
    def delete_model() -> tuple:
        """Supprime le modèle via ollama rm. Retourne (succes: bool, message: str)."""
        try:
            result = subprocess.run(
                ["ollama", "rm", OLLAMA_MODEL],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0:
                return True, f"Modèle {OLLAMA_MODEL} supprimé avec succès."
            return False, result.stderr.strip() or "Erreur inconnue."
        except FileNotFoundError:
            return False, "Ollama n'est pas installé."
        except Exception as exc:
            return False, str(exc)

    @staticmethod
    def get_download_url():
        """Retourne l'URL de téléchargement d'Ollama pour la plateforme courante."""
        return OLLAMA_DOWNLOAD_URLS.get(platform.system())

    @staticmethod
    def get_platform_name() -> str:
        """Retourne un nom lisible de la plateforme."""
        return {"Windows": "Windows", "Darwin": "macOS", "Linux": "Linux"}.get(
            platform.system(), platform.system()
        )


# ===========================================================================
# Classe : OllamaInstallWorker
# Télécharge et installe Ollama dans un QThread séparé.
# ===========================================================================

class OllamaInstallWorker(QThread):
    """
    Worker QThread pour télécharger et installer Ollama.

    Signaux :
      progress(int, str)   : pourcentage + message d'état
      speed_updated(str)   : vitesse ex. "2.3 MB/s"
      finished_ok(str)     : message de succès
      error_occurred(str)  : message d'erreur
    """

    progress       = Signal(int, str)
    speed_updated  = Signal(str)
    finished_ok    = Signal(str)
    error_occurred = Signal(str)

    def run(self) -> None:
        """Télécharge et exécute l'installeur Ollama selon la plateforme."""
        url  = OllamaManager.get_download_url()
        plat = platform.system()

        if url is None:
            self.error_occurred.emit("Plateforme non supportée pour l'installation automatique.")
            return

        try:
            self.progress.emit(5, "Connexion aux serveurs Ollama…")

            if plat == "Linux":
                self._install_linux(url)
                return

            import time
            tmpdir = tempfile.mkdtemp()
            ext    = ".exe" if plat == "Windows" else ".zip"
            dest   = os.path.join(tmpdir, f"ollama_installer{ext}")

            start_time      = [time.time()]
            last_downloaded = [0]

            def reporthook(block_num, block_size, total_size):
                downloaded = block_num * block_size
                pct = min(int(downloaded / total_size * 80), 80) if total_size > 0 else 0
                self.progress.emit(pct, f"Téléchargement Ollama… {downloaded // (1024*1024)} MB")
                elapsed = time.time() - start_time[0]
                if elapsed >= 0.5:
                    speed = (downloaded - last_downloaded[0]) / elapsed / (1024 * 1024)
                    self.speed_updated.emit(f"{speed:.1f} MB/s")
                    start_time[0]      = time.time()
                    last_downloaded[0] = downloaded

            urllib.request.urlretrieve(url, dest, reporthook=reporthook)
            self.progress.emit(85, "Installation en cours…")

            if plat == "Windows":
                subprocess.run([dest, "/S"], check=True, timeout=120)
            elif plat == "Darwin":
                subprocess.run(
                    ["unzip", "-o", dest, "-d", "/Applications"], check=True
                )

            self.progress.emit(100, "Ollama installé avec succès.")
            self.finished_ok.emit(
                "Ollama a été installé. Relancez l'application si nécessaire."
            )

        except Exception as exc:  # noqa: BLE001
            self.error_occurred.emit(f"Erreur d'installation : {exc}")

    def _install_linux(self, url: str) -> None:
        """Installation Linux via le script officiel curl | sh."""
        self.progress.emit(10, "Lancement du script d'installation Linux…")
        try:
            result = subprocess.run(
                f"curl -fsSL {url} | sh",
                shell=True, capture_output=True, text=True, timeout=300,
            )
            if result.returncode == 0:
                self.progress.emit(100, "Ollama installé.")
                self.finished_ok.emit("Ollama installé via le script officiel.")
            else:
                self.error_occurred.emit(result.stderr or "Erreur d'installation Linux.")
        except Exception as exc:  # noqa: BLE001
            self.error_occurred.emit(str(exc))


# ===========================================================================
# Classe : ModelPullWorker
# Télécharge ministral-3:3b via `ollama pull` dans un QThread.
# ===========================================================================

class ModelPullWorker(QThread):
    """
    Worker QThread pour `ollama pull ministral-3:3b`.
    Parse les lignes JSON écrites par Ollama sur stdout.

    Signaux :
      progress(int, str)
      speed_updated(str)
      finished_ok()
      error_occurred(str)
      cancelled()
    """

    progress       = Signal(int, str)
    speed_updated  = Signal(str)
    finished_ok    = Signal()
    error_occurred = Signal(str)
    cancelled      = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._cancel_requested = False
        self._process          = None

    def request_cancel(self) -> None:
        """Demande l'annulation propre du téléchargement."""
        self._cancel_requested = True
        if self._process is not None:
            self._process.terminate()

    def run(self) -> None:
        """Lance ollama pull et parse les lignes JSON de progression."""
        import time

        try:
            self.progress.emit(0, f"Démarrage du téléchargement de {OLLAMA_MODEL}…")

            self._process = subprocess.Popen(
                ["ollama", "pull", OLLAMA_MODEL],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            # stdout est garanti non-None car on a passé stdout=PIPE
            assert self._process.stdout is not None, "stdout inattendu None"

            last_time      = time.time()
            last_completed = 0

            for raw_line in self._process.stdout:
                if self._cancel_requested:
                    self._process.terminate()
                    self.cancelled.emit()
                    return

                line = raw_line.strip()
                if not line:
                    continue

                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    self.progress.emit(1, line)
                    continue

                status    = data.get("status", "")
                total     = data.get("total", 0)
                completed = data.get("completed", 0)

                if total and total > 0:
                    pct          = int(completed / total * 100)
                    completed_mb = completed / (1024 * 1024)
                    total_mb     = total     / (1024 * 1024)

                    now     = time.time()
                    elapsed = now - last_time
                    if elapsed >= 1.0:
                        delta     = completed - last_completed
                        speed_mbs = delta / (1024 * 1024) / elapsed
                        rem_mb    = (total - completed) / (1024 * 1024)
                        eta_sec   = int(rem_mb / speed_mbs) if speed_mbs > 0 else 0
                        eta_str   = (
                            f"{eta_sec // 60} min {eta_sec % 60} s"
                            if eta_sec >= 60 else f"{eta_sec} s"
                        )
                        self.speed_updated.emit(
                            f"{speed_mbs:.1f} MB/s  ·  ETA {eta_str}"
                        )
                        last_time      = now
                        last_completed = completed

                    self.progress.emit(
                        pct, f"{status} — {completed_mb:.0f} / {total_mb:.0f} MB"
                    )
                else:
                    self.progress.emit(1, status)

            self._process.wait()

            if self._cancel_requested:
                self.cancelled.emit()
                return

            if self._process.returncode == 0:
                self.progress.emit(100, "Modèle prêt.")
                self.finished_ok.emit()
            else:
                self.error_occurred.emit(
                    f"ollama pull a échoué (code {self._process.returncode})."
                )

        except FileNotFoundError:
            self.error_occurred.emit("Ollama est introuvable dans le PATH.")
        except Exception as exc:  # noqa: BLE001
            self.error_occurred.emit(f"Erreur inattendue : {exc}")


# ===========================================================================
# Classe : GrammarWorker
# Envoie le texte à l'API Ollama et parse la réponse JSON.
# ===========================================================================

class GrammarWorker(QThread):
    """
    Worker QThread pour l'appel à l'API Ollama.
    Utilise GRAMMAR_SYSTEM_PROMPT v0.7.1.

    Signaux :
      corrections_ready(list)
      suggestions_ready(list)
      score_ready(int)
      error_occurred(str)
      status_message(str)
    """

    corrections_ready = Signal(list)
    suggestions_ready = Signal(list)
    score_ready       = Signal(int)
    error_occurred    = Signal(str)
    status_message    = Signal(str)

    def __init__(self, text: str, parent=None) -> None:
        super().__init__(parent)
        self._text = text

    def run(self) -> None:
        """Corps du thread : appel REST + parsing JSON."""
        if not REQUESTS_AVAILABLE:
            self.error_occurred.emit(
                "Le module 'requests' n'est pas installé.\n"
                "Lancez : pip install requests"
            )
            return

        if not self._text.strip():
            self.corrections_ready.emit([])
            self.suggestions_ready.emit([])
            self.score_ready.emit(100)
            return

        self.status_message.emit(f"🔵 Analyse avec {OLLAMA_MODEL}…")

        payload = {
            "model": OLLAMA_MODEL,
            "prompt": (
                "Voici le texte français à analyser :\n\n"
                f"{self._text}\n\n"
                "Retourne uniquement le JSON de corrections et suggestions."
            ),
            "system": GRAMMAR_SYSTEM_PROMPT,
            "stream": False,
            "options": {
                "temperature": 0.1,
                "top_p":       0.9,
                "num_predict": 2048,
            },
        }

        try:
            if _requests is None:
                self.error_occurred.emit("Le module 'requests' n'est pas disponible.")
                return

            response = _requests.post(
                OLLAMA_API_URL, json=payload, timeout=API_TIMEOUT
            )
            response.raise_for_status()

            raw = response.json().get("response", "").strip()
            parsed = self._extract_json(raw)

            if parsed is None:
                self.error_occurred.emit(
                    "La réponse du modèle n'est pas du JSON valide.\n"
                    f"Début : {raw[:200]}"
                )
                return

            corrections = self._validate_corrections(parsed.get("corrections", []))
            suggestions = self._validate_suggestions(parsed.get("suggestions", []))
            score       = max(0, min(100, int(parsed.get("score", 100))))

            self.corrections_ready.emit(corrections)
            self.suggestions_ready.emit(suggestions)
            self.score_ready.emit(score)

        except AttributeError:
            # _requests est None (import raté)
            self.error_occurred.emit(
                "Le module 'requests' n'est pas installé.\n"
                "Lancez : pip install requests"
            )
        except Exception as exc:  # noqa: BLE001
            # Capturer ConnectionError, Timeout, etc. sans référencer requests.*
            exc_name = type(exc).__name__
            if "ConnectionError" in exc_name:
                self.error_occurred.emit(
                    "Impossible de joindre Ollama (localhost:11434).\n"
                    "Vérifiez qu'Ollama est bien lancé."
                )
            elif "Timeout" in exc_name:
                self.error_occurred.emit(
                    f"Délai dépassé ({API_TIMEOUT} s). Le modèle est trop lent."
                )
            else:
                self.error_occurred.emit(f"Erreur lors de l'analyse : {exc}")

    # -- Helpers ---------------------------------------------------------

    @staticmethod
    def _validate_corrections(raw: list) -> list:
        """Filtre et normalise la liste des corrections."""
        result = []
        for c in raw:
            if not isinstance(c, dict):
                continue
            orig = str(c.get("original", "")).strip()
            corr = str(c.get("correction", "")).strip()
            if orig and corr and orig != corr:
                result.append({
                    "original":    orig,
                    "correction":  corr,
                    "type":        str(c.get("type",        "orthographe")).strip(),
                    "explication": str(c.get("explication", "")).strip(),
                })
        return result

    @staticmethod
    def _validate_suggestions(raw: list) -> list:
        """Filtre et normalise la liste des suggestions."""
        result = []
        for s in raw:
            if not isinstance(s, dict):
                continue
            orig = str(s.get("original",   "")).strip()
            sug  = str(s.get("suggestion", "")).strip()
            if orig and sug and orig != sug:
                result.append({
                    "original":    orig,
                    "suggestion":  sug,
                    "type":        str(s.get("type",        "reformulation")).strip(),
                    "explication": str(s.get("explication", "")).strip(),
                })
        return result

    @staticmethod
    def _extract_json(text: str):
        """
        Extrait et parse le premier objet JSON valide dans text.
        Résiste aux blocs ```json ... ``` et au texte parasite.
        """
        # Supprimer les balises markdown
        text  = re.sub(r"```(?:json)?", "", text).strip()
        start = text.find("{")
        if start == -1:
            return None
        depth = 0
        for i, ch in enumerate(text[start:], start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start: i + 1])
                    except json.JSONDecodeError:
                        return None
        return None


# ===========================================================================
# Classe : SetupDialog
# ===========================================================================

class SetupDialog(QDialog):
    """
    Boîte de dialogue modale guidant l'installation d'Ollama + ministral-3:3b.
    """

    setup_complete = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Configuration — Correcteur IA")
        self.setMinimumWidth(500)
        self.setModal(True)

        self._install_worker = None
        self._pull_worker    = None

        self._build_ui()
        QTimer.singleShot(200, self._check_status)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(22, 22, 22, 22)

        title = QLabel("Configuration du correcteur IA")
        title.setStyleSheet("font-size: 15px; font-weight: 500;")
        layout.addWidget(title)

        subtitle = QLabel(
            f"Modèle : <b>{OLLAMA_MODEL}</b> ({MODEL_SIZE_DISPLAY})  •  "
            "Moteur : <b>Ollama</b>  •  Traitement 100 % local et privé"
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: gray; font-size: 12px;")
        layout.addWidget(subtitle)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)

        # Statut
        status_row = QHBoxLayout()
        self._status_icon = QLabel("⏳")
        self._status_icon.setStyleSheet("font-size: 22px;")
        self._status_text = QLabel("Vérification en cours…")
        self._status_text.setWordWrap(True)
        self._status_text.setStyleSheet("font-size: 13px;")
        status_row.addWidget(self._status_icon, 0, Qt.AlignmentFlag.AlignTop)
        status_row.addWidget(self._status_text, 1)
        layout.addLayout(status_row)

        # Progression
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.hide()
        layout.addWidget(self._progress_bar)

        self._speed_label = QLabel("")
        self._speed_label.setStyleSheet("font-size: 11px; color: gray;")
        self._speed_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._speed_label.hide()
        layout.addWidget(self._speed_label)

        self._info_label = QLabel(
            f"ℹ️  {OLLAMA_MODEL} nécessite environ {MODEL_SIZE_DISPLAY} d'espace disque libre."
        )
        self._info_label.setWordWrap(True)
        self._info_label.setStyleSheet("font-size: 11px; color: gray;")
        self._info_label.hide()
        layout.addWidget(self._info_label)

        # Boutons
        btn_row = QHBoxLayout()

        self._btn_action = QPushButton("Installer Ollama")
        self._btn_action.setEnabled(False)
        self._btn_action.clicked.connect(self._on_action)

        self._btn_cancel_dl = QPushButton("Annuler le téléchargement")
        self._btn_cancel_dl.hide()
        self._btn_cancel_dl.setStyleSheet("color: #c0392b;")
        self._btn_cancel_dl.clicked.connect(self._on_cancel)

        self._btn_delete = QPushButton(f"🗑 Supprimer {OLLAMA_MODEL}")
        self._btn_delete.hide()
        self._btn_delete.setStyleSheet("color: #c0392b;")
        self._btn_delete.clicked.connect(self._on_delete)

        self._btn_close = QPushButton("Fermer")
        self._btn_close.clicked.connect(self.reject)

        btn_row.addWidget(self._btn_action)
        btn_row.addWidget(self._btn_cancel_dl)
        btn_row.addStretch()
        btn_row.addWidget(self._btn_delete)
        btn_row.addWidget(self._btn_close)
        layout.addLayout(btn_row)

    # -- Logique de vérification -----------------------------------------

    def _check_status(self) -> None:
        self._set_status("⏳", "Vérification d'Ollama…")
        if not OllamaManager.is_ollama_installed():
            self._show_need_ollama()
            return
        self._set_status("⏳", "Démarrage du serveur Ollama…")
        if not OllamaManager.is_server_running():
            OllamaManager.start_server()
            QTimer.singleShot(2000, self._check_model)
        else:
            self._check_model()

    def _check_model(self) -> None:
        if not OllamaManager.is_server_running():
            self._set_status("⚠️", "Impossible de démarrer Ollama.\nEssayez : ollama serve")
            return
        if OllamaManager.is_model_available():
            self._show_ready()
        else:
            self._show_need_model()

    def _show_need_ollama(self) -> None:
        self._set_status(
            "❌",
            f"Ollama n'est pas installé sur ce {OllamaManager.get_platform_name()}.\n"
            "Cliquez sur 'Installer Ollama' pour le télécharger."
        )
        self._btn_action.setText("Installer Ollama")
        self._btn_action.setEnabled(True)
        self._info_label.show()

    def _show_need_model(self) -> None:
        self._set_status(
            "⚠️",
            f"Ollama est installé, mais {OLLAMA_MODEL} ({MODEL_SIZE_DISPLAY}) "
            "n'est pas encore téléchargé."
        )
        self._btn_action.setText(f"Télécharger {OLLAMA_MODEL}")
        self._btn_action.setEnabled(True)
        self._info_label.show()

    def _show_ready(self) -> None:
        self._set_status("✅", f"{OLLAMA_MODEL} est prêt. Le correcteur IA est opérationnel.")
        self._btn_action.setText("Fermer")
        self._btn_action.setEnabled(True)
        try:
            self._btn_action.clicked.disconnect()
        except RuntimeError:
            pass
        self._btn_action.clicked.connect(self.accept)
        self._btn_delete.show()
        self._info_label.hide()
        self.setup_complete.emit()

    def _set_status(self, icon: str, msg: str) -> None:
        self._status_icon.setText(icon)
        self._status_text.setText(msg)

    # -- Boutons ---------------------------------------------------------

    def _on_action(self) -> None:
        label = self._btn_action.text()
        if "Installer" in label:
            self._start_install()
        elif "Télécharger" in label:
            self._start_pull()

    def _start_install(self) -> None:
        self._btn_action.setEnabled(False)
        self._progress_bar.show()
        self._speed_label.show()
        self._btn_cancel_dl.show()
        self._set_status("⬇️", "Téléchargement d'Ollama…")
        self._install_worker = OllamaInstallWorker(parent=self)
        self._install_worker.progress.connect(self._on_progress)
        self._install_worker.speed_updated.connect(self._speed_label.setText)
        self._install_worker.finished_ok.connect(self._on_installed)
        self._install_worker.error_occurred.connect(self._on_error)
        self._install_worker.start()

    def _start_pull(self) -> None:
        self._btn_action.setEnabled(False)
        self._progress_bar.show()
        self._speed_label.show()
        self._btn_cancel_dl.show()
        self._set_status("⬇️", f"Téléchargement de {OLLAMA_MODEL}…")
        self._pull_worker = ModelPullWorker(parent=self)
        self._pull_worker.progress.connect(self._on_progress)
        self._pull_worker.speed_updated.connect(self._speed_label.setText)
        self._pull_worker.finished_ok.connect(self._on_model_ready)
        self._pull_worker.error_occurred.connect(self._on_error)
        self._pull_worker.cancelled.connect(self._on_cancelled)
        self._pull_worker.start()

    def _on_cancel(self) -> None:
        if self._install_worker and self._install_worker.isRunning():
            self._install_worker.terminate()
        if self._pull_worker and self._pull_worker.isRunning():
            self._pull_worker.request_cancel()
        self._hide_progress()
        self._set_status("⚠️", "Téléchargement annulé.")
        self._btn_action.setEnabled(True)

    def _on_delete(self) -> None:
        reply = QMessageBox.question(
            self, "Supprimer le modèle",
            f"Supprimer {OLLAMA_MODEL} ({MODEL_SIZE_DISPLAY}) du disque ?\n"
            "Le correcteur IA ne sera plus disponible.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            ok, msg = OllamaManager.delete_model()
            if ok:
                self._set_status("🗑", msg)
                self._btn_delete.hide()
                self._show_need_model()
            else:
                self._set_status("❌", f"Erreur : {msg}")

    def _on_progress(self, pct: int, msg: str) -> None:
        self._progress_bar.setValue(pct)
        self._set_status("⬇️", msg)

    def _on_installed(self, msg: str) -> None:
        self._hide_progress()
        self._set_status("✅", msg)
        QTimer.singleShot(1000, self._check_status)

    def _on_model_ready(self) -> None:
        self._hide_progress()
        self._show_ready()

    def _on_cancelled(self) -> None:
        self._hide_progress()
        self._set_status("⚠️", "Téléchargement annulé. Le modèle n'est pas disponible.")
        self._btn_action.setEnabled(True)

    def _on_error(self, msg: str) -> None:
        self._hide_progress()
        self._set_status("❌", msg)
        self._btn_action.setEnabled(True)

    def _hide_progress(self) -> None:
        self._progress_bar.hide()
        self._speed_label.hide()
        self._btn_cancel_dl.hide()


# ===========================================================================
# Classe : _BaseItem
# Widget de base pour les corrections et suggestions individuelles.
# Fournit les boutons "Appliquer" et "Ignorer" avec animation de collapse.
# ===========================================================================

class _BaseItem(QWidget):
    """
    Widget générique pour un élément du panneau (correction ou suggestion).

    Sous-classes doivent définir :
      _replacement_key : str  (clé du dict pour la valeur de remplacement)
      _dot_color(type) : str  (couleur hex de la pastille)
    """

    apply_requested  = Signal(str, str)   # (original, remplacement)
    ignore_requested = Signal(object)     # (self)

    _replacement_key: str = "correction"

    def __init__(self, data: dict, parent=None) -> None:
        super().__init__(parent)
        self._original    = data.get("original", "")
        self._replacement = data.get(self._replacement_key, "")
        self._type        = data.get("type", "")
        self._explication = data.get("explication", "")
        self._applied     = False
        self._ignored     = False
        self._build_ui()

    def _dot_color(self, type_str: str) -> str:
        """Retourne la couleur hex de la pastille (surcharger dans les sous-classes)."""
        return "#95A5A6"

    def _build_ui(self) -> None:
        """Construit le widget avec pastille, texte et boutons."""
        self.setContentsMargins(0, 0, 0, 0)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)

        # Pastille colorée
        dot = QLabel("●")
        dot.setStyleSheet(
            f"color: {self._dot_color(self._type)}; font-size: 10px;"
        )
        dot.setFixedWidth(14)
        layout.addWidget(dot)

        # Texte : original → remplacement + explication
        text_layout = QVBoxLayout()
        text_layout.setSpacing(3)

        main_line = QLabel(
            f'<span style="color:#E74C3C;text-decoration:line-through;">'
            f"{self._original}</span>"
            f" &rarr; "
            f'<span style="color:#27AE60;font-weight:500;">'
            f"{self._replacement}</span>"
        )
        main_line.setTextFormat(Qt.TextFormat.RichText)
        main_line.setWordWrap(True)
        text_layout.addWidget(main_line)

        if self._explication:
            expl = QLabel(
                f'<span style="color:#888;font-size:11px;">'
                f"{self._type.capitalize()} — {self._explication}</span>"
            )
            expl.setTextFormat(Qt.TextFormat.RichText)
            expl.setWordWrap(True)
            text_layout.addWidget(expl)

        layout.addLayout(text_layout, 1)

        # Boutons "Appliquer" et "Ignorer" empilés verticalement
        btn_col = QVBoxLayout()
        btn_col.setSpacing(4)

        self._btn_apply = QPushButton("Appliquer")
        self._btn_apply.setFixedSize(80, 24)
        self._btn_apply.setStyleSheet(
            "font-size: 11px; border-radius: 4px;"
            "border: 0.5px solid #27AE60; color: #27AE60;"
        )
        self._btn_apply.clicked.connect(self._on_apply)

        self._btn_ignore = QPushButton("Ignorer")
        self._btn_ignore.setFixedSize(80, 24)
        self._btn_ignore.setStyleSheet(
            "font-size: 11px; border-radius: 4px;"
            "border: 0.5px solid #888; color: #888;"
        )
        self._btn_ignore.clicked.connect(self._on_ignore)

        btn_col.addWidget(self._btn_apply)
        btn_col.addWidget(self._btn_ignore)
        layout.addLayout(btn_col)

    # -- Actions ---------------------------------------------------------

    def _on_apply(self) -> None:
        """Applique la correction et marque visuellement l'item."""
        if self._applied or self._ignored:
            return
        self._applied = True
        self._btn_apply.setText("✓ Appliqué")
        self._btn_apply.setEnabled(False)
        self._btn_apply.setStyleSheet(
            "font-size: 11px; border-radius: 4px; border: 0.5px solid gray; color: gray;"
        )
        self._btn_ignore.setEnabled(False)
        self.setStyleSheet("background: rgba(39,174,96,0.08);")
        self.apply_requested.emit(self._original, self._replacement)

    def _on_ignore(self) -> None:
        """Marque l'item comme ignoré et déclenche l'animation de collapse."""
        if self._applied or self._ignored:
            return
        self._ignored = True
        self._btn_apply.setEnabled(False)
        self._btn_ignore.setText("✗ Ignoré")
        self._btn_ignore.setEnabled(False)
        self.setStyleSheet("background: rgba(0,0,0,0.04);")
        # Lancer le collapse après un court délai visuel
        QTimer.singleShot(350, self._collapse)
        self.ignore_requested.emit(self)

    def _collapse(self) -> None:
        """Réduit progressivement la hauteur de l'item pour le masquer."""
        target  = self.sizeHint().height()
        step    = [0]
        steps   = 8

        def _tick():
            step[0] += 1
            ratio  = step[0] / steps
            height = int(target * (1.0 - ratio))
            if height <= 2 or step[0] >= steps:
                self.hide()
                self.setMaximumHeight(16777215)  # reset
                return
            self.setFixedHeight(height)
            QTimer.singleShot(18, _tick)

        _tick()

    def mark_applied(self) -> None:
        """Applique sans animation (utilisé par 'Tout accepter' de section)."""
        if not self._applied and not self._ignored:
            self._on_apply()

    def mark_ignored(self) -> None:
        """Ignore sans animation (utilisé par 'Tout ignorer' de section)."""
        if not self._applied and not self._ignored:
            self._ignored = True
            self.hide()


# ===========================================================================
# Classe : CorrectionItem
# ===========================================================================

class CorrectionItem(_BaseItem):
    """Widget d'une correction individuelle (faute détectée)."""

    _replacement_key = "correction"

    _TYPE_COLORS = {
        "orthographe":  "#E74C3C",
        "grammaire":    "#E67E22",
        "conjugaison":  "#9B59B6",
        "accord":       "#2980B9",
        "ponctuation":  "#27AE60",
    }

    def _dot_color(self, type_str: str) -> str:
        return self._TYPE_COLORS.get(type_str.lower(), "#E74C3C")


# ===========================================================================
# Classe : SuggestionItem
# ===========================================================================

class SuggestionItem(_BaseItem):
    """Widget d'une suggestion individuelle (amélioration optionnelle)."""

    _replacement_key = "suggestion"

    _TYPE_COLORS = {
        "synonyme":      "#8E44AD",
        "reformulation": "#16A085",
    }

    def _dot_color(self, type_str: str) -> str:
        return self._TYPE_COLORS.get(type_str.lower(), "#8E44AD")


# ===========================================================================
# Classe : _SectionWidget
# Section du panneau avec en-tête coloré et compteur dynamique.
# ===========================================================================

class _SectionWidget(QWidget):
    """
    Section réutilisable du panneau : en-tête coloré + liste d'items.
    Compteur dynamique mis à jour quand des items sont ignorés.
    """

    apply_requested = Signal(str, str)

    def __init__(self, title: str, color: str, item_class: type, parent=None) -> None:
        super().__init__(parent)
        self._title      = title
        self._color      = color
        self._item_class = item_class
        self._items: list = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # En-tête de section
        header = QWidget()
        header.setStyleSheet(
            f"background: {self._color}; "
            "border-bottom: 0.5px solid rgba(0,0,0,0.2);"
        )
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(10, 6, 10, 6)
        self._header_lbl = QLabel(f"{self._title} — 0")
        self._header_lbl.setStyleSheet(
            "color: white; font-size: 12px; font-weight: 500;"
        )
        h_layout.addWidget(self._header_lbl)
        layout.addWidget(header)

        # Contenu
        self._content        = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(0)

        self._empty_lbl = QLabel("Aucun élément.")
        self._empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_lbl.setStyleSheet("color: gray; font-size: 12px; padding: 10px;")
        self._content_layout.addWidget(self._empty_lbl)

        layout.addWidget(self._content)

    # -- API publique ----------------------------------------------------

    def set_items(self, data_list: list) -> None:
        """Peuple la section avec les données."""
        self._clear()
        if not data_list:
            self._empty_lbl.show()
            self._update_counter()
            return

        self._empty_lbl.hide()
        for i, data in enumerate(data_list):
            if i > 0:
                sep = QFrame()
                sep.setFrameShape(QFrame.Shape.HLine)
                sep.setStyleSheet("color: rgba(0,0,0,0.07);")
                self._content_layout.addWidget(sep)

            item = self._item_class(data)
            item.apply_requested.connect(self.apply_requested)
            item.ignore_requested.connect(self._on_ignored)
            self._content_layout.addWidget(item)
            self._items.append(item)

        self._update_counter()

    def accept_all(self) -> None:
        for item in self._items:
            item.mark_applied()

    def ignore_all(self) -> None:
        for item in self._items:
            item.mark_ignored()
        self._empty_lbl.show()
        self._update_counter()

    def clear(self) -> None:
        self._clear()
        self._empty_lbl.show()
        self._update_counter()

    # -- Helpers ---------------------------------------------------------

    def _clear(self) -> None:
        """Supprime tous les items et séparateurs."""
        for item in self._items:
            item.setParent(None)   # type: ignore[call-overload]
            item.deleteLater()
        self._items.clear()

        # Supprimer les séparateurs et widgets supplémentaires
        # (on garde toujours self._empty_lbl à la position 0)
        while self._content_layout.count() > 1:
            layout_item = self._content_layout.itemAt(0)
            if layout_item is None:
                break
            w = layout_item.widget()
            if w is not None and w is not self._empty_lbl:
                self._content_layout.removeWidget(w)
                w.setParent(None)  # type: ignore[call-overload]
                w.deleteLater()
            else:
                break

    def _on_ignored(self, _: object) -> None:
        QTimer.singleShot(420, self._update_counter)

    def _update_counter(self) -> None:
        """Recalcule et affiche le nombre d'items encore visibles."""
        visible = sum(1 for item in self._items if item.isVisible())
        self._header_lbl.setText(f"{self._title} — {visible}")


# ===========================================================================
# Classe : CorrectionPanel
# Panneau latéral principal avec sections Corrections et Suggestions.
# ===========================================================================

class CorrectionPanel(QWidget):
    """
    Panneau latéral principal du correcteur IA (v0.7.1).

    Deux sections distinctes :
      - Corrections (rouge)  : fautes détectées
      - Suggestions (violet) : améliorations optionnelles

    Chaque item dispose de ses boutons "Appliquer" et "Ignorer".
    Boutons globaux par section + bouton global supprimer modèle.

    Signaux :
      apply_correction(str, str)   : (original, remplacement) à appliquer
      delete_model_requested()
    """

    apply_correction       = Signal(str, str)
    delete_model_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # -- Barre de titre -------------------------------------------
        header = QWidget()
        header.setStyleSheet("background: #2C3E50;")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(10, 8, 10, 8)

        self._title_lbl = QLabel("Corrections IA")
        self._title_lbl.setStyleSheet(
            "color: white; font-size: 13px; font-weight: 500;"
        )
        h_layout.addWidget(self._title_lbl)
        h_layout.addStretch()

        self._score_lbl = QLabel("")
        self._score_lbl.setTextFormat(Qt.TextFormat.RichText)
        h_layout.addWidget(self._score_lbl)

        layout.addWidget(header)

        # -- Zone scrollable ------------------------------------------
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; }")

        scroll_content = QWidget()
        scroll_layout  = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(0)

        # Message d'état global
        self._state_lbl = QLabel("Appuyez sur F7 pour analyser le texte.")
        self._state_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._state_lbl.setStyleSheet(
            "color: gray; font-size: 12px; padding: 24px 16px;"
        )
        self._state_lbl.setWordWrap(True)
        scroll_layout.addWidget(self._state_lbl)

        # Section Corrections
        self._sec_corrections = _SectionWidget(
            title="Corrections", color="#C0392B", item_class=CorrectionItem
        )
        self._sec_corrections.apply_requested.connect(self.apply_correction)
        self._sec_corrections.hide()
        scroll_layout.addWidget(self._sec_corrections)

        # Section Suggestions
        self._sec_suggestions = _SectionWidget(
            title="Suggestions", color="#7D3C98", item_class=SuggestionItem
        )
        self._sec_suggestions.apply_requested.connect(self.apply_correction)
        self._sec_suggestions.hide()
        scroll_layout.addWidget(self._sec_suggestions)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, 1)

        # -- Barre d'actions globales ---------------------------------
        actions = QWidget()
        actions.setStyleSheet("border-top: 1px solid rgba(0,0,0,0.15);")
        a_layout = QHBoxLayout(actions)
        a_layout.setContentsMargins(8, 6, 8, 6)
        a_layout.setSpacing(4)

        def _btn(label, color, tooltip=""):
            b = QPushButton(label)
            b.setStyleSheet(
                f"font-size: 11px; color: {color};"
                f"border: 0.5px solid {color}; border-radius: 4px; padding: 3px 6px;"
            )
            if tooltip:
                b.setToolTip(tooltip)
            return b

        btn_ac = _btn("✓ Correct.", "#27AE60", "Accepter toutes les corrections")
        btn_ac.clicked.connect(self._sec_corrections.accept_all)

        btn_ic = _btn("✗ Correct.", "#E74C3C", "Ignorer toutes les corrections")
        btn_ic.clicked.connect(self._sec_corrections.ignore_all)

        btn_as = _btn("✓ Suggest.", "#8E44AD", "Accepter toutes les suggestions")
        btn_as.clicked.connect(self._sec_suggestions.accept_all)

        btn_is = _btn("✗ Suggest.", "#888", "Ignorer toutes les suggestions")
        btn_is.clicked.connect(self._sec_suggestions.ignore_all)

        btn_del = _btn("🗑", "#888", f"Supprimer {OLLAMA_MODEL}")
        btn_del.setFixedWidth(30)
        btn_del.clicked.connect(self.delete_model_requested)

        for b in (btn_ac, btn_ic, btn_as, btn_is):
            a_layout.addWidget(b)
        a_layout.addStretch()
        a_layout.addWidget(btn_del)

        layout.addWidget(actions)

    # -- API publique ----------------------------------------------------

    def set_loading(self, message: str = "Analyse en cours…") -> None:
        """Affiche un état de chargement."""
        self._state_lbl.setText(f"⏳ {message}")
        self._state_lbl.show()
        self._sec_corrections.hide()
        self._sec_suggestions.hide()
        self._title_lbl.setText("Corrections IA")
        self._score_lbl.setText("")

    def set_error(self, message: str) -> None:
        """Affiche un message d'erreur."""
        self._state_lbl.setText(f"❌ {message}")
        self._state_lbl.show()
        self._sec_corrections.hide()
        self._sec_suggestions.hide()

    def set_results(self, corrections: list, suggestions: list, score: int) -> None:
        """
        Affiche les résultats : corrections, suggestions et score.

        Parameters
        ----------
        corrections : list[dict]  — fautes détectées
        suggestions : list[dict]  — améliorations optionnelles
        score       : int 0–100   — qualité orthographique du texte
        """
        self._state_lbl.hide()

        # Score avec couleur adaptative
        color = "#27AE60" if score >= 80 else ("#E67E22" if score >= 50 else "#E74C3C")
        self._score_lbl.setText(
            f'<span style="color:{color};">Score : {score}/100</span>'
        )

        n_c = len(corrections)
        n_s = len(suggestions)
        title = f"Corrections IA — {n_c} erreur{'s' if n_c != 1 else ''}"
        if n_s:
            title += f", {n_s} suggestion{'s' if n_s != 1 else ''}"
        self._title_lbl.setText(title)

        # Sections
        if corrections:
            self._sec_corrections.set_items(corrections)
            self._sec_corrections.show()
        else:
            self._sec_corrections.hide()

        if suggestions:
            self._sec_suggestions.set_items(suggestions)
            self._sec_suggestions.show()
        else:
            self._sec_suggestions.hide()

        # Aucune erreur ni suggestion
        if not corrections and not suggestions:
            self._state_lbl.setText("✅ Texte parfait ! Aucune erreur détectée.")
            self._state_lbl.show()

    def clear(self) -> None:
        """Réinitialise le panneau."""
        self._sec_corrections.clear()
        self._sec_suggestions.clear()
        self._sec_corrections.hide()
        self._sec_suggestions.hide()
        self._state_lbl.setText("Appuyez sur F7 pour analyser le texte.")
        self._state_lbl.show()
        self._title_lbl.setText("Corrections IA")
        self._score_lbl.setText("")
