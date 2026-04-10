"""
ai_checker.py -- Module IA pour Glyph v0.9
=================================================================
Version Flet -- utilise threading au lieu de QThread.
Fournit la logique metier sans aucune dependance UI.

Composants :
  - AVAILABLE_MODELS     : catalogue des modeles telechargeables
  - OllamaManager        : detection, installation et gestion d'Ollama/modeles
  - OllamaInstaller      : telechargement d'Ollama dans un thread
  - ModelPuller           : pull d'un modele via `ollama pull` dans un thread
  - AIProcessor           : appel REST a l'API Ollama (multi-mode) dans un thread

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

# ---------------------------------------------------------------------------
# Imports internes
# ---------------------------------------------------------------------------
from ai_prompts import PROMPTS, USER_INSTRUCTIONS


# ===========================================================================
# Catalogue des modeles disponibles
# ===========================================================================

AVAILABLE_MODELS = [
    {
        "id": "qwen2.5:1.5b",
        "name": "Qwen 2.5",
        "params": "1.5B",
        "size": "934 MB",
        "size_bytes": 934 * 1024 * 1024,
        "description": "Modele polyvalent par Alibaba. Bon equilibre taille/qualite.",
        "languages": "Multilingue (FR, EN, ZH, +)",
        "recommended_ram": "2 Go",
        "strengths": "Polyvalent, rapide, bon en francais",
    },
    {
        "id": "mistral:3b",
        "name": "Mistral 3B",
        "params": "3B",
        "size": "1.9 GB",
        "size_bytes": 1900 * 1024 * 1024,
        "description": "Par Mistral AI (France). Excellente qualite pour sa taille.",
        "languages": "Multilingue (FR, EN, +)",
        "recommended_ram": "4 Go",
        "strengths": "Tres bon en francais, correction precise",
    },
    {
        "id": "gemma2:2b",
        "name": "Gemma 2",
        "params": "2B",
        "size": "1.6 GB",
        "size_bytes": 1600 * 1024 * 1024,
        "description": "Par Google. Compact et performant, bon suivi d'instructions.",
        "languages": "Multilingue (FR, EN, +)",
        "recommended_ram": "3 Go",
        "strengths": "Suivi d'instructions precis, rapide",
    },
    {
        "id": "llama3.2:1b",
        "name": "Llama 3.2",
        "params": "1B",
        "size": "1.3 GB",
        "size_bytes": 1300 * 1024 * 1024,
        "description": "Par Meta. Le plus leger de la famille Llama, tres rapide.",
        "languages": "Multilingue (FR, EN, +)",
        "recommended_ram": "2 Go",
        "strengths": "Ultra-rapide, leger",
    },
    {
        "id": "smollm2:1.7b",
        "name": "SmolLM2",
        "params": "1.7B",
        "size": "1.0 GB",
        "size_bytes": 1000 * 1024 * 1024,
        "description": "Par Hugging Face. Concu pour les appareils a ressources limitees.",
        "languages": "Multilingue (FR, EN, +)",
        "recommended_ram": "2 Go",
        "strengths": "Optimise pour les PC modestes",
    },
    {
        "id": "deepseek-r1:1.5b",
        "name": "DeepSeek R1",
        "params": "1.5B",
        "size": "1.1 GB",
        "size_bytes": 1100 * 1024 * 1024,
        "description": "Par DeepSeek. Modele de raisonnement compact.",
        "languages": "Multilingue (FR, EN, ZH, +)",
        "recommended_ram": "2 Go",
        "strengths": "Bon raisonnement, reformulation",
    },
    {
        "id": "tinyllama",
        "name": "TinyLlama",
        "params": "1.1B",
        "size": "637 MB",
        "size_bytes": 637 * 1024 * 1024,
        "description": "Le plus petit modele. Ideal pour tester sur des PC tres anciens.",
        "languages": "Anglais principalement, FR basique",
        "recommended_ram": "1.5 Go",
        "strengths": "Ultra-leger, le plus petit telechargement",
    },
]

# Index rapide par ID
MODELS_BY_ID = {m["id"]: m for m in AVAILABLE_MODELS}

# Modele par defaut recommande
DEFAULT_MODEL_ID = "qwen2.5:1.5b"


# ===========================================================================
# Constantes API
# ===========================================================================

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
# Utilitaires
# ===========================================================================

def check_internet(timeout=5) -> bool:
    """Verifie la connexion internet en contactant un serveur fiable."""
    try:
        urllib.request.urlopen("https://ollama.com", timeout=timeout)
        return True
    except Exception:
        pass
    try:
        urllib.request.urlopen("https://www.google.com", timeout=timeout)
        return True
    except Exception:
        return False


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
    def is_model_available(model_id: str) -> bool:
        """Verifie si un modele specifique est installe localement."""
        if not REQUESTS_AVAILABLE or _requests is None:
            return False
        try:
            r = _requests.get(OLLAMA_LIST_URL, timeout=5)
            data = r.json()
            names = [m.get("name", "") for m in data.get("models", [])]
            return any(model_id in n or n.startswith(model_id.split(":")[0]) and model_id in n
                       for n in names)
        except Exception:
            return False

    @staticmethod
    def list_installed_models() -> list[str]:
        """Retourne la liste des IDs de modeles installes."""
        if not REQUESTS_AVAILABLE or _requests is None:
            return []
        try:
            r = _requests.get(OLLAMA_LIST_URL, timeout=5)
            data = r.json()
            return [m.get("name", "") for m in data.get("models", [])]
        except Exception:
            return []

    @staticmethod
    def get_installed_catalog_models() -> list[dict]:
        """Retourne les modeles du catalogue qui sont installes."""
        installed = OllamaManager.list_installed_models()
        result = []
        for model in AVAILABLE_MODELS:
            for inst_name in installed:
                if model["id"] in inst_name or inst_name.startswith(model["id"]):
                    result.append(model)
                    break
        return result

    @staticmethod
    def delete_model(model_id: str) -> tuple[bool, str]:
        """Supprime un modele via `ollama rm`."""
        try:
            result = subprocess.run(
                ["ollama", "rm", model_id],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0:
                return True, f"Modele {model_id} supprime."
            return False, result.stderr.strip() or "Erreur inconnue."
        except FileNotFoundError:
            return False, "Ollama n'est pas installe."
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
            self._on_error("Plateforme non supportee pour l'installation automatique.")
            return

        if not check_internet():
            self._on_error("Pas de connexion internet. Verifiez votre reseau.")
            return

        try:
            self._on_progress(5, "Connexion aux serveurs Ollama...")

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
                self._on_progress(pct, f"Telechargement Ollama... {downloaded // (1024*1024)} MB")
                elapsed = time.time() - start_time[0]
                if elapsed >= 0.5:
                    speed = (downloaded - last_downloaded[0]) / elapsed / (1024 * 1024)
                    self._on_speed(f"{speed:.1f} MB/s")
                    start_time[0] = time.time()
                    last_downloaded[0] = downloaded

            urllib.request.urlretrieve(url, dest, reporthook=reporthook)
            self._on_progress(85, "Installation en cours...")

            if plat == "Windows":
                subprocess.run([dest, "/S"], check=True, timeout=120)
            elif plat == "Darwin":
                subprocess.run(["unzip", "-o", dest, "-d", "/Applications"], check=True)

            self._on_progress(100, "Ollama installe avec succes.")
            self._on_done("Ollama a ete installe. Relancez l'application si necessaire.")

        except Exception as exc:
            self._on_error(f"Erreur d'installation : {exc}")

    def _install_linux(self, url):
        self._on_progress(10, "Lancement du script d'installation Linux...")
        try:
            result = subprocess.run(
                f"curl -fsSL {url} | sh",
                shell=True, capture_output=True, text=True, timeout=300,
            )
            if result.returncode == 0:
                self._on_progress(100, "Ollama installe.")
                self._on_done("Ollama installe via le script officiel.")
            else:
                self._on_error(result.stderr or "Erreur d'installation Linux.")
        except Exception as exc:
            self._on_error(str(exc))


# ===========================================================================
# Classe : ModelPuller
# Telecharge un modele via `ollama pull` dans un thread.
# ===========================================================================

class ModelPuller:
    """
    Pull d'un modele avec callbacks.

    Callbacks :
      on_progress(pct: int, msg: str)
      on_speed(speed_str: str)
      on_done()
      on_error(msg: str)
      on_cancelled()
    """

    def __init__(self, model_id, on_progress=None, on_speed=None, on_done=None,
                 on_error=None, on_cancelled=None):
        self._model_id = model_id
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
        if not check_internet():
            self._on_error("Pas de connexion internet. Verifiez votre reseau.")
            return

        try:
            model_info = MODELS_BY_ID.get(self._model_id)
            display_name = model_info["name"] if model_info else self._model_id
            self._on_progress(0, f"Demarrage du telechargement de {display_name}...")

            self._process = subprocess.Popen(
                ["ollama", "pull", self._model_id],
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

                    self._on_progress(pct, f"{status} -- {completed_mb:.0f} / {total_mb:.0f} MB")
                else:
                    self._on_progress(1, status)

            self._process.wait()

            if self._cancel_requested:
                self._on_cancelled()
                return

            if self._process.returncode == 0:
                self._on_progress(100, "Modele pret.")
                self._on_done()
            else:
                self._on_error(f"ollama pull a echoue (code {self._process.returncode}).")

        except FileNotFoundError:
            self._on_error("Ollama est introuvable dans le PATH.")
        except Exception as exc:
            self._on_error(f"Erreur inattendue : {exc}")


# ===========================================================================
# Classe : AIProcessor
# Envoie le texte a l'API Ollama et parse la reponse JSON (multi-mode).
# ===========================================================================

class AIProcessor:
    """
    Processeur IA multi-mode via Ollama.

    Supporte : correction, traduction, reformulation, resume, mots-cles.

    Callbacks :
      on_result(parsed_data: dict)
      on_error(msg: str)
      on_status(msg: str)
      on_stream(chunk: str)    — pour le mode streaming (optionnel)
    """

    def __init__(self, on_result=None, on_error=None, on_status=None, on_stream=None):
        self._on_result = on_result or (lambda *a: None)
        self._on_error = on_error or (lambda *a: None)
        self._on_status = on_status or (lambda *a: None)
        self._on_stream = on_stream or (lambda *a: None)
        self._thread = None

    def process(self, text: str, mode: str, model_id: str, stream: bool = False):
        """Lance le traitement IA dans un thread."""
        self._thread = threading.Thread(
            target=self._run, args=(text, mode, model_id, stream), daemon=True,
        )
        self._thread.start()

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _run(self, text: str, mode: str, model_id: str, stream: bool):
        if not REQUESTS_AVAILABLE:
            self._on_error(
                "Le module 'requests' n'est pas installe.\n"
                "Lancez : pip install requests"
            )
            return

        if not text.strip():
            self._on_result({})
            return

        system_prompt = PROMPTS.get(mode)
        user_instruction = USER_INSTRUCTIONS.get(mode)
        if not system_prompt or not user_instruction:
            self._on_error(f"Mode IA inconnu : {mode}")
            return

        model_info = MODELS_BY_ID.get(model_id)
        display_name = model_info["name"] if model_info else model_id
        from ai_prompts import MODE_LABELS
        mode_label = MODE_LABELS.get(mode, mode)
        self._on_status(f"{mode_label} avec {display_name}...")

        payload = {
            "model": model_id,
            "prompt": user_instruction.format(text=text),
            "system": system_prompt,
            "stream": stream,
            "options": {
                "temperature": 0.1,
                "top_p": 0.9,
                "num_predict": 4096,
            },
        }

        try:
            if _requests is None:
                self._on_error("Le module 'requests' n'est pas disponible.")
                return

            if stream:
                self._run_streaming(payload)
            else:
                self._run_sync(payload)

        except Exception as exc:
            exc_name = type(exc).__name__
            if "ConnectionError" in exc_name:
                self._on_error(
                    "Impossible de joindre Ollama (localhost:11434).\n"
                    "Verifiez qu'Ollama est bien lance."
                )
            elif "Timeout" in exc_name:
                self._on_error(
                    f"Delai depasse ({API_TIMEOUT} s). Le modele est trop lent\n"
                    "ou le texte est trop long. Essayez avec un texte plus court."
                )
            else:
                self._on_error(f"Erreur lors du traitement : {exc}")

    def _run_sync(self, payload):
        """Appel synchrone (attend la reponse complete)."""
        response = _requests.post(OLLAMA_API_URL, json=payload, timeout=API_TIMEOUT)
        response.raise_for_status()

        raw = response.json().get("response", "").strip()
        parsed = self._extract_json(raw)

        if parsed is None:
            self._on_error(
                "La reponse du modele n'est pas du JSON valide.\n"
                f"Debut : {raw[:200]}"
            )
            return

        self._on_result(parsed)

    def _run_streaming(self, payload):
        """Appel en streaming (affiche au fur et a mesure)."""
        response = _requests.post(
            OLLAMA_API_URL, json=payload, timeout=API_TIMEOUT, stream=True,
        )
        response.raise_for_status()

        full_response = ""
        for line in response.iter_lines(decode_unicode=True):
            if not line:
                continue
            try:
                data = json.loads(line)
                chunk = data.get("response", "")
                full_response += chunk
                if chunk:
                    self._on_stream(chunk)
                if data.get("done", False):
                    break
            except json.JSONDecodeError:
                continue

        parsed = self._extract_json(full_response.strip())
        if parsed is None:
            self._on_error(
                "La reponse du modele n'est pas du JSON valide.\n"
                f"Debut : {full_response[:200]}"
            )
            return

        self._on_result(parsed)

    @staticmethod
    def _extract_json(text: str):
        """Extrait le premier objet JSON valide du texte."""
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
