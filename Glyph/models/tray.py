"""
models/tray.py — Icône de zone de notification, en Win32 pur.

Pourquoi pas `pystray` ? Il dépend de Pillow, soit une quinzaine de
mégaoctets que l'on vient précisément de retirer de l'exécutable. Pour une
icône et deux entrées de menu, l'appel direct à `Shell_NotifyIcon` via
`ctypes` est plus léger et n'ajoute aucune dépendance.

Ce module rend possible l'**instance résidente** : à la fermeture de la
fenêtre, Glyph se cache au lieu de quitter. Le double-clic suivant sur un
fichier passe par l'IPC déjà en place et la fenêtre réapparaît en quelques
dizaines de millisecondes, au lieu des sept à dix secondes d'un démarrage
complet.

L'icône tourne dans son **propre thread**, avec sa propre boucle de
messages : Win32 exige que les messages d'une fenêtre soient traités par le
thread qui l'a créée. Les rappels sont donc invoqués depuis ce thread ;
l'appelant doit les reporter sur le thread d'interface.

En cas d'échec (autre système, API indisponible), `start()` renvoie False et
l'application doit se rabattre sur une fermeture normale.
"""

import ctypes
import itertools
import os
import sys
import threading
from ctypes import wintypes

_IS_WINDOWS = sys.platform == "win32"

#: Chaque instance enregistre sa propre classe de fenêtre : `RegisterClassExW`
#: échoue si le nom existe déjà, et une classe survit à la destruction de sa
#: fenêtre. Sans compteur, une seconde icône dans le même processus échouait.
_class_counter = itertools.count()

# --- Constantes Win32 -------------------------------------------------------
WM_DESTROY = 0x0002
WM_COMMAND = 0x0111
WM_USER = 0x0400
WM_TRAYICON = WM_USER + 20
WM_LBUTTONUP = 0x0202
WM_RBUTTONUP = 0x0205
WM_LBUTTONDBLCLK = 0x0203

NIM_ADD = 0x0000
NIM_DELETE = 0x0002
NIF_MESSAGE = 0x0001
NIF_ICON = 0x0002
NIF_TIP = 0x0004

IMAGE_ICON = 1
LR_LOADFROMFILE = 0x0010
LR_DEFAULTSIZE = 0x0040
IDI_APPLICATION = 32512

MF_STRING = 0x0000
MF_SEPARATOR = 0x0800
TPM_RIGHTBUTTON = 0x0002

CMD_SHOW = 1001
CMD_QUIT = 1002

WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_longlong, wintypes.HWND, wintypes.UINT,
                             wintypes.WPARAM, wintypes.LPARAM) if _IS_WINDOWS else None


class _WNDCLASSEX(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT), ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC if _IS_WINDOWS else ctypes.c_void_p),
        ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE), ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR),
        ("hIconSm", wintypes.HICON),
    ]


class _GUID(ctypes.Structure):
    _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD), ("Data4", ctypes.c_byte * 8)]


class _NOTIFYICONDATA(ctypes.Structure):
    """Doit reproduire NOTIFYICONDATAW **exactement**.

    Une structure tronquée ou mal ordonnée fait lire Windows au-delà de la
    mémoire allouée : violation d'accès, et arrêt brutal du processus.
    """

    _fields_ = [
        ("cbSize", wintypes.DWORD), ("hWnd", wintypes.HWND),
        ("uID", wintypes.UINT), ("uFlags", wintypes.UINT),
        ("uCallbackMessage", wintypes.UINT), ("hIcon", wintypes.HICON),
        ("szTip", wintypes.WCHAR * 128),
        ("dwState", wintypes.DWORD), ("dwStateMask", wintypes.DWORD),
        ("szInfo", wintypes.WCHAR * 256), ("uVersion", wintypes.UINT),
        ("szInfoTitle", wintypes.WCHAR * 64), ("dwInfoFlags", wintypes.DWORD),
        ("guidItem", _GUID), ("hBalloonIcon", wintypes.HICON),
    ]


class TrayIcon:
    """Icône de notification avec un menu « Ouvrir » / « Quitter »."""

    def __init__(self, title: str, icon_path: str | None,
                 on_show=None, on_quit=None):
        self._title = title[:127]
        self._icon_path = icon_path
        self._on_show = on_show or (lambda: None)
        self._on_quit = on_quit or (lambda: None)

        self._hwnd = None
        self._hicon = None
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._ok = False
        # La référence doit survivre : Windows appelle ce pointeur bien après
        # la sortie de `start()`. Sans elle, le ramasse-miettes la libère et
        # le processus tombe au premier clic.
        self._wndproc = None

    # ------------------------------------------------------------------
    @property
    def active(self) -> bool:
        return self._ok

    def start(self) -> bool:
        """Crée l'icône. Retourne False si l'environnement ne le permet pas."""
        if not _IS_WINDOWS:
            return False
        if self._thread is not None:
            return self._ok

        self._thread = threading.Thread(target=self._run, name="glyph-tray",
                                        daemon=True)
        self._thread.start()
        self._ready.wait(3.0)
        return self._ok

    def stop(self):
        """Retire l'icône et arrête la boucle de messages."""
        if not self._hwnd:
            return
        try:
            ctypes.windll.user32.PostMessageW(self._hwnd, WM_DESTROY, 0, 0)
        except Exception:
            pass

    # ------------------------------------------------------------------
    def _run(self):
        try:
            self._create()
            self._ok = True
        except Exception:
            self._ok = False
        finally:
            self._ready.set()

        if not self._ok:
            return

        # Boucle de messages : obligatoire, et propre à ce thread.
        msg = wintypes.MSG()
        user32 = ctypes.windll.user32
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    def _create(self):
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        self._wndproc = WNDPROC(self._on_message)
        # Sans `restype` explicite, ctypes suppose un `int` 32 bits : tout
        # handle 64 bits revient tronqué, et Windows le déréférence ensuite —
        # violation d'accès immédiate. Idem pour `lParam` en entrée.
        self._declare_signatures(user32, kernel32)

        hinstance = kernel32.GetModuleHandleW(None)
        class_name = f"GlyphTray{os.getpid()}_{next(_class_counter)}"
        self._class_name = class_name
        self._hinstance = hinstance

        wc = _WNDCLASSEX()
        wc.cbSize = ctypes.sizeof(_WNDCLASSEX)
        wc.lpfnWndProc = self._wndproc
        wc.hInstance = hinstance
        wc.lpszClassName = class_name
        if not user32.RegisterClassExW(ctypes.byref(wc)):
            raise OSError("RegisterClassExW a échoué")

        # Fenêtre invisible : elle n'existe que pour recevoir les messages.
        self._hwnd = user32.CreateWindowExW(
            0, class_name, class_name, 0, 0, 0, 0, 0, None, None, hinstance, None)
        if not self._hwnd:
            raise OSError("CreateWindowExW a échoué")

        self._hicon = self._load_icon()

        nid = _NOTIFYICONDATA()
        nid.cbSize = ctypes.sizeof(_NOTIFYICONDATA)
        nid.hWnd = self._hwnd
        nid.uID = 1
        nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        nid.uCallbackMessage = WM_TRAYICON
        nid.hIcon = self._hicon
        nid.szTip = self._title
        if not ctypes.windll.shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid)):
            raise OSError("Shell_NotifyIconW a échoué")
        self._nid = nid

    @staticmethod
    def _declare_signatures(user32, kernel32):
        """Déclare les types de chaque appel Win32 utilisé ici."""
        kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
        kernel32.GetModuleHandleW.restype = wintypes.HMODULE

        user32.RegisterClassExW.argtypes = [ctypes.c_void_p]
        user32.RegisterClassExW.restype = wintypes.ATOM

        user32.CreateWindowExW.argtypes = [
            wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
            ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
            wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, ctypes.c_void_p]
        user32.CreateWindowExW.restype = wintypes.HWND

        user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT,
                                          wintypes.WPARAM, wintypes.LPARAM]
        user32.DefWindowProcW.restype = ctypes.c_longlong

        user32.CreatePopupMenu.restype = wintypes.HMENU
        user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT,
                                        wintypes.WPARAM, wintypes.LPARAM]

        ctypes.windll.shell32.Shell_NotifyIconW.argtypes = [wintypes.DWORD,
                                                            ctypes.c_void_p]
        ctypes.windll.shell32.Shell_NotifyIconW.restype = wintypes.BOOL

    def _load_icon(self):
        user32 = ctypes.windll.user32
        user32.LoadImageW.restype = wintypes.HANDLE
        user32.LoadIconW.restype = wintypes.HICON

        if self._icon_path and os.path.isfile(self._icon_path):
            handle = user32.LoadImageW(None, self._icon_path, IMAGE_ICON, 0, 0,
                                       LR_LOADFROMFILE | LR_DEFAULTSIZE)
            if handle:
                return handle

        # Icône générique plutôt qu'aucune icône : une entrée invisible dans
        # la zone de notification serait pire que pas d'entrée du tout.
        #
        # IDI_APPLICATION est un identifiant **numérique**, pas une chaîne :
        # il se transmet comme une valeur de pointeur (macro MAKEINTRESOURCE).
        # Le passer en `c_wchar_p` faisait déréférencer l'adresse 32512 à
        # Windows — violation d'accès immédiate.
        return user32.LoadIconW(None, ctypes.c_void_p(IDI_APPLICATION))

    # ------------------------------------------------------------------
    def _on_message(self, hwnd, msg, wparam, lparam):
        user32 = ctypes.windll.user32

        if msg == WM_TRAYICON:
            event = lparam & 0xFFFF
            if event in (WM_LBUTTONUP, WM_LBUTTONDBLCLK):
                self._safe(self._on_show)
            elif event == WM_RBUTTONUP:
                self._show_menu(hwnd)
            return 0

        if msg == WM_COMMAND:
            command = wparam & 0xFFFF
            if command == CMD_SHOW:
                self._safe(self._on_show)
            elif command == CMD_QUIT:
                self._safe(self._on_quit)
            return 0

        if msg == WM_DESTROY:
            self._remove_icon()
            self._unregister_class()
            user32.PostQuitMessage(0)
            return 0

        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _unregister_class(self):
        """Libère la classe de fenêtre pour que le nom soit réutilisable."""
        name = getattr(self, "_class_name", None)
        if not name:
            return
        try:
            ctypes.windll.user32.UnregisterClassW(name,
                                                  getattr(self, "_hinstance", None))
        except Exception:
            pass
        self._class_name = None

    def _show_menu(self, hwnd):
        user32 = ctypes.windll.user32
        menu = user32.CreatePopupMenu()
        user32.AppendMenuW(menu, MF_STRING, CMD_SHOW, "Ouvrir Glyph")
        user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
        user32.AppendMenuW(menu, MF_STRING, CMD_QUIT, "Quitter Glyph")

        point = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(point))
        # Sans SetForegroundWindow, le menu reste affiché après le clic.
        user32.SetForegroundWindow(hwnd)
        user32.TrackPopupMenu(menu, TPM_RIGHTBUTTON, point.x, point.y,
                              0, hwnd, None)
        user32.PostMessageW(hwnd, 0, 0, 0)
        user32.DestroyMenu(menu)

    def _remove_icon(self):
        nid = getattr(self, "_nid", None)
        if nid is None:
            return
        try:
            ctypes.windll.shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(nid))
        except Exception:
            pass
        self._nid = None

    @staticmethod
    def _safe(callback):
        # Une exception qui remonterait dans la WndProc corromprait la boucle
        # de messages de Windows.
        try:
            callback()
        except Exception:
            pass
