"""
views/dialogs/setup_dialog.py -- Gestionnaire de modeles IA (Ollama).

Fonctionnalites :
  - Detection / installation d'Ollama
  - Liste des modeles disponibles avec infos detaillees
  - Telechargement avec barre de progression
  - Suppression de modeles installes
  - Selection du modele actif
"""

import threading

import flet as ft

from theme import T
from ai_checker import (
    OllamaManager, OllamaInstaller, ModelPuller,
    AVAILABLE_MODELS, MODELS_BY_ID, DEFAULT_MODEL_ID,
    check_internet,
)


def show_setup_dialog(page, c, state):
    """Affiche le gestionnaire de modeles IA."""

    # ---- Etat local du dialog ----
    status = ft.Text("Verification...", size=13, color=c(T.L_SECONDARY, T.D_SECONDARY))
    prog = ft.ProgressBar(visible=False, bar_height=6, border_radius=3,
                          color=c(T.L_ACCENT, T.D_ACCENT))
    speed = ft.Text("", size=11, color=c(T.L_MUTED, T.D_MUTED), visible=False)
    model_list_col = ft.Column(spacing=0, controls=[])
    install_section = ft.Container(visible=False)
    active_puller = [None]  # mutable ref pour le ModelPuller en cours

    # ---- Fonctions internes ----
    def close_dlg(e=None):
        page.pop_dialog()

    def check():
        """Verifie l'etat d'Ollama et rafraichit la liste."""
        try:
            _check_inner()
        except Exception as ex:
            status.value = f"Erreur : {ex}"
            page.update()

    def _check_inner():
        if not OllamaManager.is_ollama_installed():
            status.value = "Ollama n'est pas installe sur cet ordinateur."
            install_section.visible = True
            install_section.content = ft.Column(spacing=10, controls=[
                ft.Text("Ollama est necessaire pour utiliser l'IA locale.",
                        size=12, color=c(T.L_TERTIARY, T.D_TERTIARY)),
                ft.ElevatedButton(
                    "Installer Ollama",
                    bgcolor=c(T.L_ACCENT, T.D_ACCENT), color="#FFFFFF",
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                    on_click=lambda e: start_install(),
                ),
            ])
            model_list_col.controls.clear()
            page.update()
            return

        install_section.visible = False

        if not OllamaManager.is_server_running():
            status.value = "Demarrage d'Ollama..."
            page.update()
            OllamaManager.start_server()
            import time
            threading.Timer(2.5, lambda: page.run_thread(check)).start()
            return

        status.value = "Ollama est pret. Gerez vos modeles ci-dessous."
        refresh_models()
        page.update()

    def refresh_models():
        """Reconstruit la liste des modeles."""
        installed_names = OllamaManager.list_installed_models()
        model_list_col.controls.clear()

        for model in AVAILABLE_MODELS:
            is_installed = any(
                OllamaManager._model_matches(n, model["id"])
                for n in installed_names
            )
            is_selected = state.ai_selected_model == model["id"]

            # Badge d'etat
            if is_selected and is_installed:
                badge = ft.Container(
                    padding=ft.Padding(8, 2, 8, 2), border_radius=10,
                    bgcolor=c(T.L_SUCCESS, T.D_SUCCESS),
                    content=ft.Text("Actif", size=10, color="#FFFFFF",
                                    weight=ft.FontWeight.W_600),
                )
            elif is_installed:
                badge = ft.Container(
                    padding=ft.Padding(8, 2, 8, 2), border_radius=10,
                    bgcolor=c(T.L_ACCENT_LT, T.D_ACCENT_LT),
                    content=ft.Text("Installe", size=10,
                                    color=c(T.L_ACCENT, T.D_ACCENT)),
                )
            else:
                badge = ft.Container(
                    padding=ft.Padding(8, 2, 8, 2), border_radius=10,
                    border=ft.Border.all(1, c(T.L_BORDER, T.D_BORDER)),
                    content=ft.Text("Non installe", size=10,
                                    color=c(T.L_MUTED, T.D_MUTED)),
                )

            # Boutons d'action
            actions = []
            mid = model["id"]
            if is_installed and not is_selected:
                actions.append(ft.TextButton(
                    "Selectionner", height=28,
                    style=ft.ButtonStyle(
                        color=c(T.L_ACCENT, T.D_ACCENT),
                        padding=ft.Padding(8, 0, 8, 0),
                        text_style=ft.TextStyle(size=11)),
                    on_click=lambda e, m=mid: select_model(m),
                ))
            if is_installed:
                actions.append(ft.TextButton(
                    "Supprimer", height=28,
                    style=ft.ButtonStyle(
                        color=c(T.L_ERROR, T.D_ERROR),
                        padding=ft.Padding(8, 0, 8, 0),
                        text_style=ft.TextStyle(size=11)),
                    on_click=lambda e, m=mid: confirm_delete(m),
                ))
            else:
                actions.append(ft.TextButton(
                    "Telecharger", height=28,
                    style=ft.ButtonStyle(
                        color=c(T.L_ACCENT, T.D_ACCENT),
                        padding=ft.Padding(8, 0, 8, 0),
                        text_style=ft.TextStyle(size=11)),
                    on_click=lambda e, m=mid: start_pull(m),
                ))

            card = ft.Container(
                padding=ft.Padding(14, 10, 14, 10),
                border=ft.Border.only(bottom=ft.BorderSide(1, c(T.L_BORDER, T.D_BORDER))),
                bgcolor=c(T.L_ACCENT_LT, T.D_ACCENT_LT) if is_selected else None,
                content=ft.Column(spacing=4, controls=[
                    # Ligne 1 : nom + params + badge
                    ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
                        ft.Row(spacing=8, controls=[
                            ft.Text(model["name"], size=13, weight=ft.FontWeight.W_600,
                                    color=c(T.L_PRIMARY, T.D_PRIMARY)),
                            ft.Container(
                                padding=ft.Padding(6, 1, 6, 1), border_radius=8,
                                bgcolor=c(T.L_HOVER, T.D_HOVER),
                                content=ft.Text(model["params"], size=10,
                                                color=c(T.L_TERTIARY, T.D_TERTIARY)),
                            ),
                        ]),
                        badge,
                    ]),
                    # Ligne 2 : description
                    ft.Text(model["description"], size=11,
                            color=c(T.L_TERTIARY, T.D_TERTIARY)),
                    # Ligne 3 : infos techniques
                    ft.Row(spacing=12, controls=[
                        ft.Row(spacing=4, controls=[
                            ft.Icon(ft.Icons.DOWNLOAD, size=12,
                                    color=c(T.L_MUTED, T.D_MUTED)),
                            ft.Text(model["size"], size=10,
                                    color=c(T.L_MUTED, T.D_MUTED)),
                        ]),
                        ft.Row(spacing=4, controls=[
                            ft.Icon(ft.Icons.MEMORY, size=12,
                                    color=c(T.L_MUTED, T.D_MUTED)),
                            ft.Text(f"RAM : {model['recommended_ram']}", size=10,
                                    color=c(T.L_MUTED, T.D_MUTED)),
                        ]),
                        ft.Row(spacing=4, controls=[
                            ft.Icon(ft.Icons.STAR_OUTLINE, size=12,
                                    color=c(T.L_MUTED, T.D_MUTED)),
                            ft.Text(model["strengths"], size=10,
                                    color=c(T.L_MUTED, T.D_MUTED)),
                        ]),
                    ]),
                    # Ligne 4 : actions
                    ft.Row(spacing=4, controls=actions),
                ]),
            )
            model_list_col.controls.append(card)

    def select_model(model_id):
        state.ai_selected_model = model_id
        info = MODELS_BY_ID.get(model_id)
        name = info["name"] if info else model_id
        status.value = f"Modele actif : {name}"
        refresh_models()
        page.update()

    def confirm_delete(model_id):
        info = MODELS_BY_ID.get(model_id)
        name = info["name"] if info else model_id

        def do_delete(e):
            page.pop_dialog()
            status.value = f"Suppression de {name}..."
            page.update()
            ok, msg = OllamaManager.delete_model(model_id)
            if ok:
                if state.ai_selected_model == model_id:
                    state.ai_selected_model = ""
                status.value = msg
            else:
                status.value = f"Erreur : {msg}"
            refresh_models()
            page.update()
            # Re-show the setup dialog since pop_dialog closed it
            show_setup_dialog(page, c, state)

        def cancel(e):
            page.pop_dialog()
            show_setup_dialog(page, c, state)

        confirm_dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Supprimer le modele", size=15,
                          font_family="Nunito SemiBold", weight=ft.FontWeight.W_600),
            content=ft.Text(
                f"Supprimer {name} ({info['size'] if info else ''}) ?\n"
                "Cette action liberera l'espace disque.",
                size=13, color=c(T.L_SECONDARY, T.D_SECONDARY)),
            actions=[
                ft.TextButton("Annuler", on_click=cancel),
                ft.ElevatedButton("Supprimer", bgcolor=c(T.L_ERROR, T.D_ERROR),
                                  color="#FFFFFF", on_click=do_delete),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.pop_dialog()
        page.show_dialog(confirm_dlg)

    def start_install():
        """Telecharge et installe Ollama."""
        if not check_internet():
            status.value = "Pas de connexion internet."
            page.update()
            return
        prog.visible = True
        speed.visible = True
        page.update()
        OllamaInstaller(
            on_progress=lambda p, m: page.run_thread(lambda: _upd_prog(p, m)),
            on_speed=lambda s: page.run_thread(lambda: _upd_speed(s)),
            on_done=lambda m: page.run_thread(lambda: (_set_status(m), check())),
            on_error=lambda m: page.run_thread(lambda: _set_status(f"Erreur : {m}")),
        ).start()

    def start_pull(model_id):
        """Telecharge un modele."""
        if not check_internet():
            status.value = "Pas de connexion internet. Verifiez votre reseau."
            page.update()
            return

        info = MODELS_BY_ID.get(model_id)
        name = info["name"] if info else model_id
        size = info["size"] if info else "?"

        status.value = f"Telechargement de {name} ({size})..."
        prog.visible = True
        prog.value = 0
        speed.visible = True
        speed.value = ""
        cancel_btn.visible = True
        page.update()

        def on_done():
            # Auto-selectionner si aucun modele actif
            if not state.ai_selected_model:
                state.ai_selected_model = model_id
            page.run_thread(lambda: (_set_status(f"{name} installe !"), check()))

        puller = ModelPuller(
            model_id=model_id,
            on_progress=lambda p, m: page.run_thread(lambda: _upd_prog(p, m)),
            on_speed=lambda s: page.run_thread(lambda: _upd_speed(s)),
            on_done=on_done,
            on_error=lambda m: page.run_thread(lambda: _set_status(f"Erreur : {m}")),
            on_cancelled=lambda: page.run_thread(lambda: _set_status("Telechargement annule.")),
        )
        active_puller[0] = puller
        puller.start()

    def cancel_pull(e):
        if active_puller[0]:
            active_puller[0].request_cancel()

    def _upd_prog(p, m):
        prog.value = p / 100
        status.value = m
        page.update()

    def _upd_speed(s_val):
        speed.value = s_val
        page.update()

    def _set_status(m):
        status.value = m
        prog.visible = False
        speed.visible = False
        cancel_btn.visible = False
        page.update()

    # ---- Construction du dialog ----
    dlg = ft.AlertDialog(
        modal=True,
        title=ft.Row(spacing=10, controls=[
            ft.Icon(ft.Icons.SMART_TOY_OUTLINED, size=22, color=c(T.L_ACCENT, T.D_ACCENT)),
            ft.Text("Gestionnaire de modeles IA", size=16,
                    font_family="Nunito SemiBold", weight=ft.FontWeight.W_600),
        ]),
        content=ft.Container(
            width=560, height=480,
            content=ft.Column(spacing=10, controls=[
                ft.Text("Les modeles fonctionnent 100% en local sur votre PC.",
                        size=12, color=c(T.L_TERTIARY, T.D_TERTIARY)),
                ft.Divider(color=c(T.L_BORDER, T.D_BORDER)),
                status,
                prog,
                speed,
                install_section,
                ft.Container(
                    expand=True, border_radius=8,
                    border=ft.Border.all(1, c(T.L_BORDER, T.D_BORDER)),
                    clip_behavior=ft.ClipBehavior.HARD_EDGE,
                    content=ft.Column(spacing=0, expand=True,
                                      scroll=ft.ScrollMode.AUTO,
                                      controls=[model_list_col]),
                ),
            ]),
        ),
        actions=[
            cancel_btn := ft.TextButton("Annuler telechargement",
                          on_click=cancel_pull,
                          visible=False,
                          style=ft.ButtonStyle(
                              color=c(T.L_WARNING, T.D_WARNING))),
            ft.TextButton("Fermer", on_click=close_dlg),
        ],
        actions_alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
    )
    page.show_dialog(dlg)
    threading.Timer(0.3, lambda: page.run_thread(check)).start()
