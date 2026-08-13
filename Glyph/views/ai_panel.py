"""
views/ai_panel.py -- Panneau lateral IA multi-mode.

Affiche les resultats adaptes au mode actif :
  - Correction : score + liste de corrections/suggestions
  - Traduction : texte traduit + notes
  - Reformulation : texte reformule + changements
  - Resume : texte resume + points cles
  - Mots-cles : theme + mots-cles classes
"""

import flet as ft

from constants import (ICON_XS, ICON_SM, ICON_MD, svg_icon, svg_icon_btn, UI_FONT_STRONG)
from theme import T
from ai_prompts import MODE_LABELS


def build_ai_panel(state, c, callbacks):
    """
    Construit le panneau de resultats IA.

    callbacks attendus :
        close_ai(), apply_correction(original, replacement),
        dismiss_correction(item, kind),
        replace_with_result(text), copy_result(text)
    """
    if not state.show_ai:
        return ft.Container(visible=False)

    items = []

    # Header avec titre dynamique
    if state.ai_mode == "free":
        mode_label = state.ai_instruction[:48] or "Demande libre"
    else:
        mode_label = MODE_LABELS.get(state.ai_mode, "IA")
    model_name = state.ai_model_used or "—"

    items.append(ft.Container(
        padding=ft.Padding(16, 14, 16, 14),
        border=ft.Border.only(bottom=ft.BorderSide(1, c(T.L_BORDER, T.D_BORDER))),
        content=ft.Column(spacing=4, controls=[
            ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Text(mode_label, size=14, weight=ft.FontWeight.W_700,
                            font_family=UI_FONT_STRONG,
                            color=c(T.L_PRIMARY, T.D_PRIMARY)),
                    ft.IconButton(icon=ft.Icons.CLOSE, icon_size=18,
                                  icon_color=c(T.L_MUTED, T.D_MUTED),
                                  on_click=lambda e: callbacks["close_ai"]()),
                ],
            ),
            ft.Row(spacing=8, controls=[
                ft.Text(model_name, size=11,
                        color=c(T.L_MUTED, T.D_MUTED)),
            ] + ([ft.Text(f"{state.ai_elapsed} s", size=11,
                          color=c(T.L_ACCENT, T.D_ACCENT))]
                 if state.ai_elapsed > 0 and not state.ai_loading else [])),
        ]),
    ))

    # Contenu selon l'etat
    if state.ai_loading:
        items.append(_build_loading(state, c, callbacks))
    elif state.ai_error:
        items.append(_build_error(state, c))
    elif state.ai_mode == "correction":
        _build_correction_results(items, state, c, callbacks)
    elif state.ai_mode in ("translate_fr_en", "translate_en_fr"):
        _build_translation_results(items, state, c, callbacks)
    elif state.ai_mode in ("reformulate", "natural", "professional", "free"):
        _build_reformulation_results(items, state, c, callbacks)
    elif state.ai_mode == "summarize":
        _build_summary_results(items, state, c, callbacks)
    elif state.ai_mode == "keywords":
        _build_keywords_results(items, state, c, callbacks)
    else:
        items.append(_build_empty(c))

    return ft.Container(
        width=380, bgcolor=c(T.L_SURFACE, T.D_SURFACE),
        border=ft.Border.only(left=ft.BorderSide(1, c(T.L_BORDER, T.D_BORDER))),
        shadow=ft.BoxShadow(spread_radius=0, blur_radius=12,
                            color=ft.Colors.with_opacity(0.04, ft.Colors.BLACK),
                            offset=ft.Offset(-2, 0)),
        content=ft.Column(spacing=0, expand=True, scroll=ft.ScrollMode.AUTO, controls=items),
    )


# ===========================================================================
# Etats communs : loading, error, empty
# ===========================================================================

def _build_loading(state, c, callbacks=None):
    mode_label = MODE_LABELS.get(state.ai_mode, "Traitement")
    controls = [
        ft.ProgressRing(width=32, height=32, color=c(T.L_ACCENT, T.D_ACCENT)),
        ft.Text(f"{mode_label} en cours...", size=13,
                color=c(T.L_TERTIARY, T.D_TERTIARY)),
    ]
    # Le streaming permet d'afficher la progression reelle plutot qu'un
    # simple sablier : l'attente devient lisible.
    streamed = len(getattr(state, "ai_stream", "") or "")
    if streamed:
        controls.append(ft.Text(f"{streamed} caracteres recus", size=11,
                                color=c(T.L_MUTED, T.D_MUTED)))
    if callbacks and "close_ai" in callbacks:
        controls.append(ft.TextButton(
            "Annuler", height=28,
            style=ft.ButtonStyle(
                color=c(T.L_MUTED, T.D_MUTED),
                shape=ft.RoundedRectangleBorder(radius=6),
                text_style=ft.TextStyle(size=11)),
            on_click=lambda e: callbacks["close_ai"](),
        ))
    return ft.Container(
        padding=40, alignment=ft.Alignment(0, 0),
        content=ft.Column(horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=16,
                          controls=controls),
    )


def _build_error(state, c):
    return ft.Container(
        padding=24,
        content=ft.Row(spacing=10, controls=[
            svg_icon("document-circle-wrong", size=ICON_MD, color=c(T.L_ERROR, T.D_ERROR)),
            ft.Text(state.ai_error, size=13, color=c(T.L_ERROR, T.D_ERROR), expand=True),
        ]),
    )


def _build_empty(c):
    return ft.Container(
        padding=40, alignment=ft.Alignment(0, 0),
        content=ft.Column(horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=12,
                          controls=[
            svg_icon("user-robot", size=42, color=c(T.L_MUTED, T.D_MUTED)),
            ft.Text("Selectionnez une fonction IA", size=13,
                    color=c(T.L_TERTIARY, T.D_TERTIARY)),
        ]),
    )


# ===========================================================================
# Boutons d'action communs
# ===========================================================================

def _action_buttons(c, on_replace=None, on_copy=None, replace_label="Remplacer",
                    on_review=None):
    """Cree les boutons Comparer / Remplacer / Copier."""
    btns = []
    if on_review:
        btns.append(ft.Button(
                              "Comparer", height=32,
            bgcolor=c(T.L_ACCENT, T.D_ACCENT), color="#FFFFFF",
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=6),
                padding=ft.Padding(16, 0, 16, 0),
                text_style=ft.TextStyle(size=12, weight=ft.FontWeight.W_500)),
            on_click=on_review,
        ))
    if on_replace:
        btns.append(ft.OutlinedButton(
            replace_label, height=32,
            style=ft.ButtonStyle(
                color=c(T.L_SECONDARY, T.D_SECONDARY),
                side=ft.BorderSide(1, c(T.L_BORDER, T.D_BORDER)),
                shape=ft.RoundedRectangleBorder(radius=6),
                padding=ft.Padding(16, 0, 16, 0),
                text_style=ft.TextStyle(size=12)),
            on_click=on_replace,
        ))
    if on_copy:
        btns.append(ft.OutlinedButton(
            "Copier", height=32,
            style=ft.ButtonStyle(
                color=c(T.L_SECONDARY, T.D_SECONDARY),
                side=ft.BorderSide(1, c(T.L_BORDER, T.D_BORDER)),
                shape=ft.RoundedRectangleBorder(radius=6),
                padding=ft.Padding(16, 0, 16, 0),
                text_style=ft.TextStyle(size=12)),
            on_click=on_copy,
        ))
    return ft.Container(
        padding=ft.Padding(16, 12, 16, 12),
        content=ft.Row(spacing=8, controls=btns),
    )


# ===========================================================================
# 1. CORRECTION — score + corrections + suggestions
# ===========================================================================

def _build_correction_results(items, state, c, callbacks):
    if state.ai_score < 0 and not state.ai_corr:
        items.append(_build_empty(c))
        return

    # Score
    sc = c(T.L_SUCCESS, T.D_SUCCESS) if state.ai_score >= 80 \
        else c(T.L_WARNING, T.D_WARNING) if state.ai_score >= 50 \
        else c(T.L_ERROR, T.D_ERROR)

    items.append(ft.Container(
        padding=20,
        content=ft.Column(horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8,
                          controls=[
            ft.Text(str(state.ai_score), size=36, weight=ft.FontWeight.BOLD, color=sc),
            ft.Text("Score de qualite", size=12, color=c(T.L_TERTIARY, T.D_TERTIARY)),
            ft.ProgressBar(value=state.ai_score / 100, color=sc,
                           bgcolor=c(T.L_BORDER, T.D_BORDER), bar_height=6, border_radius=3),
        ]),
    ))

    dot_colors = {"orthographe": "#DC2626", "grammaire": "#EA580C",
                  "conjugaison": "#9333EA", "accord": "#2563EB", "ponctuation": "#059669"}

    # Corrections
    for cr in state.ai_corr:
        dc = dot_colors.get(cr.get("type", "").lower(), "#DC2626")
        items.append(ft.Container(
            padding=ft.Padding(16, 12, 16, 12),
            border=ft.Border.only(bottom=ft.BorderSide(1, c(T.L_BORDER, T.D_BORDER))),
            content=ft.Column(spacing=6, controls=[
                ft.Row(spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER,
                       controls=[
                    ft.Container(width=8, height=8, border_radius=4, bgcolor=dc),
                    ft.Text(cr["original"], size=13,
                            style=ft.TextStyle(decoration=ft.TextDecoration.LINE_THROUGH),
                            color=c(T.L_ERROR, T.D_ERROR)),
                    ft.Text("->", size=13, color=c(T.L_MUTED, T.D_MUTED)),
                    ft.Text(cr["correction"], size=13, weight=ft.FontWeight.W_500,
                            color=c(T.L_SUCCESS, T.D_SUCCESS)),
                ]),
                ft.Text(f"{cr.get('type','').capitalize()} -- {cr.get('explication','')}",
                        size=11, color=c(T.L_MUTED, T.D_MUTED)),
                ft.Row(spacing=8, controls=[
                    ft.OutlinedButton("Appliquer", height=28, style=ft.ButtonStyle(
                        color=c(T.L_SUCCESS, T.D_SUCCESS),
                        side=ft.BorderSide(1, c(T.L_SUCCESS, T.D_SUCCESS)),
                        shape=ft.RoundedRectangleBorder(radius=6),
                        padding=ft.Padding(12, 0, 12, 0),
                        text_style=ft.TextStyle(size=11)),
                        on_click=lambda e, o=cr["original"], r=cr["correction"]:
                            callbacks["apply_correction"](o, r)),
                    ft.OutlinedButton("Ignorer", height=28, style=ft.ButtonStyle(
                        color=c(T.L_MUTED, T.D_MUTED),
                        side=ft.BorderSide(1, c(T.L_BORDER, T.D_BORDER)),
                        shape=ft.RoundedRectangleBorder(radius=6),
                        padding=ft.Padding(12, 0, 12, 0),
                        text_style=ft.TextStyle(size=11)),
                        on_click=lambda e, item=cr:
                            callbacks["dismiss_correction"](item, "corr")),
                ]),
            ]),
        ))

    # Suggestions
    for sg in state.ai_sugg:
        items.append(ft.Container(
            padding=ft.Padding(16, 12, 16, 12),
            border=ft.Border.only(bottom=ft.BorderSide(1, c(T.L_BORDER, T.D_BORDER))),
            content=ft.Column(spacing=6, controls=[
                ft.Row(spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER,
                       controls=[
                    ft.Container(width=8, height=8, border_radius=4, bgcolor="#8B5CF6"),
                    ft.Text(sg["original"], size=13, color=c(T.L_SECONDARY, T.D_SECONDARY)),
                    ft.Text("->", size=13, color=c(T.L_MUTED, T.D_MUTED)),
                    ft.Text(sg["suggestion"], size=13, weight=ft.FontWeight.W_500,
                            color="#8B5CF6"),
                ]),
                ft.Text(f"{sg.get('type','').capitalize()} -- {sg.get('explication','')}",
                        size=11, color=c(T.L_MUTED, T.D_MUTED)),
                ft.Row(spacing=8, controls=[
                    ft.OutlinedButton("Appliquer", height=28, style=ft.ButtonStyle(
                        color="#8B5CF6", side=ft.BorderSide(1, "#8B5CF6"),
                        shape=ft.RoundedRectangleBorder(radius=6),
                        padding=ft.Padding(12, 0, 12, 0),
                        text_style=ft.TextStyle(size=11)),
                        on_click=lambda e, o=sg["original"], r=sg["suggestion"]:
                            callbacks["apply_correction"](o, r)),
                    ft.OutlinedButton("Ignorer", height=28, style=ft.ButtonStyle(
                        color=c(T.L_MUTED, T.D_MUTED),
                        side=ft.BorderSide(1, c(T.L_BORDER, T.D_BORDER)),
                        shape=ft.RoundedRectangleBorder(radius=6),
                        padding=ft.Padding(12, 0, 12, 0),
                        text_style=ft.TextStyle(size=11)),
                        on_click=lambda e, item=sg:
                            callbacks["dismiss_correction"](item, "sugg")),
                ]),
            ]),
        ))

    # Bouton copier toutes les corrections
    if state.ai_corr or state.ai_sugg:
        corr_parts = []
        if state.ai_corr:
            corr_lines = []
            for cr in state.ai_corr:
                corr_lines.append(f"- {cr['original']} -> {cr['correction']} ({cr.get('type', '')})")
            corr_parts.append("Corrections :\n" + "\n".join(corr_lines))
        if state.ai_sugg:
            sugg_lines = []
            for sg in state.ai_sugg:
                sugg_lines.append(f"- {sg['original']} -> {sg['suggestion']} ({sg.get('type', '')})")
            corr_parts.append("Suggestions :\n" + "\n".join(sugg_lines))
        corr_text = f"Score : {state.ai_score}/100\n\n" + "\n\n".join(corr_parts)
        items.append(_action_buttons(
            c,
            on_copy=lambda e, t=corr_text: callbacks["copy_result"](e, t),
        ))

    # Texte parfait
    if not state.ai_corr and not state.ai_sugg:
        items.append(ft.Container(
            padding=24, alignment=ft.Alignment(0, 0),
            content=ft.Column(horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8,
                              controls=[
                svg_icon("badge-check", size=42, color=c(T.L_SUCCESS, T.D_SUCCESS)),
                ft.Text("Texte parfait !", size=14, weight=ft.FontWeight.W_500,
                        color=c(T.L_SUCCESS, T.D_SUCCESS)),
            ]),
        ))


# ===========================================================================
# 2. TRADUCTION — texte traduit + notes
# ===========================================================================

def _build_translation_results(items, state, c, callbacks):
    if not state.ai_translation:
        items.append(_build_empty(c))
        return

    direction = "FR -> EN" if state.ai_mode == "translate_fr_en" else "EN -> FR"

    # Texte traduit
    items.append(ft.Container(
        padding=ft.Padding(16, 16, 16, 8),
        content=ft.Column(spacing=8, controls=[
            ft.Row(spacing=8, controls=[
                svg_icon("language-exchange", size=ICON_SM, color=c(T.L_ACCENT, T.D_ACCENT)),
                ft.Text(f"Traduction ({direction})", size=13, weight=ft.FontWeight.W_700,
                        color=c(T.L_PRIMARY, T.D_PRIMARY)),
            ]),
            ft.Container(
                padding=16, border_radius=8,
                bgcolor=c(T.L_HOVER, T.D_HOVER),
                border=ft.Border.all(1, c(T.L_BORDER, T.D_BORDER)),
                content=ft.Text(state.ai_translation, size=13, selectable=True,
                                color=c(T.L_PRIMARY, T.D_PRIMARY)),
            ),
        ]),
    ))

    # Boutons Remplacer / Copier
    copy_text = f"Traduction ({direction}) :\n{state.ai_translation}"
    items.append(_action_buttons(
        c,
        on_replace=lambda e: callbacks["replace_with_result"](state.ai_translation),
        on_review=(lambda e: callbacks["review_inline"]())
        if callbacks.get("review_inline") else None,
        on_copy=lambda e, t=copy_text: callbacks["copy_result"](e, t),
    ))

    # Notes de traduction
    if state.ai_translation_notes:
        items.append(ft.Container(
            padding=ft.Padding(16, 8, 16, 16),
            content=ft.Column(spacing=6, controls=[
                ft.Text("Notes de traduction", size=12, weight=ft.FontWeight.W_700,
                        color=c(T.L_TERTIARY, T.D_TERTIARY)),
            ] + [
                ft.Container(
                    padding=ft.Padding(12, 8, 12, 8), border_radius=6,
                    border=ft.Border.all(1, c(T.L_BORDER, T.D_BORDER)),
                    content=ft.Column(spacing=2, controls=[
                        ft.Text(n.get("original", ""), size=12, italic=True,
                                color=c(T.L_MUTED, T.D_MUTED)),
                        ft.Text(n.get("note", ""), size=12,
                                color=c(T.L_SECONDARY, T.D_SECONDARY)),
                    ]),
                )
                for n in state.ai_translation_notes if isinstance(n, dict)
            ]),
        ))


# ===========================================================================
# 3. REFORMULATION — texte reformule + changements
# ===========================================================================

def _build_reformulation_results(items, state, c, callbacks):
    if not state.ai_reformulation:
        items.append(_build_empty(c))
        return

    mode_icons = {
        "reformulate": "sparkles",
        "natural": "text",
        "professional": "assessment",
    }
    icon_name = mode_icons.get(state.ai_mode, "sparkles")
    mode_label = MODE_LABELS.get(state.ai_mode, "Reformulation")

    # Texte reformule
    items.append(ft.Container(
        padding=ft.Padding(16, 16, 16, 8),
        content=ft.Column(spacing=8, controls=[
            ft.Row(spacing=8, controls=[
                svg_icon(icon_name, size=ICON_SM, color=c(T.L_ACCENT, T.D_ACCENT)),
                ft.Text(mode_label, size=13, weight=ft.FontWeight.W_700,
                        color=c(T.L_PRIMARY, T.D_PRIMARY)),
            ]),
            ft.Container(
                padding=16, border_radius=8,
                bgcolor=c(T.L_HOVER, T.D_HOVER),
                border=ft.Border.all(1, c(T.L_BORDER, T.D_BORDER)),
                content=ft.Text(state.ai_reformulation, size=13, selectable=True,
                                color=c(T.L_PRIMARY, T.D_PRIMARY)),
            ),
        ]),
    ))

    # Boutons
    copy_text = f"{mode_label} :\n{state.ai_reformulation}"
    items.append(_action_buttons(
        c,
        on_replace=lambda e: callbacks["replace_with_result"](state.ai_reformulation),
        on_review=(lambda e: callbacks["review_inline"]())
        if callbacks.get("review_inline") else None,
        on_copy=lambda e, t=copy_text: callbacks["copy_result"](e, t),
    ))

    # Changements
    if state.ai_reformulation_changes:
        items.append(ft.Container(
            padding=ft.Padding(16, 8, 16, 16),
            content=ft.Column(spacing=6, controls=[
                ft.Text("Changements effectues", size=12, weight=ft.FontWeight.W_700,
                        color=c(T.L_TERTIARY, T.D_TERTIARY)),
            ] + [
                ft.Container(
                    padding=ft.Padding(12, 8, 12, 8), border_radius=6,
                    border=ft.Border.all(1, c(T.L_BORDER, T.D_BORDER)),
                    content=ft.Column(spacing=2, controls=[
                        ft.Row(spacing=6, controls=[
                            ft.Text(ch.get("before", ""), size=12,
                                    style=ft.TextStyle(decoration=ft.TextDecoration.LINE_THROUGH),
                                    color=c(T.L_ERROR, T.D_ERROR)),
                            ft.Text("->", size=12, color=c(T.L_MUTED, T.D_MUTED)),
                            ft.Text(ch.get("after", ""), size=12,
                                    color=c(T.L_SUCCESS, T.D_SUCCESS),
                                    weight=ft.FontWeight.W_500),
                        ]),
                        ft.Text(ch.get("reason", ""), size=11,
                                color=c(T.L_MUTED, T.D_MUTED)),
                    ]),
                )
                for ch in state.ai_reformulation_changes if isinstance(ch, dict)
            ]),
        ))


# ===========================================================================
# 4. RESUME — texte resume + points cles
# ===========================================================================

def _build_summary_results(items, state, c, callbacks):
    if not state.ai_summary:
        items.append(_build_empty(c))
        return

    # Reduction badge
    items.append(ft.Container(
        padding=ft.Padding(16, 16, 16, 8),
        content=ft.Column(spacing=8, controls=[
            ft.Row(spacing=8, controls=[
                svg_icon("rectangle-list", size=ICON_SM, color=c(T.L_ACCENT, T.D_ACCENT)),
                ft.Text("Resume", size=13, weight=ft.FontWeight.W_700,
                        color=c(T.L_PRIMARY, T.D_PRIMARY), expand=True),
                ft.Container(
                    padding=ft.Padding(8, 2, 8, 2), border_radius=10,
                    bgcolor=c(T.L_ACCENT_LT, T.D_ACCENT_LT),
                    content=ft.Text(
                        f"Reduction : {state.ai_reduction}" if state.ai_reduction else "",
                        size=10, color=c(T.L_ACCENT, T.D_ACCENT)),
                ) if state.ai_reduction else ft.Container(),
                svg_icon_btn("clone", size=ICON_SM, color=c(T.L_MUTED, T.D_MUTED),
                             tooltip="Copier le resume", padding=4,
                             on_click=lambda e: callbacks["copy_result"](e, f"Resume :\n{state.ai_summary}")),
            ]),
            ft.Container(
                padding=16, border_radius=8,
                bgcolor=c(T.L_HOVER, T.D_HOVER),
                border=ft.Border.all(1, c(T.L_BORDER, T.D_BORDER)),
                content=ft.Text(state.ai_summary, size=13, selectable=True,
                                color=c(T.L_PRIMARY, T.D_PRIMARY)),
            ),
        ]),
    ))

    # Boutons
    summary_copy = f"Resume :\n{state.ai_summary}"
    items.append(_action_buttons(
        c,
        on_replace=lambda e: callbacks["replace_with_result"](state.ai_summary),
        on_review=(lambda e: callbacks["review_inline"]())
        if callbacks.get("review_inline") else None,
        on_copy=lambda e, t=summary_copy: callbacks["copy_result"](e, t),
        replace_label="Remplacer par le resume",
    ))

    # Points cles
    if state.ai_key_points:
        kp_text = "Points cles :\n" + "\n".join(f"- {pt}" for pt in state.ai_key_points if isinstance(pt, str))
        items.append(ft.Container(
            padding=ft.Padding(16, 8, 16, 16),
            content=ft.Column(spacing=6, controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Text("Points cles", size=12, weight=ft.FontWeight.W_700,
                                color=c(T.L_TERTIARY, T.D_TERTIARY)),
                        svg_icon_btn("clone", size=ICON_SM, color=c(T.L_MUTED, T.D_MUTED),
                                     tooltip="Copier les points cles", padding=4,
                                     on_click=lambda e, t=kp_text: callbacks["copy_result"](e, t)),
                    ],
                ),
            ] + [
                ft.Container(
                    padding=ft.Padding(12, 6, 12, 6),
                    content=ft.Row(spacing=8, controls=[
                        ft.Container(width=6, height=6, border_radius=3,
                                     bgcolor=c(T.L_ACCENT, T.D_ACCENT)),
                        ft.Text(str(pt), size=12, expand=True,
                                color=c(T.L_SECONDARY, T.D_SECONDARY)),
                    ]),
                )
                for pt in state.ai_key_points if isinstance(pt, str)
            ]),
        ))


# ===========================================================================
# 5. MOTS-CLES — theme + mots-cles primaires/secondaires
# ===========================================================================

def _build_keywords_results(items, state, c, callbacks):
    if not state.ai_primary_keywords and not state.ai_theme:
        items.append(_build_empty(c))
        return

    # Theme
    if state.ai_theme:
        items.append(ft.Container(
            padding=ft.Padding(16, 16, 16, 8),
            content=ft.Column(spacing=8, controls=[
                ft.Row(spacing=8, controls=[
                    svg_icon("bullseye", size=ICON_SM, color=c(T.L_ACCENT, T.D_ACCENT)),
                    ft.Text("Theme", size=13, weight=ft.FontWeight.W_700,
                            color=c(T.L_PRIMARY, T.D_PRIMARY)),
                ]),
                ft.Container(
                    padding=12, border_radius=8,
                    bgcolor=c(T.L_ACCENT_LT, T.D_ACCENT_LT),
                    content=ft.Text(state.ai_theme, size=13,
                                    color=c(T.L_ACCENT, T.D_ACCENT),
                                    weight=ft.FontWeight.W_500),
                ),
            ]),
        ))

    # Mots-cles primaires (chips)
    if state.ai_primary_keywords:
        primary_chips = []
        for kw in state.ai_primary_keywords:
            if isinstance(kw, dict):
                word = kw.get("keyword", "")
                ctx = kw.get("context", "")
                primary_chips.append(ft.Container(
                    padding=ft.Padding(10, 5, 10, 5), border_radius=16,
                    bgcolor=c(T.L_ACCENT, T.D_ACCENT),
                    tooltip=ctx,
                    content=ft.Text(word, size=12, color="#FFFFFF",
                                    weight=ft.FontWeight.W_500),
                ))

        items.append(ft.Container(
            padding=ft.Padding(16, 8, 16, 8),
            content=ft.Column(spacing=8, controls=[
                ft.Text("Mots-cles principaux", size=12, weight=ft.FontWeight.W_700,
                        color=c(T.L_TERTIARY, T.D_TERTIARY)),
                ft.Row(spacing=6, wrap=True, controls=primary_chips),
            ]),
        ))

    # Mots-cles secondaires
    if state.ai_secondary_keywords:
        secondary_chips = []
        for kw in state.ai_secondary_keywords:
            if isinstance(kw, dict):
                word = kw.get("keyword", "")
                ctx = kw.get("context", "")
                secondary_chips.append(ft.Container(
                    padding=ft.Padding(10, 5, 10, 5), border_radius=16,
                    border=ft.Border.all(1, c(T.L_BORDER, T.D_BORDER)),
                    tooltip=ctx,
                    content=ft.Text(word, size=12,
                                    color=c(T.L_SECONDARY, T.D_SECONDARY)),
                ))

        items.append(ft.Container(
            padding=ft.Padding(16, 8, 16, 16),
            content=ft.Column(spacing=8, controls=[
                ft.Text("Mots-cles secondaires", size=12, weight=ft.FontWeight.W_700,
                        color=c(T.L_TERTIARY, T.D_TERTIARY)),
                ft.Row(spacing=6, wrap=True, controls=secondary_chips),
            ]),
        ))

    # Bouton copier les mots-cles
    kw_parts = []
    if state.ai_primary_keywords:
        primary = [kw.get("keyword", "") for kw in state.ai_primary_keywords if isinstance(kw, dict)]
        if primary:
            kw_parts.append("Mots cles principaux :\n" + "\n".join(f"- {w}" for w in primary))
    if state.ai_secondary_keywords:
        secondary = [kw.get("keyword", "") for kw in state.ai_secondary_keywords if isinstance(kw, dict)]
        if secondary:
            kw_parts.append("Mots-cles secondaires :\n" + "\n".join(f"- {w}" for w in secondary))
    kw_text = "\n\n".join(kw_parts)

    items.append(_action_buttons(
        c,
        on_copy=lambda e: callbacks["copy_result"](e, kw_text),
    ))
