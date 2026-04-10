"""
ai_checker.py — Module de correction IA pour Glyph v0.9
=================================================================
Version Flet — utilise threading au lieu de QThread.
Fournit la logique metier sans aucune dependance UI.

Composants :
  - OllamaManager       : detection, installation et gestion d'Ollama/modele
  - OllamaInstaller     : telechargement d'Ollama dans un thread
  - ModelPuller          : pull du modele ministral-3:3b dans un thread
  - GrammarChecker       : appel REST a l'API Ollama dans un thread

Les composants UI (SetupDialog, CorrectionPanel, etc.) sont desormais
dans le fichier principal glyph.py (Flet).

Dependances Python : requests
Dependances systeme : Ollama >= 0.13.1

Auteur  : Arnaud
Licence : CC BY-NC-ND 4.0
Version : 0.9
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
import threading
import time
import urllib.request

# ---------------------------------------------------------------------------
# Imports tiers
# ---------------------------------------------------------------------------
try:
    import requests as _requests
    REQUESTS_AVAILABLE = True
except ImportError:
    _requests = None
    REQUESTS_AVAILABLE = False


# ===========================================================================
# Constantes
# ===========================================================================

OLLAMA_MODEL = "ministral-3:3b"
MODEL_SIZE_DISPLAY = "3.0 GB"

OLLAMA_API_URL    = "http://localhost:11434/api/generate"
OLLAMA_HEALTH_URL = "http://localhost:11434/"
OLLAMA_LIST_URL   = "http://localhost:11434/api/tags"

OLLAMA_DOWNLOAD_URLS = {
    "Windows": "https://ollama.com/download/OllamaSetup.exe",
    "Darwin":  "https://ollama.com/download/Ollama-darwin.zip",
    "Linux":   "https://ollama.com/install.sh",
}

API_TIMEOUT = 120


# ===========================================================================
# Prompt systeme v0.7.1
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
    """Classe utilitaire statique pour la detection et la gestion d'Ollama."""

    @staticmethod
    def is_ollama_installed() -> bool:
        return shutil.which("ollama") is not None

    @staticmethod
    def is_server_running() -> bool:
        if not REQUESTS_AVAILABLE or _requests is None:
            return False
        try:
            r = _requests.get(OLLAMA_HEALTH_URL, timeout=3)
            return r.status_code == 200
        except Exception:
            return False

    @staticmethod
    def start_server() -> bool:
        try:
            if platform.system() == "Windows":
                subprocess.Popen(
                    ["ollama", "serve"],
                    creationflags=subprocess.CREATE_NO_WINDOW,
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
        if not REQUESTS_AVAILABLE or _requests is None:
            return False
        try:
            r = _requests.get(OLLAMA_LIST_URL, timeout=5)
            data = r.json()
            names = [m.get("name", "") for m in data.get("models", [])]
            return any(OLLAMA_MODEL in n or n in OLLAMA_MODEL for n in names)
        except Exception:
            return False

    @staticmethod
    def delete_model() -> tuple:
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
        return OLLAMA_DOWNLOAD_URLS.get(platform.system())

    @staticmethod
    def get_platform_name() -> str:
        return {"Windows": "Windows", "Darwin": "macOS", "Linux": "Linux"}.get(
            platform.system(), platform.system()
        )


# ===========================================================================
# Classe : OllamaInstaller
# Telecharge et installe Ollama dans un thread separe.
# ===========================================================================

class OllamaInstaller:
    """
    Telechargeur/installeur d'Ollama avec callbacks.

    Callbacks :
      on_progress(pct: int, msg: str)
      on_speed(speed_str: str)
      on_done(msg: str)
      on_error(msg: str)
    """

    def __init__(self, on_progress=None, on_speed=None, on_done=None, on_error=None):
        self._on_progress = on_progress or (lambda *a: None)
        self._on_speed = on_speed or (lambda *a: None)
        self._on_done = on_done or (lambda *a: None)
        self._on_error = on_error or (lambda *a: None)
        self._thread = None

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        url = OllamaManager.get_download_url()
        plat = platform.system()

        if url is None:
            self._on_error("Plateforme non supportée pour l'installation automatique.")
            return

        try:
            self._on_progress(5, "Connexion aux serveurs Ollama…")

            if plat == "Linux":
                self._install_linux(url)
                return

            tmpdir = tempfile.mkdtemp()
            ext = ".exe" if plat == "Windows" else ".zip"
            dest = os.path.join(tmpdir, f"ollama_installer{ext}")

            start_time = [time.time()]
            last_downloaded = [0]

            def reporthook(block_num, block_size, total_size):
                downloaded = block_num * block_size
                pct = min(int(downloaded / total_size * 80), 80) if total_size > 0 else 0
                self._on_progress(pct, f"Téléchargement Ollama… {downloaded // (1024*1024)} MB")
                elapsed = time.time() - start_time[0]
                if elapsed >= 0.5:
                    speed = (downloaded - last_downloaded[0]) / elapsed / (1024 * 1024)
                    self._on_speed(f"{speed:.1f} MB/s")
                    start_time[0] = time.time()
                    last_downloaded[0] = downloaded

            urllib.request.urlretrieve(url, dest, reporthook=reporthook)
            self._on_progress(85, "Installation en cours…")

            if plat == "Windows":
                subprocess.run([dest, "/S"], check=True, timeout=120)
            elif plat == "Darwin":
                subprocess.run(["unzip", "-o", dest, "-d", "/Applications"], check=True)

            self._on_progress(100, "Ollama installé avec succès.")
            self._on_done("Ollama a été installé. Relancez l'application si nécessaire.")

        except Exception as exc:
            self._on_error(f"Erreur d'installation : {exc}")

    def _install_linux(self, url):
        self._on_progress(10, "Lancement du script d'installation Linux…")
        try:
            result = subprocess.run(
                f"curl -fsSL {url} | sh",
                shell=True, capture_output=True, text=True, timeout=300,
            )
            if result.returncode == 0:
                self._on_progress(100, "Ollama installé.")
                self._on_done("Ollama installé via le script officiel.")
            else:
                self._on_error(result.stderr or "Erreur d'installation Linux.")
        except Exception as exc:
            self._on_error(str(exc))


# ===========================================================================
# Classe : ModelPuller
# Telecharge ministral-3:3b via `ollama pull` dans un thread.
# ===========================================================================

class ModelPuller:
    """
    Pull du modele ministral-3:3b avec callbacks.

    Callbacks :
      on_progress(pct: int, msg: str)
      on_speed(speed_str: str)
      on_done()
      on_error(msg: str)
      on_cancelled()
    """

    def __init__(self, on_progress=None, on_speed=None, on_done=None,
                 on_error=None, on_cancelled=None):
        self._on_progress = on_progress or (lambda *a: None)
        self._on_speed = on_speed or (lambda *a: None)
        self._on_done = on_done or (lambda: None)
        self._on_error = on_error or (lambda *a: None)
        self._on_cancelled = on_cancelled or (lambda: None)
        self._cancel_requested = False
        self._process = None
        self._thread = None

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def request_cancel(self):
        self._cancel_requested = True
        if self._process is not None:
            self._process.terminate()

    def _run(self):
        try:
            self._on_progress(0, f"Démarrage du téléchargement de {OLLAMA_MODEL}…")

            self._process = subprocess.Popen(
                ["ollama", "pull", OLLAMA_MODEL],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            assert self._process.stdout is not None

            last_time = time.time()
            last_completed = 0

            for raw_line in self._process.stdout:
                if self._cancel_requested:
                    self._process.terminate()
                    self._on_cancelled()
                    return

                line = raw_line.strip()
                if not line:
                    continue

                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    self._on_progress(1, line)
                    continue

                status = data.get("status", "")
                total = data.get("total", 0)
                completed = data.get("completed", 0)

                if total and total > 0:
                    pct = int(completed / total * 100)
                    completed_mb = completed / (1024 * 1024)
                    total_mb = total / (1024 * 1024)

                    now = time.time()
                    elapsed = now - last_time
                    if elapsed >= 1.0:
                        delta = completed - last_completed
                        speed_mbs = delta / (1024 * 1024) / elapsed
                        rem_mb = (total - completed) / (1024 * 1024)
                        eta_sec = int(rem_mb / speed_mbs) if speed_mbs > 0 else 0
                        eta_str = (
                            f"{eta_sec // 60} min {eta_sec % 60} s"
                            if eta_sec >= 60 else f"{eta_sec} s"
                        )
                        self._on_speed(f"{speed_mbs:.1f} MB/s  ·  ETA {eta_str}")
                        last_time = now
                        last_completed = completed

                    self._on_progress(pct, f"{status} — {completed_mb:.0f} / {total_mb:.0f} MB")
                else:
                    self._on_progress(1, status)

            self._process.wait()

            if self._cancel_requested:
                self._on_cancelled()
                return

            if self._process.returncode == 0:
                self._on_progress(100, "Modèle prêt.")
                self._on_done()
            else:
                self._on_error(f"ollama pull a échoué (code {self._process.returncode}).")

        except FileNotFoundError:
            self._on_error("Ollama est introuvable dans le PATH.")
        except Exception as exc:
            self._on_error(f"Erreur inattendue : {exc}")


# ===========================================================================
# Classe : GrammarChecker
# Envoie le texte a l'API Ollama et parse la reponse JSON.
# ===========================================================================

class GrammarChecker:
    """
    Correcteur grammatical IA via Ollama.

    Callbacks :
      on_result(corrections: list, suggestions: list, score: int)
      on_error(msg: str)
      on_status(msg: str)
    """

    def __init__(self, on_result=None, on_error=None, on_status=None):
        self._on_result = on_result or (lambda *a: None)
        self._on_error = on_error or (lambda *a: None)
        self._on_status = on_status or (lambda *a: None)
        self._thread = None

    def check(self, text: str):
        """Lance l'analyse dans un thread."""
        self._thread = threading.Thread(target=self._run, args=(text,), daemon=True)
        self._thread.start()

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _run(self, text: str):
        if not REQUESTS_AVAILABLE:
            self._on_error(
                "Le module 'requests' n'est pas installé.\n"
                "Lancez : pip install requests"
            )
            return

        if not text.strip():
            self._on_result([], [], 100)
            return

        self._on_status(f"Analyse avec {OLLAMA_MODEL}…")

        payload = {
            "model": OLLAMA_MODEL,
            "prompt": (
                "Voici le texte français à analyser :\n\n"
                f"{text}\n\n"
                "Retourne uniquement le JSON de corrections et suggestions."
            ),
            "system": GRAMMAR_SYSTEM_PROMPT,
            "stream": False,
            "options": {
                "temperature": 0.1,
                "top_p": 0.9,
                "num_predict": 2048,
            },
        }

        try:
            if _requests is None:
                self._on_error("Le module 'requests' n'est pas disponible.")
                return

            response = _requests.post(OLLAMA_API_URL, json=payload, timeout=API_TIMEOUT)
            response.raise_for_status()

            raw = response.json().get("response", "").strip()
            parsed = self._extract_json(raw)

            if parsed is None:
                self._on_error(
                    "La réponse du modèle n'est pas du JSON valide.\n"
                    f"Début : {raw[:200]}"
                )
                return

            corrections = self._validate_corrections(parsed.get("corrections", []))
            suggestions = self._validate_suggestions(parsed.get("suggestions", []))
            score = max(0, min(100, int(parsed.get("score", 100))))

            self._on_result(corrections, suggestions, score)

        except Exception as exc:
            exc_name = type(exc).__name__
            if "ConnectionError" in exc_name:
                self._on_error(
                    "Impossible de joindre Ollama (localhost:11434).\n"
                    "Vérifiez qu'Ollama est bien lancé."
                )
            elif "Timeout" in exc_name:
                self._on_error(
                    f"Délai dépassé ({API_TIMEOUT} s). Le modèle est trop lent."
                )
            else:
                self._on_error(f"Erreur lors de l'analyse : {exc}")

    @staticmethod
    def _validate_corrections(raw: list) -> list:
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
                    "type":        str(c.get("type", "orthographe")).strip(),
                    "explication": str(c.get("explication", "")).strip(),
                })
        return result

    @staticmethod
    def _validate_suggestions(raw: list) -> list:
        result = []
        for s in raw:
            if not isinstance(s, dict):
                continue
            orig = str(s.get("original", "")).strip()
            sug = str(s.get("suggestion", "")).strip()
            if orig and sug and orig != sug:
                result.append({
                    "original":    orig,
                    "suggestion":  sug,
                    "type":        str(s.get("type", "reformulation")).strip(),
                    "explication": str(s.get("explication", "")).strip(),
                })
        return result

    @staticmethod
    def _extract_json(text: str):
        text = re.sub(r"```(?:json)?", "", text).strip()
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
