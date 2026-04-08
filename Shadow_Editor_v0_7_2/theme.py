"""
theme.py — Design tokens (couleurs) pour Shadow Editor.
"""


class T:
    """Palette de couleurs Light / Dark."""

    # Highlight (recherche)
    L_HL_CURRENT = "#FBBF24"   # ambre — match courant (selection_color)
    L_HL_OTHER   = "#FEF3C7"   # jaune pâle — autres matches
    D_HL_CURRENT = "#F59E0B"   # ambre chaud
    D_HL_OTHER   = "#78350F"   # brun doré subtil

    # Light
    L_BG        = "#FFFFFF"
    L_SIDEBAR   = "#F9FAFB"
    L_SURFACE   = "#FFFFFF"
    L_BORDER    = "#EAECF0"
    L_HOVER     = "#F3F4F6"
    L_SELECTED  = "#EEF2FF"
    L_PRIMARY   = "#101828"
    L_SECONDARY = "#344054"
    L_TERTIARY  = "#667085"
    L_MUTED     = "#98A2B3"
    L_ACCENT    = "#6366F1"
    L_ACCENT_LT = "#EEF2FF"
    L_SUCCESS   = "#059669"
    L_WARNING   = "#D97706"
    L_ERROR     = "#DC2626"
    L_TOOLBAR   = "#FFFFFF"
    L_TB_BORDER = "#E5E7EB"
    L_EDITOR    = "#FFFFFF"
    L_STATUS    = "#F9FAFB"

    # Dark
    D_BG        = "#0F172A"
    D_SIDEBAR   = "#0F172A"
    D_SURFACE   = "#1E293B"
    D_BORDER    = "#334155"
    D_HOVER     = "#1E293B"
    D_SELECTED  = "#312E81"
    D_PRIMARY   = "#F8FAFC"
    D_SECONDARY = "#CBD5E1"
    D_TERTIARY  = "#94A3B8"
    D_MUTED     = "#64748B"
    D_ACCENT    = "#818CF8"
    D_ACCENT_LT = "#1E1B4B"
    D_SUCCESS   = "#34D399"
    D_WARNING   = "#FBBF24"
    D_ERROR     = "#F87171"
    D_TOOLBAR   = "#1E293B"
    D_TB_BORDER = "#334155"
    D_EDITOR    = "#0F172A"
    D_STATUS    = "#0F172A"
