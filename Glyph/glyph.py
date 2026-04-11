"""
Glyph v0.10.1 — Flet Edition
=====================================
Editeur de texte moderne avec interface Clean SaaS inspiree Notion / Untitled UI.

Fonctionnalites :
  - Onglets multiples avec gestion individuelle des fichiers
  - Calculatrice integree (parser AST securise)
  - Text-to-Speech et Speech-to-Text (non-bloquant via threading)
  - Correcteur IA local : ministral-3:3b via Ollama
  - Correcteur orthographique de base (pyspellchecker) en fallback
  - Remplacement automatique d'emojis (400+ codes)
  - Barre d'outils de formatage flottante
  - Themes sombre / clair avec design epure
  - Mode Texte / Mode Calcul / Mode Lecture
  - Selecteur visuel d'emojis avec recherche
  - Panneau lateral de corrections IA

Auteur  : Arnaud
Licence : CC BY-NC-ND 4.0
Version : 0.10.1
"""

import flet as ft

from controllers.app_controller import AppController


async def main(page: ft.Page):
    AppController(page)


if __name__ == "__main__":
    ft.run(main, assets_dir="ressource")
