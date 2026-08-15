"""
models/ipc_server.py — Instance unique : ouvre les fichiers dans la fenêtre existante.

Sécurité
--------
La version précédente écoutait sur 127.0.0.1:47823 et ouvrait **n'importe
quel chemin** envoyé par **n'importe quel processus local**, sans
authentification. Un programme sans privilège particulier pouvait donc faire
ouvrir des fichiers arbitraires dans Carib — y compris des chemins UNC
(`\\\\serveur\\partage\\...`) dont la simple lecture déclenche une
authentification SMB sortante.

Trois protections sont désormais en place :

  1. **Jeton partagé** — un secret aléatoire est écrit dans `~/.carib/ipc.token`
     à la première exécution. Seuls les processus capables de lire ce fichier
     (donc s'exécutant sous le même compte) peuvent parler au serveur.
  2. **Validation des chemins** — le message doit désigner un fichier régulier
     existant ; les chemins UNC sont refusés.
  3. **Message borné** — la lecture est plafonnée, avec un délai maximal.
"""

import os
import secrets
import socket
import threading

_IPC_HOST = "127.0.0.1"
_IPC_PORT = 47823
_DATA_DIR = os.path.join(os.path.expanduser("~"), ".carib")
_TOKEN_FILE = os.path.join(_DATA_DIR, "ipc.token")

_MAX_MESSAGE = 4096
_SOCKET_TIMEOUT = 2.0

#: Socket d'écoute de cette instance, pour pouvoir la fermer à l'arrêt.
_server_socket: socket.socket | None = None
_stopping = threading.Event()


def _load_or_create_token() -> str:
    """Lit le jeton local, en créant un nouveau si nécessaire."""
    try:
        os.makedirs(_DATA_DIR, exist_ok=True)
        if os.path.isfile(_TOKEN_FILE):
            with open(_TOKEN_FILE, "r", encoding="utf-8") as fh:
                token = fh.read().strip()
            if len(token) >= 32:
                return token

        token = secrets.token_hex(24)
        tmp = _TOKEN_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(token)
        if os.name != "nt":
            os.chmod(tmp, 0o600)
        os.replace(tmp, _TOKEN_FILE)
        return token
    except OSError:
        # Sans jeton persistant, on en génère un éphémère : l'instance unique
        # ne fonctionnera pas, mais l'application démarre quand même.
        return secrets.token_hex(24)


def _is_acceptable_path(path: str) -> bool:
    """Refuse tout ce qui n'est ni un fichier ni un dossier local ordinaire."""
    if not path or len(path) > 4096:
        return False
    # Chemins UNC : leur seule ouverture peut provoquer une authentification
    # réseau sortante vers un serveur choisi par l'appelant.
    if path.startswith("\\\\") or path.startswith("//"):
        return False
    try:
        return os.path.isfile(path) or os.path.isdir(path)
    except OSError:
        return False


def send_to_existing_instance(paths) -> bool:
    """Transmet un ou plusieurs chemins à une instance déjà ouverte.

    Le multi-chemins compte : Windows passe toute une sélection en argv
    quand on l'ouvre avec Carib ou qu'on la dépose sur son icône.

    Retourne True si une instance a bien reçu le message.
    """
    if isinstance(paths, str):
        paths = [paths]
    paths = [p for p in paths if p]
    if not paths:
        return False

    token = _load_or_create_token()
    payload = ("\n".join([token, *paths])).encode("utf-8")
    if len(payload) > _MAX_MESSAGE:
        return False
    try:
        with socket.create_connection((_IPC_HOST, _IPC_PORT), timeout=0.5) as sock:
            sock.sendall(payload)
        return True
    except OSError:
        return False


def start_ipc_server(on_paths_received):
    """Démarre le serveur dans un thread daemon.

    `on_paths_received(liste_de_chemins)` n'est appelé que pour un message
    authentifié dont les chemins existent réellement.
    """
    token = _load_or_create_token()

    def _handle(conn):
        with conn:
            conn.settimeout(_SOCKET_TIMEOUT)
            try:
                data = conn.recv(_MAX_MESSAGE)
            except OSError:
                return
            if not data:
                return

            try:
                message = data.decode("utf-8")
            except UnicodeDecodeError:
                return

            received_token, _, rest = message.partition("\n")
            # Comparaison à temps constant : le jeton est un secret.
            if not secrets.compare_digest(received_token.strip(), token):
                return

            paths = [p.strip() for p in rest.split("\n") if p.strip()]
            accepted = [p for p in paths if _is_acceptable_path(p)]
            if accepted:
                on_paths_received(accepted)

    def _serve():
        global _server_socket
        try:
            srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # Pas de SO_REUSEADDR : sous Windows il permettrait à un second
            # processus de détourner le port d'une instance déjà en écoute.
            srv.bind((_IPC_HOST, _IPC_PORT))
            srv.listen(5)
            srv.settimeout(1.0)
        except OSError:
            return          # port occupé : cette instance est secondaire

        _server_socket = srv
        try:
            while not _stopping.is_set():
                try:
                    conn, _ = srv.accept()
                except socket.timeout:
                    continue
                except OSError:
                    break
                if _stopping.is_set():
                    conn.close()
                    break
                _handle(conn)
        finally:
            try:
                srv.close()
            except OSError:
                pass
            _server_socket = None

    _stopping.clear()
    threading.Thread(target=_serve, daemon=True).start()


def stop_ipc_server():
    """Ferme l'écoute — à appeler à la fermeture de l'application.

    Le thread est déjà `daemon`, mais laisser le port ouvert pendant l'arrêt
    fait qu'un lancement immédiat de Carib croit parler à l'instance
    précédente : il lui envoie ses chemins, et disparaît sans rien ouvrir.
    """
    _stopping.set()
    srv = _server_socket
    if srv is not None:
        try:
            srv.close()          # débloque l'`accept()` en attente
        except OSError:
            pass
