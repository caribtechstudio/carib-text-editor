"""
models/print_manager.py — Impression via Win32 GDI.
"""

import ctypes
import ctypes.wintypes as wt
import threading

try:
    import win32con
    WIN32_PRINT = True
except ImportError:
    WIN32_PRINT = False


def print_document(title: str, text: str, on_success=None, on_error=None) -> None:
    """Imprime un document via la boîte d'impression Windows (dans un thread)."""
    if not WIN32_PRINT:
        if on_error:
            on_error("pywin32 non installé.")
        return

    def _do_print():
        class PRINTDLGW(ctypes.Structure):
            _fields_ = [
                ("lStructSize",         wt.DWORD),
                ("hwndOwner",           wt.HWND),
                ("hDevMode",            wt.HANDLE),
                ("hDevNames",           wt.HANDLE),
                ("hDC",                 wt.HDC),
                ("Flags",               wt.DWORD),
                ("nFromPage",           wt.WORD),
                ("nToPage",             wt.WORD),
                ("nMinPage",            wt.WORD),
                ("nMaxPage",            wt.WORD),
                ("nCopies",             wt.WORD),
                ("hInstance",           wt.HINSTANCE),
                ("lCustData",           ctypes.POINTER(ctypes.c_long)),
                ("lpfnPrintHook",       ctypes.c_void_p),
                ("lpfnSetupHook",       ctypes.c_void_p),
                ("lpPrintTemplateName", wt.LPCWSTR),
                ("lpSetupTemplateName", wt.LPCWSTR),
                ("hPrintTemplate",      wt.HANDLE),
                ("hSetupTemplate",      wt.HANDLE),
            ]

        PD_RETURNDC    = 0x00000100
        PD_NOPAGENUMS  = 0x00000008
        PD_NOSELECTION = 0x00000004

        try:
            pd = PRINTDLGW()
            pd.lStructSize = ctypes.sizeof(PRINTDLGW)
            pd.Flags = PD_RETURNDC | PD_NOPAGENUMS | PD_NOSELECTION

            if not ctypes.windll.comdlg32.PrintDlgW(ctypes.byref(pd)):
                return  # Annulé

            hdc = pd.hDC
            gdi = ctypes.windll.gdi32

            dpi_y = gdi.GetDeviceCaps(hdc, win32con.LOGPIXELSY)
            font_h = -int(11 * dpi_y / 72)
            hfont = gdi.CreateFontW(
                font_h, 0, 0, 0, 400, 0, 0, 0, 1, 0, 0, 0, 0,
                "Courier New"
            )
            gdi.SelectObject(hdc, hfont)

            page_w = gdi.GetDeviceCaps(hdc, win32con.HORZRES)
            page_h = gdi.GetDeviceCaps(hdc, win32con.VERTRES)
            margin_x = int(page_w * 0.05)
            margin_y = int(page_h * 0.05)
            max_y = page_h - margin_y

            class TEXTMETRICW(ctypes.Structure):
                _fields_ = [
                    ("tmHeight", ctypes.c_long),
                    ("tmAscent", ctypes.c_long),
                    ("tmDescent", ctypes.c_long),
                    ("tmInternalLeading", ctypes.c_long),
                    ("tmExternalLeading", ctypes.c_long),
                ] + [(f"_pad{i}", ctypes.c_long) for i in range(15)]

            tm = TEXTMETRICW()
            gdi.GetTextMetricsW(hdc, ctypes.byref(tm))
            line_h = int((tm.tmHeight + tm.tmExternalLeading) * 1.2)

            class DOCINFOW(ctypes.Structure):
                _fields_ = [
                    ("cbSize",       ctypes.c_int),
                    ("lpszDocName",  wt.LPCWSTR),
                    ("lpszOutput",   wt.LPCWSTR),
                    ("lpszDatatype", wt.LPCWSTR),
                    ("fwType",       wt.DWORD),
                ]

            di = DOCINFOW()
            di.cbSize = ctypes.sizeof(DOCINFOW)
            di.lpszDocName = title

            gdi.StartDocW(hdc, ctypes.byref(di))
            gdi.StartPage(hdc)
            y = margin_y

            for line in text.split("\n"):
                if y + line_h > max_y:
                    gdi.EndPage(hdc)
                    gdi.StartPage(hdc)
                    y = margin_y
                out = line if line else " "
                gdi.TextOutW(hdc, margin_x, y, out, len(out))
                y += line_h

            gdi.EndPage(hdc)
            gdi.EndDoc(hdc)
            gdi.DeleteObject(hfont)
            ctypes.windll.user32.ReleaseDC(None, hdc)

            if on_success:
                on_success()

        except Exception as exc:
            if on_error:
                on_error(str(exc))

    threading.Thread(target=_do_print, daemon=True).start()
