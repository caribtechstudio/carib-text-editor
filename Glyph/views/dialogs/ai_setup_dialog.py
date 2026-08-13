"""
views/dialogs/ai_setup_dialog.py — Connexion et réglage des moteurs IA.

Principes d'expérience retenus :

  * **Rien n'est bloquant.** Glyph fonctionne entièrement sans IA ; le
    dialogue le dit explicitement et propose « Plus tard ».
  * **Trente secondes pour se connecter.** Coller une clé, cliquer sur
    « Tester », voir une coche verte. Aucun téléchargement de plusieurs
    gigaoctets, contrairement au parcours Ollama d'origine.
  * **On ne choisit pas un modèle, on choisit un compromis.** Trois profils
    (économique / équilibré / qualité) au lieu d'une liste d'identifiants ;
    la sélection fine reste accessible dans « Réglages avancés ».
  * **La confidentialité est un réglage de premier plan**, pas une note de
    bas de page : c'est la première objection dans un éditeur de texte.
"""

import threading

import flet as ft

from constants import ICON_MD, ICON_SM, UI_FONT, UI_FONT_STRONG, svg_icon
from models.llm.manager import (PROFILE_LABELS, PROFILES, TIER_BEST, TIER_FAST,
                                TIER_STANDARD)
from models.llm.registry import PROVIDER_ORDER, PROVIDERS
from theme import T

_TIER_LABELS = {
    TIER_FAST: "Rapide (autocomplétion)",
    TIER_STANDARD: "Standard (correction, reformulation)",
    TIER_BEST: "Qualité (résumés, textes longs)",
}


def show_ai_setup(page, c, manager, on_changed=None):
    """Ouvre le gestionnaire d'IA.

    Args:
        manager: LLMManager.
        on_changed: appelé après toute modification de configuration.
    """
    # --- État local du dialogue ---
    ui = {
        "expanded": "",        # fournisseur dont le formulaire est déplié
        "advanced": False,
        "testing": "",         # fournisseur en cours de test, "" si aucun
        "message": "",
        "message_ok": False,
        "key_draft": "",
    }

    # Le dialogue s'adapte à la fenêtre : la barre d'état ci-dessous doit
    # rester visible sans jamais pousser les actions hors de l'écran.
    avail = page.height or 820
    body_h = max(320, min(560, avail - 280))

    body = ft.Column(spacing=10, tight=True, scroll=ft.ScrollMode.AUTO,
                     expand=True)
    #: Bandeau d'état épinglé, hors zone de défilement : le résultat d'un test
    #: doit se voir sans avoir à faire défiler la liste des fournisseurs.
    status = ft.Container(visible=False)

    def notify():
        if on_changed:
            on_changed()

    def refresh():
        body.controls = _build(page, c, manager, ui, refresh, notify)
        _apply_status(c, status, ui)
        page.update()

    def close(e=None):
        manager.save()
        notify()
        page.pop_dialog()

    dlg = ft.AlertDialog(
        title=ft.Row(spacing=10, controls=[
            svg_icon("user-robot", size=ICON_MD, color=c(T.L_ACCENT, T.D_ACCENT)),
            ft.Text("Intelligence artificielle", size=16,
                    font_family=UI_FONT_STRONG, weight=ft.FontWeight.W_700),
        ]),
        content=ft.Container(width=640, height=body_h, content=ft.Column(
            spacing=10, controls=[body, status])),
        actions=[ft.TextButton("Fermer", on_click=close)],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    body.controls = _build(page, c, manager, ui, refresh, notify)
    _apply_status(c, status, ui)
    page.show_dialog(dlg)


def _apply_status(c, status: ft.Container, ui) -> None:
    """Met à jour le bandeau d'état épinglé en bas du dialogue."""
    if not ui["message"]:
        status.visible = False
        status.content = None
        return

    busy = bool(ui["testing"])
    if busy:
        tone = c(T.L_ACCENT, T.D_ACCENT)
    elif ui["message_ok"]:
        tone = c(T.L_SUCCESS, T.D_SUCCESS)
    else:
        tone = c(T.L_ERROR, T.D_ERROR)

    leading = (
        ft.ProgressRing(width=14, height=14, stroke_width=2, color=tone) if busy
        else svg_icon("badge-check" if ui["message_ok"] else "shield-check",
                      size=ICON_SM, color=tone)
    )

    status.visible = True
    status.padding = ft.Padding(12, 10, 12, 10)
    status.border_radius = 8
    status.bgcolor = ft.Colors.with_opacity(0.12, tone)
    status.content = ft.Row(
        spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            leading,
            ft.Text(ui["message"], size=12, font_family=UI_FONT,
                    expand=True, color=tone),
        ],
    )


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

def _build(page, c, manager, ui, refresh, notify) -> list:
    controls: list = []
    configured = set(manager.configured_providers())

    controls.append(ft.Text(
        "Glyph fonctionne parfaitement sans IA. Connectez un service "
        "uniquement si vous en voulez les fonctions d'écriture.",
        size=12, font_family=UI_FONT, color=c(T.L_TERTIARY, T.D_TERTIARY),
    ))

    for key in PROVIDER_ORDER:
        controls.append(_provider_card(page, c, manager, ui, refresh, notify,
                                       key, key in configured))

    # Le message d'état n'est plus rendu ici : il vit dans le bandeau épinglé
    # (voir `_apply_status`), toujours visible sans défilement.

    if configured:
        controls.append(ft.Divider(color=c(T.L_BORDER, T.D_BORDER)))
        controls.extend(_settings_section(page, c, manager, ui, refresh, notify))

    return controls


def _provider_card(page, c, manager, ui, refresh, notify, key, connected) -> ft.Control:
    cfg = PROVIDERS[key]
    active = manager.active_provider == key and connected
    expanded = ui["expanded"] == key

    # --- Badge d'état ---
    if active:
        badge = _badge(c, "Actif", c(T.L_SUCCESS, T.D_SUCCESS), filled=True)
    elif connected:
        badge = _badge(c, "Connecté", c(T.L_ACCENT, T.D_ACCENT))
    else:
        badge = _badge(c, "Non connecté", c(T.L_MUTED, T.D_MUTED), outline=True)

    def toggle_expand(e=None):
        ui["expanded"] = "" if expanded else key
        ui["key_draft"] = manager.get_key(key) if not connected else ""
        ui["message"] = ""
        refresh()

    def activate(e=None):
        manager.active_provider = key
        manager.save()
        ui["message"] = f"{cfg.label} est maintenant le moteur actif."
        ui["message_ok"] = True
        refresh()
        notify()

    actions = []
    if connected and not active:
        actions.append(_small_btn(c, "Utiliser", activate, primary=True))
    actions.append(_small_btn(c, "Fermer" if expanded else
                              ("Régler" if connected else "Connecter"),
                              toggle_expand))

    header = ft.Row(
        spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            svg_icon(cfg.icon, size=ICON_MD,
                     color=c(T.L_ACCENT, T.D_ACCENT) if connected
                     else c(T.L_MUTED, T.D_MUTED)),
            ft.Column(spacing=1, expand=True, tight=True, controls=[
                ft.Row(spacing=8, controls=[
                    ft.Text(cfg.label, size=14, font_family=UI_FONT_STRONG,
                            color=c(T.L_PRIMARY, T.D_PRIMARY)),
                    badge,
                ]),
                ft.Text(cfg.tagline, size=11, font_family=UI_FONT,
                        color=c(T.L_MUTED, T.D_MUTED)),
            ]),
            *actions,
        ],
    )

    children = [header]
    if expanded:
        children.append(ft.Container(height=1, bgcolor=c(T.L_BORDER, T.D_BORDER)))
        children.append(
            _ollama_form(page, c, manager, ui, refresh, notify)
            if key == "ollama"
            else _key_form(page, c, manager, ui, refresh, notify, key, connected)
        )

    return ft.Container(
        padding=ft.Padding(12, 10, 12, 10), border_radius=10,
        border=ft.Border.all(
            1, c(T.L_ACCENT, T.D_ACCENT) if active else c(T.L_BORDER, T.D_BORDER)),
        bgcolor=c(T.L_ACCENT_LT, T.D_ACCENT_LT) if active else ft.Colors.TRANSPARENT,
        content=ft.Column(spacing=10, tight=True, controls=children),
    )


def _key_form(page, c, manager, ui, refresh, notify, key, connected) -> ft.Control:
    """Formulaire de saisie de clé API, avec test de connexion."""
    cfg = PROVIDERS[key]

    field = ft.TextField(
        value=ui["key_draft"],
        hint_text=f"Collez votre clé {cfg.label}…",
        password=True, can_reveal_password=True,
        text_size=12, border=ft.InputBorder.OUTLINE,
        border_radius=6, content_padding=ft.Padding(10, 8, 10, 8),
        border_color=c(T.L_BORDER, T.D_BORDER),
        focused_border_color=c(T.L_ACCENT, T.D_ACCENT),
        expand=True,
        on_change=lambda e: ui.__setitem__("key_draft", e.control.value or ""),
    )

    def test_and_save(e=None):
        if ui["testing"]:
            return          # un test est deja en cours : on ignore le clic
        candidate = (ui["key_draft"] or "").strip()
        if not candidate:
            ui["message"] = "Renseignez d'abord une clé."
            ui["message_ok"] = False
            refresh()
            return

        ui["testing"] = key
        ui["message"] = f"Test de la connexion à {cfg.label}…"
        ui["message_ok"] = True
        refresh()

        def worker():
            ok = False
            try:
                ok, msg = manager.test_connection(key, candidate)
                if ok:
                    manager.set_key(key, candidate)
                    manager.active_provider = key
                    manager.save()
                    ui["expanded"] = ""
                    ui["key_draft"] = ""
            except Exception as exc:
                # Sans ce filet, une exception tuerait le thread en laissant
                # le bandeau bloque sur « Test de la connexion… ».
                ok = False
                msg = f"Le test a échoué : {exc}"
            finally:
                ui["testing"] = ""

            ui["message"] = msg
            ui["message_ok"] = ok
            page.run_thread(refresh)
            if ok:
                page.run_thread(notify)

        threading.Thread(target=worker, daemon=True).start()

    def forget(e=None):
        manager.forget(key)
        ui["expanded"] = ""
        ui["message"] = f"Clé {cfg.label} supprimée."
        ui["message_ok"] = True
        refresh()
        notify()

    busy = ui["testing"] == key
    field.disabled = busy

    rows = [
        ft.Row(spacing=8, controls=[
            field,
            _small_btn(c, "Test en cours…" if busy else "Tester", test_and_save,
                       primary=True, busy=busy),
        ]),
        ft.Row(spacing=6, controls=[
            svg_icon("shield-check", size=ICON_SM, color=c(T.L_MUTED, T.D_MUTED)),
            ft.Text(
                "La clé est chiffrée par Windows (DPAPI) et liée à votre "
                "compte. Elle n'est jamais écrite dans les fichiers de session.",
                size=10, font_family=UI_FONT, expand=True,
                color=c(T.L_MUTED, T.D_MUTED)),
        ]),
    ]

    if cfg.key_url:
        rows.append(ft.Row(spacing=6, controls=[
            ft.Text("Obtenir une clé :", size=10, font_family=UI_FONT,
                    color=c(T.L_MUTED, T.D_MUTED)),
            ft.TextButton(
                cfg.key_url, url=cfg.key_url,
                style=ft.ButtonStyle(padding=0),
            ),
        ]))

    if connected:
        rows.append(ft.Row(spacing=10, controls=[
            ft.Text(f"Clé enregistrée : {manager.masked_key(key)}", size=11,
                    font_family=UI_FONT, expand=True,
                    color=c(T.L_TERTIARY, T.D_TERTIARY)),
            _small_btn(c, "Supprimer", forget, danger=True),
        ]))

    return ft.Column(spacing=10, tight=True, controls=rows)


def _ollama_form(page, c, manager, ui, refresh, notify) -> ft.Control:
    """Section Ollama : détection, démarrage, installation."""
    from models.ollama import DOWNLOAD_PAGE, SUGGESTED_MODELS, OllamaManager

    installed = OllamaManager.is_ollama_installed()
    running = manager.is_ollama_running()

    if running:
        models = manager.available_models("ollama", force=True)
        if models:
            status = f"Ollama fonctionne — {len(models)} modèle(s) installé(s)."
        else:
            status = ("Ollama fonctionne mais aucun modèle n'est installé. "
                      f"Lancez « ollama pull {SUGGESTED_MODELS[0]} » dans un terminal.")
        color = c(T.L_SUCCESS, T.D_SUCCESS)
    elif installed:
        status = "Ollama est installé mais n'est pas démarré."
        color = c(T.L_WARNING, T.D_WARNING)
    else:
        status = "Ollama n'est pas installé sur cet ordinateur."
        color = c(T.L_MUTED, T.D_MUTED)

    rows = [ft.Text(status, size=12, font_family=UI_FONT, color=color)]

    if installed and not running:
        def start(e=None):
            OllamaManager.start_server()
            ui["message"] = "Démarrage d'Ollama… relancez le test dans quelques secondes."
            ui["message_ok"] = True
            refresh()

        rows.append(_small_btn(c, "Démarrer Ollama", start, primary=True))

    if not installed:
        # Volontairement un lien, pas une installation automatique : Glyph
        # n'exécute aucun script téléchargé sur la machine de l'utilisateur.
        rows.append(ft.Row(spacing=6, controls=[
            ft.Text("Télécharger :", size=11, font_family=UI_FONT,
                    color=c(T.L_MUTED, T.D_MUTED)),
            ft.TextButton(DOWNLOAD_PAGE, url=DOWNLOAD_PAGE,
                          style=ft.ButtonStyle(padding=0)),
        ]))

    rows.append(ft.Row(spacing=6, controls=[
        svg_icon("shield-check", size=ICON_SM, color=c(T.L_MUTED, T.D_MUTED)),
        ft.Text(
            "Aucune donnée ne quitte votre ordinateur. Comptez 1 à 2 Go de "
            "disque par modèle, contre 0 pour un service en ligne.",
            size=10, font_family=UI_FONT, expand=True,
            color=c(T.L_MUTED, T.D_MUTED)),
    ]))

    return ft.Column(spacing=10, tight=True, controls=rows)


# ---------------------------------------------------------------------------
# Réglages
# ---------------------------------------------------------------------------

def _settings_section(page, c, manager, ui, refresh, notify) -> list:
    controls = [ft.Text("Réglages", size=13, font_family=UI_FONT_STRONG,
                        color=c(T.L_PRIMARY, T.D_PRIMARY))]

    # --- Profil ---
    def set_profile(profile):
        manager.profile = profile
        manager.save()
        refresh()
        notify()

    controls.append(ft.Column(spacing=6, tight=True, controls=[
        ft.Text("Compromis qualité / coût", size=11, font_family=UI_FONT,
                color=c(T.L_TERTIARY, T.D_TERTIARY)),
        ft.Row(spacing=6, controls=[
            _chip(c, PROFILE_LABELS[p], manager.profile == p,
                  lambda e, p=p: set_profile(p))
            for p in PROFILES
        ]),
    ]))

    # --- Mode confidentiel ---
    def toggle_privacy(e):
        manager.privacy_mode = bool(e.control.value)
        manager.save()
        refresh()
        notify()

    controls.append(_switch_row(
        c, "shield-trust", "Mode confidentiel",
        "Force le traitement local (Ollama). Aucune action IA n'envoie de texte en ligne.",
        manager.privacy_mode, toggle_privacy,
    ))

    # --- Repli local ---
    def toggle_fallback(e):
        manager.fallback_local = bool(e.control.value)
        manager.save()

    controls.append(_switch_row(
        c, "shield-divided-four", "Repli automatique sur Ollama",
        "Si le service en ligne est indisponible ou le crédit épuisé.",
        manager.fallback_local, toggle_fallback,
    ))

    # --- Budget ---
    def set_budget(e):
        try:
            manager.budget_alert = max(0.0, float((e.control.value or "0").replace(",", ".")))
        except ValueError:
            manager.budget_alert = 0.0
        manager.save()

    controls.append(ft.Row(
        spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            svg_icon("hand-holding-usd", size=ICON_MD, color=c(T.L_ACCENT, T.D_ACCENT)),
            ft.Column(spacing=1, expand=True, tight=True, controls=[
                ft.Text("Alerte de dépense", size=13,
                        color=c(T.L_PRIMARY, T.D_PRIMARY)),
                ft.Text("Prévenir quand la session dépasse ce montant. 0 = jamais.",
                        size=10, font_family=UI_FONT,
                        color=c(T.L_MUTED, T.D_MUTED)),
            ]),
            ft.TextField(
                value=f"{manager.budget_alert:.2f}", width=80, text_size=12,
                suffix=ft.Text("€", size=12), border_radius=6,
                content_padding=ft.Padding(8, 6, 4, 6),
                border_color=c(T.L_BORDER, T.D_BORDER),
                on_blur=set_budget, on_submit=set_budget),
        ],
    ))

    # --- Consommation ---
    usage = manager.session_usage
    controls.append(ft.Row(spacing=10, controls=[
        ft.Text(
            f"Cette session : {usage.total_tokens:,} jetons  ·  "
            f"≈ {manager.session_cost:.3f} €".replace(",", " "),
            size=11, font_family=UI_FONT, expand=True,
            color=c(T.L_TERTIARY, T.D_TERTIARY)),
        _small_btn(c, "Réinitialiser",
                   lambda e: (manager.reset_usage(), refresh(), notify())),
    ]))

    # --- Avancé ---
    def toggle_advanced(e=None):
        ui["advanced"] = not ui["advanced"]
        refresh()

    controls.append(ft.Container(
        ink=True, on_click=toggle_advanced, border_radius=6,
        padding=ft.Padding(0, 6, 0, 6),
        content=ft.Row(spacing=6, controls=[
            svg_icon("angle-circle-down" if ui["advanced"] else "angle-circle-right",
                     size=ICON_SM, color=c(T.L_MUTED, T.D_MUTED)),
            ft.Text("Réglages avancés — choisir les modèles", size=11,
                    font_family=UI_FONT, color=c(T.L_TERTIARY, T.D_TERTIARY)),
        ]),
    ))

    if ui["advanced"]:
        controls.append(_model_picker(page, c, manager, refresh))

    return controls


def _model_picker(page, c, manager, refresh) -> ft.Control:
    """Sélection explicite d'un modèle par niveau, pour le fournisseur actif."""
    provider = manager.active_provider
    if provider not in manager.configured_providers():
        return ft.Text("Aucun fournisseur actif.", size=11, italic=True,
                       color=c(T.L_MUTED, T.D_MUTED))

    models = manager.available_models(provider)
    if not models:
        return ft.Text(
            "Liste des modèles indisponible — vérifiez la connexion.",
            size=11, italic=True, color=c(T.L_MUTED, T.D_MUTED))

    rows = []

    for tier in (TIER_FAST, TIER_STANDARD, TIER_BEST):
        def on_select(e, t=tier):
            manager.set_model(provider, t, e.control.value)

        rows.append(ft.Row(
            spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Text(_TIER_LABELS[tier], size=11, width=230,
                        font_family=UI_FONT, color=c(T.L_TERTIARY, T.D_TERTIARY)),
                ft.Dropdown(
                    value=manager.model_for(provider, tier),
                    # Options reconstruites pour chaque menu : un controle Flet
                    # ne peut pas etre partage entre plusieurs parents.
                    options=[ft.DropdownOption(key=m.id, text=m.id)
                             for m in models],
                    expand=True, text_size=11,
                    border_radius=6, content_padding=ft.Padding(8, 4, 8, 4),
                    border_color=c(T.L_BORDER, T.D_BORDER),
                    on_select=on_select),
            ],
        ))

    rows.append(ft.Row(spacing=8, controls=[
        ft.Text(f"{len(models)} modèles récupérés depuis {PROVIDERS[provider].label}.",
                size=10, font_family=UI_FONT, expand=True,
                color=c(T.L_MUTED, T.D_MUTED)),
        _small_btn(c, "Actualiser",
                   lambda e: (manager.available_models(provider, force=True), refresh())),
    ]))

    return ft.Column(spacing=8, tight=True, controls=rows)


# ---------------------------------------------------------------------------
# Petits composants
# ---------------------------------------------------------------------------

def _badge(c, label, color, filled=False, outline=False) -> ft.Control:
    return ft.Container(
        padding=ft.Padding(8, 2, 8, 2), border_radius=10,
        bgcolor=color if filled else (
            ft.Colors.TRANSPARENT if outline
            else ft.Colors.with_opacity(0.14, color)),
        border=ft.Border.all(1, c(T.L_BORDER, T.D_BORDER)) if outline else None,
        content=ft.Text(label, size=10, font_family=UI_FONT_STRONG,
                        color="#FFFFFF" if filled else color),
    )


def _small_btn(c, label, on_click, primary=False, danger=False,
               busy=False) -> ft.Control:
    if primary:
        bg, fg = c(T.L_ACCENT, T.D_ACCENT), "#FFFFFF"
    elif danger:
        bg, fg = ft.Colors.TRANSPARENT, c(T.L_ERROR, T.D_ERROR)
    else:
        bg, fg = ft.Colors.TRANSPARENT, c(T.L_SECONDARY, T.D_SECONDARY)

    text = ft.Text(label, size=11, font_family=UI_FONT_STRONG, color=fg)
    content = ft.Row(spacing=8, tight=True,
                     vertical_alignment=ft.CrossAxisAlignment.CENTER,
                     controls=[ft.ProgressRing(width=12, height=12,
                                               stroke_width=2, color=fg),
                               text]) if busy else text

    return ft.Container(
        padding=ft.Padding(12, 6, 12, 6), border_radius=6, ink=not busy,
        bgcolor=ft.Colors.with_opacity(0.55, bg) if busy and primary else bg,
        border=None if primary else ft.Border.all(1, c(T.L_BORDER, T.D_BORDER)),
        on_click=None if busy else on_click,
        content=content,
    )


def _chip(c, label, active, on_click) -> ft.Control:
    return ft.Container(
        padding=ft.Padding(12, 6, 12, 6), border_radius=14, ink=True,
        bgcolor=c(T.L_ACCENT, T.D_ACCENT) if active else c(T.L_HOVER, T.D_HOVER),
        on_click=on_click,
        content=ft.Text(label, size=11, font_family=UI_FONT_STRONG,
                        color="#FFFFFF" if active else c(T.L_SECONDARY, T.D_SECONDARY)),
    )


def _switch_row(c, icon, title, subtitle, value, on_change) -> ft.Control:
    return ft.Row(
        spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            svg_icon(icon, size=ICON_MD, color=c(T.L_ACCENT, T.D_ACCENT)),
            ft.Column(spacing=1, expand=True, tight=True, controls=[
                ft.Text(title, size=13, color=c(T.L_PRIMARY, T.D_PRIMARY)),
                ft.Text(subtitle, size=10, font_family=UI_FONT,
                        color=c(T.L_MUTED, T.D_MUTED)),
            ]),
            ft.Switch(value=value, active_color=c(T.L_ACCENT, T.D_ACCENT),
                      on_change=on_change),
        ],
    )


# ---------------------------------------------------------------------------
# Consentement cloud
# ---------------------------------------------------------------------------

def show_cloud_consent(page, c, manager, on_accept):
    """Demande explicite avant le premier envoi de texte vers un service distant."""
    from models.llm.registry import PROVIDERS as _P

    provider, _ = manager.resolve("edit")
    label = _P[provider].label if provider in _P else "un service en ligne"

    remember = ft.Checkbox(value=True, label="Ne plus demander",
                           active_color=c(T.L_ACCENT, T.D_ACCENT))

    def accept(e):
        if remember.value:
            manager.cloud_consent = True
            manager.save()
        page.pop_dialog()
        on_accept()

    dlg = ft.AlertDialog(
        modal=True,
        title=ft.Text("Envoyer ce texte à " + label + " ?", size=16,
                      font_family=UI_FONT_STRONG, weight=ft.FontWeight.W_700),
        content=ft.Container(width=440, content=ft.Column(spacing=12, tight=True, controls=[
            ft.Text(
                f"Le texte sélectionné sera transmis à {label} pour être traité. "
                "Il quitte donc votre ordinateur.",
                size=13, color=c(T.L_SECONDARY, T.D_SECONDARY)),
            ft.Row(spacing=8, controls=[
                svg_icon("shield-check", size=ICON_SM, color=c(T.L_MUTED, T.D_MUTED)),
                ft.Text(
                    "Pour un traitement 100 % local, activez le mode "
                    "confidentiel dans les options IA.",
                    size=11, expand=True, font_family=UI_FONT,
                    color=c(T.L_MUTED, T.D_MUTED)),
            ]),
            remember,
        ])),
        actions=[
            ft.TextButton("Annuler", on_click=lambda e: page.pop_dialog()),
            ft.Button("Envoyer", bgcolor=c(T.L_ACCENT, T.D_ACCENT),
                      color="#FFFFFF", on_click=accept),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    page.show_dialog(dlg)
