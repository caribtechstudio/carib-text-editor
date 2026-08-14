"""
models/ollama.py — Détection du moteur local Ollama.

Remplace l'ancien `ai_checker.py`, qui portait 480 lignes dont la quasi-totalité
était devenue morte une fois la couche `models/llm/` en place :

  * `AVAILABLE_MODELS` — catalogue de modèles codé en dur, déjà périmé. La
    liste vient désormais de `GET /v1/models`, donc elle ne vieillit plus.
  * `ModelPuller` — téléchargement de modèles via `ollama pull`. Plus aucune
    interface ne l'appelait.
  * `OllamaInstaller` — **exécutait un script distant** via
    `subprocess.run("curl -fsSL … | sh", shell=True)`, sans vérifier ni
    signature ni somme de contrôle. Embarquer cela dans un éditeur de texte
    n'était pas défendable ; le dialogue IA renvoie maintenant vers la page
    de téléchargement officielle, où l'utilisateur voit ce qu'il installe.

Il ne reste ici que ce dont l'application se sert réellement : savoir si
Ollama est présent et le démarrer.
"""

import platform
import shutil
import socket
import subprocess

OLLAMA_HOST = "127.0.0.1"
OLLAMA_PORT = 11434
DOWNLOAD_PAGE = "https://ollama.com/download"

#: Modèles suggérés à l'utilisateur s'il n'en a aucun. Purement indicatif :
#: aucune logique ne dépend de cette liste.
SUGGESTED_MODELS = ("qwen2.5:3b", "llama3.2:3b", "mistral:7b")


class OllamaManager:
    """Présence et démarrage du serveur Ollama local."""

    @staticmethod
    def is_ollama_installed() -> bool:
        return shutil.which("ollama") is not None

    @staticmethod
    def is_server_running(timeout: float = 0.35) -> bool:
        """Test de connexion local, sans requête HTTP ni appel distant."""
        try:
            with socket.create_connection((OLLAMA_HOST, OLLAMA_PORT), timeout=timeout):
                return True
        except OSError:
            return False

    @staticmethod
    def start_server() -> bool:
        """Lance `ollama serve` en arrière-plan. Retourne False si introuvable."""
        try:
            if platform.system() == "Windows":
                subprocess.Popen(["ollama", "serve"],
                                 creationflags=subprocess.CREATE_NO_WINDOW)
            else:
                subprocess.Popen(["ollama", "serve"],
                                 stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
            return True
        except (FileNotFoundError, OSError):
            return False

    @staticmethod
    def platform_name() -> str:
        return {"Windows": "Windows", "Darwin": "macOS",
                "Linux": "Linux"}.get(platform.system(), platform.system())
