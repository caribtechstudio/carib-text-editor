"""
Tests d'intégration de la couche LLM, contre un **vrai serveur HTTP**.

Pourquoi pas un simple `mock` ? Parce que ce qui casse en production n'est
presque jamais la logique métier, mais le transport : découpage des trames
SSE, en-tête `Retry-After`, code d'erreur mal interprété, connexion qui ne se
ferme pas à l'annulation. Un objet simulé passerait à côté de tout cela.

Le serveur ci-dessous parle le protocole `/chat/completions` d'OpenAI — le
même que Claude, Gemini et Ollama exposent. Ce qui est validé ici vaut donc
pour les quatre fournisseurs.

Ce que ces tests ne prouvent pas : que les identifiants de modèles réels
existent, ni que les quotas d'un compte donné se comportent comme prévu.
Cela demande une vraie clé.
"""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from models.llm.base import (AuthError, CancelledError, ModelError, NetworkError,
                             QuotaError, RateLimitError)
from models.llm.client import CancelToken, OpenAICompatClient
from models.llm.registry import ProviderConfig


# ===========================================================================
# Serveur de test
# ===========================================================================

class _Scenario:
    """Ce que le serveur doit répondre au prochain appel."""

    def __init__(self):
        self.mode = "ok"
        self.calls = 0
        self.rate_limit_before = 0          # nb de 429 avant de réussir
        self.last_payload = None
        self.last_headers = None
        self.stream_delay = 0.0


SCENARIO = _Scenario()


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass                                # silence pendant les tests

    def handle_one_request(self):
        # Le test d'annulation coupe la connexion au milieu d'un flux : c'est
        # le comportement attendu, pas une trace d'erreur à afficher.
        try:
            super().handle_one_request()
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            self.close_connection = True

    # ------------------------------------------------------------------
    def _send_json(self, code: int, payload: dict, headers: dict | None = None):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    # ------------------------------------------------------------------
    def do_GET(self):
        if not self.path.endswith("/models"):
            self._send_json(404, {"error": {"message": "inconnu"}})
            return
        if SCENARIO.mode == "auth_error":
            self._send_json(401, {"error": {"message": "Invalid API key"}})
            return
        self._send_json(200, {"data": [
            {"id": "gpt-4.1-mini"}, {"id": "gpt-4.1-nano"}, {"id": "gpt-4.1"},
            {"id": "text-embedding-3-small"},        # doit être filtré
            {"id": "whisper-1"},                     # doit être filtré
        ]})

    # ------------------------------------------------------------------
    def do_POST(self):
        SCENARIO.calls += 1
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        SCENARIO.last_payload = json.loads(raw or b"{}")
        SCENARIO.last_headers = dict(self.headers)

        mode = SCENARIO.mode

        if SCENARIO.rate_limit_before >= SCENARIO.calls:
            self._send_json(429, {"error": {"message": "slow down"}},
                            {"Retry-After": "0"})
            return

        handlers = {
            "auth_error": lambda: self._send_json(
                401, {"error": {"message": "Invalid API key"}}),
            "quota": lambda: self._send_json(
                429, {"error": {"message": "You exceeded your current quota"}}),
            "not_found": lambda: self._send_json(
                404, {"error": {"message": "model not found"}}),
            "bad_request": lambda: self._send_json(
                400, {"error": {"message": "context length exceeded"}}),
            "server_error": lambda: self._send_json(
                500, {"error": {"message": "internal"}}),
        }
        if mode in handlers:
            handlers[mode]()
            return

        if SCENARIO.last_payload.get("stream"):
            self._send_stream()
        else:
            self._send_json(200, {
                "choices": [{"message": {"content": "Bonjour le monde."}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 5},
            })

    # ------------------------------------------------------------------
    def _send_stream(self):
        """Réponse SSE, découpée comme le ferait un vrai fournisseur."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()

        pieces = ["Bon", "jour", " le", " monde", "."]
        if SCENARIO.mode == "stream_json":
            pieces = ['{"result"', ': "corr', 'igé", ', '"changes": []}']

        def chunk(data: str):
            payload = data.encode("utf-8")
            self.wfile.write(f"{len(payload):X}\r\n".encode())
            self.wfile.write(payload + b"\r\n")
            self.wfile.flush()

        try:
            for piece in pieces:
                chunk("data: " + json.dumps(
                    {"choices": [{"delta": {"content": piece}}]}) + "\n\n")
                if SCENARIO.stream_delay:
                    time.sleep(SCENARIO.stream_delay)
            chunk("data: " + json.dumps({
                "choices": [{"delta": {}}],
                "usage": {"prompt_tokens": 7, "completion_tokens": 3},
            }) + "\n\n")
            chunk("data: [DONE]\n\n")
            self.wfile.write(b"0\r\n\r\n")
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass                            # le client a annulé : c'est attendu


@pytest.fixture(scope="module")
def server():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}/v1"
    httpd.shutdown()


@pytest.fixture
def client(server):
    SCENARIO.mode = "ok"
    SCENARIO.calls = 0
    SCENARIO.rate_limit_before = 0
    SCENARIO.stream_delay = 0.0
    cfg = ProviderConfig(key="openai", label="ChatGPT", base_url=server,
                         supports_json_schema=True, key_prefix="sk-",
                         hide_patterns=("embedding", "whisper"),
                         price_hint=(0.35, 1.40))
    return OpenAICompatClient(cfg, "sk-test-1234567890")


# ===========================================================================
# Modèles
# ===========================================================================

def test_liste_des_modeles_et_filtrage(client):
    models = client.list_models()
    ids = [m.id for m in models]
    assert "gpt-4.1-mini" in ids
    # Les modèles hors-sujet ne doivent pas polluer le sélecteur.
    assert "text-embedding-3-small" not in ids
    assert "whisper-1" not in ids


def test_validation_reussie(client):
    ok, message = client.validate()
    assert ok and "modèles" in message


def test_validation_refuse_une_cle_mal_formee(client):
    client.api_key = "pas-une-cle-openai"
    ok, message = client.validate()
    assert not ok and "sk-" in message
    # Aucun appel réseau ne doit partir pour une clé manifestement invalide.
    assert SCENARIO.calls == 0


def test_validation_signale_une_cle_rejetee(client):
    SCENARIO.mode = "auth_error"
    ok, message = client.validate()
    assert not ok and "invalide" in message.lower()


# ===========================================================================
# Génération
# ===========================================================================

def test_appel_synchrone(client):
    from models.llm.base import Message
    result = client.chat([Message("user", "salut")], "gpt-4.1-mini")
    assert result.text == "Bonjour le monde."
    assert result.usage.prompt_tokens == 12
    assert result.usage.completion_tokens == 5
    assert result.elapsed >= 0


def test_streaming_assemble_les_fragments(client):
    from models.llm.base import Message
    chunks = []
    result = client.chat([Message("user", "salut")], "gpt-4.1-mini",
                         stream=True, on_chunk=chunks.append)
    assert result.text == "Bonjour le monde."
    # Le découpage réel doit remonter au fil de l'eau, pas d'un bloc.
    assert len(chunks) == 5
    assert "".join(chunks) == "Bonjour le monde."
    assert result.usage.completion_tokens == 3


def test_le_schema_json_est_transmis_en_mode_strict(client):
    from models.llm.base import Message
    schema = {"name": "resultat",
              "schema": {"type": "object", "properties": {}, "required": [],
                         "additionalProperties": False}}
    client.chat([Message("user", "x")], "gpt-4.1-mini", json_schema=schema)

    fmt = SCENARIO.last_payload["response_format"]
    assert fmt["type"] == "json_schema"
    assert fmt["json_schema"]["strict"] is True


def test_repli_json_object_si_le_schema_strict_est_indisponible(server):
    from models.llm.base import Message
    cfg = ProviderConfig(key="ollama", label="Ollama", base_url=server,
                         needs_key=False, supports_json_schema=False)
    OpenAICompatClient(cfg).chat([Message("user", "x")], "qwen",
                                 json_schema={"name": "x", "schema": {}})
    assert SCENARIO.last_payload["response_format"] == {"type": "json_object"}


def test_entetes_dauthentification(client):
    from models.llm.base import Message
    client.chat([Message("user", "x")], "gpt-4.1-mini")
    assert SCENARIO.last_headers["Authorization"] == "Bearer sk-test-1234567890"


def test_ollama_nenvoie_aucune_cle(server):
    from models.llm.base import Message
    cfg = ProviderConfig(key="ollama", label="Ollama", base_url=server,
                         needs_key=False)
    OpenAICompatClient(cfg).chat([Message("user", "x")], "qwen")
    assert "Authorization" not in SCENARIO.last_headers


# ===========================================================================
# Erreurs — chacune doit produire un message actionnable en français
# ===========================================================================

@pytest.mark.parametrize("mode, expected", [
    ("auth_error", AuthError),
    ("quota", QuotaError),
    ("not_found", ModelError),
    ("bad_request", ModelError),
])
def test_traduction_des_erreurs(client, mode, expected):
    from models.llm.base import Message
    SCENARIO.mode = mode
    with pytest.raises(expected) as exc:
        client.chat([Message("user", "x")], "gpt-4.1-mini")
    assert exc.value.user_message
    assert "HTTP" not in exc.value.user_message      # jamais de jargon brut


def test_erreur_serveur_est_reessayee_puis_abandonnee(client):
    from models.llm.base import Message
    SCENARIO.mode = "server_error"
    with pytest.raises(NetworkError):
        client.chat([Message("user", "x")], "gpt-4.1-mini")
    # 1 tentative + MAX_RETRIES nouvelles tentatives
    from models.llm.client import MAX_RETRIES
    assert SCENARIO.calls == MAX_RETRIES + 1


def test_limite_de_debit_est_reessayee_avec_succes(client):
    from models.llm.base import Message
    SCENARIO.rate_limit_before = 2          # deux 429 puis ça passe
    result = client.chat([Message("user", "x")], "gpt-4.1-mini")
    assert result.text == "Bonjour le monde."
    assert SCENARIO.calls == 3


def test_limite_de_debit_persistante_finit_par_lever(client):
    from models.llm.base import Message
    SCENARIO.rate_limit_before = 99
    with pytest.raises(RateLimitError):
        client.chat([Message("user", "x")], "gpt-4.1-mini")


def test_serveur_injoignable(server):
    from models.llm.base import Message
    cfg = ProviderConfig(key="openai", label="ChatGPT",
                         base_url="http://127.0.0.1:9/v1")
    with pytest.raises(NetworkError) as exc:
        OpenAICompatClient(cfg, "sk-x").chat([Message("user", "x")], "m")
    assert "internet" in exc.value.user_message.lower()


def test_ollama_arrete_donne_un_message_specifique():
    from models.llm.base import Message
    cfg = ProviderConfig(key="ollama", label="Ollama",
                         base_url="http://127.0.0.1:9/v1", needs_key=False)
    with pytest.raises(NetworkError) as exc:
        OpenAICompatClient(cfg).chat([Message("user", "x")], "qwen")
    assert "Ollama" in exc.value.user_message


# ===========================================================================
# Annulation — elle doit vraiment couper, pas seulement lever un drapeau
# ===========================================================================

def test_annulation_pendant_le_streaming(client):
    from models.llm.base import Message
    SCENARIO.stream_delay = 0.15
    cancel = CancelToken()
    received = []

    def on_chunk(piece):
        received.append(piece)
        if len(received) == 2:
            cancel.cancel()                 # ferme la connexion HTTP

    with pytest.raises(CancelledError):
        client.chat([Message("user", "x")], "gpt-4.1-mini",
                    stream=True, on_chunk=on_chunk, cancel=cancel)

    # La génération s'est bien arrêtée en cours de route.
    assert 2 <= len(received) < 5


def test_annulation_avant_le_depart(client):
    from models.llm.base import Message
    cancel = CancelToken()
    cancel.cancel()
    with pytest.raises(CancelledError):
        client.chat([Message("user", "x")], "gpt-4.1-mini", cancel=cancel)
    assert SCENARIO.calls == 0


def test_le_jeton_est_reutilisable_apres_reset(client):
    from models.llm.base import Message
    cancel = CancelToken()
    cancel.cancel()
    cancel.reset()
    result = client.chat([Message("user", "x")], "gpt-4.1-mini", cancel=cancel)
    assert result.text


# ===========================================================================
# Bout en bout : le flux réel jusqu'au JSON exploité par l'application
# ===========================================================================

def test_chaine_complete_streaming_puis_parsing(client):
    """Reproduit exactement ce que fait AIController en mode correction."""
    from models.llm.base import Message
    from models.llm.json_parse import extract_json

    SCENARIO.mode = "stream_json"
    result = client.chat([Message("system", "sys"), Message("user", "texte")],
                         "gpt-4.1-mini", stream=True)
    parsed = extract_json(result.text)
    assert parsed == {"result": "corrigé", "changes": []}


def test_le_manager_route_et_comptabilise(client, server, tmp_path, monkeypatch):
    """Le manager doit choisir le fournisseur, appeler, puis cumuler le coût."""
    from models.llm import credentials, manager as mgr_mod
    from models.llm.base import Message

    monkeypatch.setattr(credentials, "_KEYS_FILE", str(tmp_path / "creds.dat"))
    monkeypatch.setattr(mgr_mod, "_CONFIG_FILE", str(tmp_path / "llm.json"))
    monkeypatch.setattr(mgr_mod, "_MODELS_CACHE", str(tmp_path / "models.json"))
    monkeypatch.setitem(mgr_mod.PROVIDERS, "openai", client.cfg)

    manager = mgr_mod.LLMManager()
    manager.set_key("openai", "sk-test-1234567890")
    manager.active_provider = "openai"

    result = manager.complete([Message("user", "salut")], task="edit")
    assert result.text == "Bonjour le monde."
    assert manager.session_usage.total_tokens == 17
    assert manager.session_cost > 0
    assert "ChatGPT" in manager.status_label()
