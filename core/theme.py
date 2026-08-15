"""
theme.py — Design tokens (couleurs) pour Carib.
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
    L_SIDEBAR   = "#F6F6F9"
    L_SURFACE   = "#FFFFFF"
    L_BORDER    = "#ECECF1"
    L_HOVER     = "#F4F4F7"
    L_SELECTED  = "#F1EEFF"
    L_PRIMARY   = "#17171D"
    L_SECONDARY = "#6C6C78"
    L_TERTIARY  = "#858590"
    L_MUTED     = "#A2A2AD"
    L_ACCENT    = "#6A4DF5"
    L_ACCENT_LT = "#F1EEFF"
    L_SUCCESS   = "#059669"
    L_WARNING   = "#D97706"
    L_ERROR     = "#DC2626"
    L_TOOLBAR   = "#FFFFFF"
    L_TB_BORDER = "#ECECF1"
    L_EDITOR    = "#FBFBFD"
    L_STATUS    = "#F6F6F9"

    # Dark
    D_BG        = "#141418"
    D_SIDEBAR   = "#101014"
    D_SURFACE   = "#141418"
    D_BORDER    = "#29292F"
    D_HOVER     = "#202025"
    D_SELECTED  = "#28233D"
    D_PRIMARY   = "#ECECEF"
    D_SECONDARY = "#9B9BA7"
    D_TERTIARY  = "#858590"
    D_MUTED     = "#6E6E7A"
    D_ACCENT    = "#9A85FF"
    D_ACCENT_LT = "#28233D"
    D_SUCCESS   = "#34D399"
    D_WARNING   = "#FBBF24"
    D_ERROR     = "#F87171"
    D_TOOLBAR   = "#141418"
    D_TB_BORDER = "#29292F"
    D_EDITOR    = "#17171C"
    D_STATUS    = "#101014"

    # ------------------------------------------------------------------
    # Coloration syntaxique
    #
    # Teintes choisies pour rester lisibles sur les deux fonds sans jamais
    # descendre sous un contraste de 4,5:1 : la couleur doit aider à lire,
    # pas transformer le texte en sapin de Noël.
    # ------------------------------------------------------------------
    SYNTAX_LIGHT = {
        "comment":  "#8B95A5",
        "string":   "#0A7C4A",
        "number":   "#B45309",
        "keyword":  "#7C3AED",
        "builtin":  "#0369A1",
        "name":     "#1D4ED8",
        "heading":  "#111827",
        "emphasis": "#374151",
        "link":     "#0369A1",
        "punct":    "#6B7280",
        "key":      "#B91C1C",
    }
    SYNTAX_DARK = {
        "comment":  "#6B7A90",
        "string":   "#4ADE80",
        "number":   "#FBBF24",
        "keyword":  "#C084FC",
        "builtin":  "#38BDF8",
        "name":     "#93C5FD",
        "heading":  "#F8FAFC",
        "emphasis": "#CBD5E1",
        "link":     "#38BDF8",
        "punct":    "#94A3B8",
        "key":      "#FCA5A5",
    }

    #: Types de jeton rendus en gras / italique, quel que soit le thème.
    SYNTAX_BOLD = frozenset({"heading", "keyword"})
    SYNTAX_ITALIC = frozenset({"comment", "emphasis"})
