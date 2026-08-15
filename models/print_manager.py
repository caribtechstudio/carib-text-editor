"""
models/print_manager.py — Impression via aperçu navigateur (HTML).

Génère un fichier HTML temporaire stylé et l'ouvre dans le navigateur
par défaut, dont le dialogue d'impression offre :
  - Aperçu avant impression
  - Export PDF (Microsoft Print to PDF)
  - Choix de l'imprimante
"""

import html
import os
import tempfile
import threading
import webbrowser

WIN32_PRINT = True  # toujours disponible (pas de dépendance externe)


def print_document(title: str, text: str, on_success=None, on_error=None) -> None:
    """Ouvre un aperçu d'impression dans le navigateur par défaut."""

    def _do_print():
        try:
            escaped_title = html.escape(title or "Document")
            escaped_text = html.escape(text or "")

            html_content = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<title>{escaped_title}</title>
<style>
  @media print {{
    @page {{
      margin: 2cm;
    }}
    body {{
      margin: 0;
    }}
    .no-print {{
      display: none !important;
    }}
  }}
  @media screen {{
    body {{
      max-width: 800px;
      margin: 40px auto;
      padding: 0 20px;
    }}
  }}
  body {{
    font-family: 'Segoe UI', 'Nunito', sans-serif;
    font-size: 12pt;
    line-height: 1.6;
    color: #1a1a1a;
    background: #fff;
  }}
  h1 {{
    font-size: 14pt;
    color: #333;
    border-bottom: 1px solid #ddd;
    padding-bottom: 8px;
    margin-bottom: 20px;
  }}
  pre {{
    white-space: pre-wrap;
    word-wrap: break-word;
    font-family: 'Segoe UI', 'Nunito', sans-serif;
    font-size: 12pt;
    line-height: 1.6;
    margin: 0;
  }}
  .no-print {{
    text-align: center;
    padding: 16px;
    margin-bottom: 24px;
    background: #f0f4ff;
    border-radius: 8px;
    color: #555;
    font-size: 10pt;
  }}
</style>
</head>
<body>
<div class="no-print">
  Utilisez <strong>Ctrl+P</strong> pour ouvrir le dialogue d'impression
  ou cliquez sur le bouton ci-dessous.<br><br>
  <button onclick="window.print()"
    style="padding:8px 24px;font-size:11pt;border:1px solid #ccc;
           border-radius:6px;background:#fff;cursor:pointer;">
    Imprimer / Enregistrer en PDF
  </button>
</div>
<h1>{escaped_title}</h1>
<pre>{escaped_text}</pre>
<script>
  // Ouvrir le dialogue d'impression automatiquement
  window.onload = function() {{
    setTimeout(function() {{ window.print(); }}, 400);
  }};
</script>
</body>
</html>"""

            # Écrire dans un fichier temporaire qui persiste
            fd, path = tempfile.mkstemp(suffix=".html", prefix="carib_print_")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(html_content)

            webbrowser.open(f"file:///{path.replace(os.sep, '/')}")

            if on_success:
                on_success()

        except Exception as exc:
            if on_error:
                on_error(str(exc))

    threading.Thread(target=_do_print, daemon=True).start()
