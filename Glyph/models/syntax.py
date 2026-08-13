"""
models/syntax.py — Coloration syntaxique légère, sans dépendance externe.

Pourquoi pas Pygments ? Il pèse une dizaine de mégaoctets et importe des
centaines de modules ; embarqué dans l'exécutable, il annulerait une partie
du gain de démarrage obtenu par ailleurs. Glyph n'a besoin que d'une poignée
de langages, et un analyseur par expressions régulières les couvre en
quelques centaines de lignes.

Le module ne produit que des **segments** `(début, fin, type)`. C'est la vue
qui les traduit en couleurs, via la même couche de spans que la recherche et
le diff.

Ajouter un langage = ajouter une entrée dans `LANGUAGES`.
"""

import os
import re

# --- Types de jeton (indépendants du thème) --------------------------------
COMMENT = "comment"
STRING = "string"
NUMBER = "number"
KEYWORD = "keyword"
BUILTIN = "builtin"
NAME = "name"          # nom de fonction/classe défini
HEADING = "heading"
EMPHASIS = "emphasis"
LINK = "link"
PUNCT = "punct"
KEY = "key"            # clé d'objet JSON / YAML

#: Au-delà, on ne colore que le début du document. Un fichier de 500 000
#: caractères produirait des dizaines de milliers de spans, ce que le moteur
#: de rendu ne digère pas — mieux vaut dégrader que figer l'application.
MAX_HIGHLIGHT_CHARS = 120_000


class Language:
    """Un langage : un motif combiné et la correspondance groupe → type."""

    __slots__ = ("name", "pattern")

    def __init__(self, name: str, rules: list[tuple[str, str]], flags: int = 0):
        self.name = name
        # L'ordre des règles fait la priorité : commentaires et chaînes
        # d'abord, sinon un mot-clé à l'intérieur d'une chaîne serait coloré.
        #
        # Les drapeaux sont passés ici et non en `(?i)` au milieu du motif :
        # Python n'accepte les drapeaux globaux qu'en tête d'expression.
        self.pattern = re.compile(
            "|".join(f"(?P<{token}_{i}>{regex})"
                     for i, (token, regex) in enumerate(rules)),
            re.MULTILINE | flags,
        )

    def tokenize(self, text: str):
        """Produit des tuples (début, fin, type), sans chevauchement."""
        for match in self.pattern.finditer(text):
            group = match.lastgroup
            if group is None:
                continue
            token = group.rsplit("_", 1)[0]
            start, end = match.span()
            if end > start:
                yield start, end, token


# ---------------------------------------------------------------------------
# Python
# ---------------------------------------------------------------------------

_PY_KEYWORDS = (
    "False|None|True|and|as|assert|async|await|break|class|continue|def|del|"
    "elif|else|except|finally|for|from|global|if|import|in|is|lambda|nonlocal|"
    "not|or|pass|raise|return|try|while|with|yield|match|case|self|cls"
)
_PY_BUILTINS = (
    "abs|all|any|bool|bytes|callable|chr|dict|dir|enumerate|eval|filter|float|"
    "format|frozenset|getattr|hasattr|hash|id|input|int|isinstance|issubclass|"
    "iter|len|list|map|max|min|next|object|open|ord|print|range|repr|reversed|"
    "round|set|setattr|sorted|str|sum|super|tuple|type|vars|zip"
)

PYTHON = Language("python", [
    (COMMENT, r"#[^\n]*"),
    # Chaînes triples avant les simples, sinon """ serait vu comme "" + "
    (STRING, r'[rbfu]{0,2}"""(?:\\.|[^\\])*?"""'),
    (STRING, r"[rbfu]{0,2}'''(?:\\.|[^\\])*?'''"),
    (STRING, r'[rbfu]{0,2}"(?:\\.|[^"\\\n])*"'),
    (STRING, r"[rbfu]{0,2}'(?:\\.|[^'\\\n])*'"),
    (NAME, r"(?<=\bdef\s)\w+"),
    (NAME, r"(?<=\bclass\s)\w+"),
    (KEYWORD, r"@\w+(?:\.\w+)*"),                       # décorateur
    (KEYWORD, rf"\b(?:{_PY_KEYWORDS})\b"),
    (BUILTIN, rf"\b(?:{_PY_BUILTINS})\b"),
    (NUMBER, r"\b0[xXbBoO][0-9a-fA-F_]+\b"),
    (NUMBER, r"\b\d[\d_]*\.?[\d_]*(?:[eE][-+]?\d+)?\b"),
])

# ---------------------------------------------------------------------------
# JSON
# ---------------------------------------------------------------------------

JSON = Language("json", [
    # La clé se distingue par les deux-points qui la suivent.
    (KEY, r'"(?:\\.|[^"\\])*"(?=\s*:)'),
    (STRING, r'"(?:\\.|[^"\\])*"'),
    (KEYWORD, r"\b(?:true|false|null)\b"),
    (NUMBER, r"-?\b\d+(?:\.\d+)?(?:[eE][-+]?\d+)?\b"),
    (PUNCT, r"[{}\[\],:]"),
])

# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------

MARKDOWN = Language("markdown", [
    (STRING, r"^```[\s\S]*?^```", ),                    # bloc de code
    (STRING, r"`[^`\n]+`"),                             # code en ligne
    (HEADING, r"^#{1,6}[ \t][^\n]*"),
    (HEADING, r"^[^\n]+\n(?:={3,}|-{3,})$"),            # titre souligné
    (COMMENT, r"^>[ \t]?[^\n]*"),                       # citation
    (LINK, r"!?\[[^\]\n]*\]\([^)\n]*\)"),
    (LINK, r"<https?://[^>\s]+>"),
    (LINK, r"https?://[^\s)]+"),
    (EMPHASIS, r"\*\*\*[^\n*]+\*\*\*"),
    (EMPHASIS, r"\*\*[^\n*]+\*\*"),
    (EMPHASIS, r"__[^\n_]+__"),
    (EMPHASIS, r"\*[^\n*]+\*"),
    (EMPHASIS, r"~~[^\n~]+~~"),
    (KEYWORD, r"^[ \t]*(?:[-*+]|\d+\.)[ \t]"),          # puce de liste
    (PUNCT, r"^[ \t]*(?:---|\*\*\*|___)[ \t]*$"),       # règle horizontale
    (KEY, r"^\|[^\n]*\|$"),                             # ligne de tableau
])

# ---------------------------------------------------------------------------
# YAML / INI / TOML
# ---------------------------------------------------------------------------

CONFIG = Language("config", [
    (COMMENT, r"[#;][^\n]*"),
    (STRING, r'"(?:\\.|[^"\\\n])*"'),
    (STRING, r"'(?:\\.|[^'\\\n])*'"),
    (HEADING, r"^\[[^\]\n]*\]"),                        # section INI/TOML
    (KEY, r"^[ \t]*[-\w.\"']+(?=[ \t]*[:=])"),
    (KEYWORD, r"\b(?:true|false|null|yes|no|on|off|none)\b"),
    (NUMBER, r"\b-?\d+(?:\.\d+)?\b"),
    (PUNCT, r"^[ \t]*-[ \t]"),                          # élément de liste YAML
])

# ---------------------------------------------------------------------------
# Familles proches du C (js, ts, css, java, sql…)
# ---------------------------------------------------------------------------

_C_KEYWORDS = (
    "async|await|break|case|catch|class|const|continue|default|delete|do|else|"
    "export|extends|finally|for|from|function|if|import|in|instanceof|let|new|"
    "of|return|static|super|switch|this|throw|try|typeof|var|void|while|yield|"
    "true|false|null|undefined|interface|type|enum|public|private|protected"
)

CLIKE = Language("clike", [
    (COMMENT, r"//[^\n]*"),
    (COMMENT, r"/\*[\s\S]*?\*/"),
    (STRING, r'"(?:\\.|[^"\\\n])*"'),
    (STRING, r"'(?:\\.|[^'\\\n])*'"),
    (STRING, r"`(?:\\.|[^`\\])*`"),
    (NAME, r"(?<=\bfunction\s)\w+"),
    (NAME, r"(?<=\bclass\s)\w+"),
    (KEYWORD, rf"\b(?:{_C_KEYWORDS})\b"),
    (NUMBER, r"\b0[xX][0-9a-fA-F]+\b"),
    (NUMBER, r"\b\d+(?:\.\d+)?\b"),
])

# SQL est insensible à la casse : le drapeau s'applique à tout le langage.
SQL = Language("sql", [
    (COMMENT, r"--[^\n]*"),
    (COMMENT, r"/\*[\s\S]*?\*/"),
    (STRING, r"'(?:''|[^'])*'"),
    (KEYWORD, r"\b(?:select|from|where|insert|into|values|update|set|"
              r"delete|create|table|alter|drop|join|left|right|inner|outer|on|"
              r"group|by|order|having|limit|offset|as|and|or|not|null|is|in|"
              r"exists|distinct|union|all|case|when|then|else|end|with|index|"
              r"primary|key|foreign|references|default|constraint)\b"),
    (NUMBER, r"\b\d+(?:\.\d+)?\b"),
], flags=re.IGNORECASE)

# ---------------------------------------------------------------------------
# Association extension → langage
# ---------------------------------------------------------------------------

LANGUAGES: dict[str, Language] = {
    ".py": PYTHON, ".pyw": PYTHON,
    ".json": JSON,
    ".md": MARKDOWN, ".markdown": MARKDOWN, ".rst": MARKDOWN,
    ".yaml": CONFIG, ".yml": CONFIG, ".ini": CONFIG, ".cfg": CONFIG,
    ".conf": CONFIG, ".toml": CONFIG, ".env": CONFIG,
    ".js": CLIKE, ".ts": CLIKE, ".jsx": CLIKE, ".tsx": CLIKE,
    ".css": CLIKE, ".java": CLIKE, ".c": CLIKE, ".h": CLIKE,
    ".cpp": CLIKE, ".cs": CLIKE, ".go": CLIKE, ".rs": CLIKE,
    ".sql": SQL,
}

#: Libellé affiché dans la barre de statut.
LANGUAGE_LABELS = {
    "python": "Python", "json": "JSON", "markdown": "Markdown",
    "config": "Config", "clike": "Code", "sql": "SQL",
}


def detect_language(path: str | None, title: str = "") -> Language | None:
    """Devine le langage d'après l'extension du fichier."""
    name = path or title or ""
    if not name:
        return None
    ext = os.path.splitext(name)[1].lower()
    return LANGUAGES.get(ext)


def language_label(language: Language | None) -> str:
    if language is None:
        return "Texte"
    return LANGUAGE_LABELS.get(language.name, language.name.title())


def highlight(text: str, language: Language | None) -> list[tuple[int, int, str]]:
    """Segments colorés du texte. Liste vide si aucun langage ne s'applique.

    Les segments retournés ne se chevauchent jamais et sont triés : la vue
    peut les parcourir séquentiellement pour construire ses spans.
    """
    if not text or language is None:
        return []
    if len(text) > MAX_HIGHLIGHT_CHARS:
        text = text[:MAX_HIGHLIGHT_CHARS]

    segments: list[tuple[int, int, str]] = []
    last_end = 0
    for start, end, token in language.tokenize(text):
        # `finditer` ne renvoie jamais de chevauchement, mais une règle mal
        # écrite pourrait en produire : on s'en protège.
        if start < last_end:
            continue
        segments.append((start, end, token))
        last_end = end
    return segments
