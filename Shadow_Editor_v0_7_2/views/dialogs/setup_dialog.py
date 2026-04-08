"""
views/dialogs/setup_dialog.py — Configuration du correcteur IA (Ollama).
"""

import threading

import flet as ft

from theme import T
from ai_checker import (
    OllamaManager, OllamaInstaller, ModelPuller,
    OLLAMA_MODEL, MODEL_SIZE_DISPLAY,
)


def show_setup_dialog(page, c):
    """Affiche la boîte de configuration Ollama / modèle IA."""
    status = ft.Text("Vérification…", size=13, color=c(T.L_SECONDARY, T.D_SECONDARY))
    prog = ft.ProgressBar(visible=False, bar_height=6, border_radius=3)
    speed = ft.Text("", size=11, color=c(T.L_MUTED, T.D_MUTED), visible=False)
    action_btn = ft.Button("Vérifier", disabled=True)

    def check():
        if not OllamaManager.is_ollama_installed():
            status.value = "Ollama n'est pas installé."
            action_btn.text = "Installer Ollama"
            action_btn.disabled = False
            action_btn.on_click = lambda e: start_install()
        elif not OllamaManager.is_server_running():
            OllamaManager.start_server()
            status.value = "Démarrage…"
            import time
            threading.Timer(2.0, lambda: page.run_thread(check_model)).start()
        else:
            check_model()
        page.update()

    def check_model():
        if OllamaManager.is_model_available():
            status.value = f"✅ {OLLAMA_MODEL} prêt !"
            action_btn.text = "Fermer"
            action_btn.disabled = False
            action_btn.on_click = lambda e: page.pop_dialog()
        else:
            status.value = f"{OLLAMA_MODEL} non téléchargé."
            action_btn.text = f"Télécharger {OLLAMA_MODEL}"
            action_btn.disabled = False
            action_btn.on_click = lambda e: start_pull()
        page.update()

    def start_install():
        action_btn.disabled = True
        prog.visible = True
        speed.visible = True
        OllamaInstaller(
            on_progress=lambda p, m: page.run_thread(lambda: _upd_prog(p, m)),
            on_speed=lambda s: page.run_thread(lambda: _upd_speed(s)),
            on_done=lambda m: page.run_thread(lambda: (_set_status(m), check())),
            on_error=lambda m: page.run_thread(lambda: _set_status(f"Erreur: {m}")),
        ).start()

    def start_pull():
        action_btn.disabled = True
        prog.visible = True
        speed.visible = True
        ModelPuller(
            on_progress=lambda p, m: page.run_thread(lambda: _upd_prog(p, m)),
            on_speed=lambda s: page.run_thread(lambda: _upd_speed(s)),
            on_done=lambda: page.run_thread(check_model),
            on_error=lambda m: page.run_thread(lambda: _set_status(f"Erreur: {m}")),
        ).start()

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
        action_btn.disabled = False
        page.update()

    dlg = ft.AlertDialog(
        modal=True,
        title=ft.Text("Configuration — Correcteur IA", size=16, font_family="Nunito SemiBold", weight=ft.FontWeight.W_600),
        content=ft.Container(
            width=460,
            content=ft.Column(spacing=14, controls=[
                ft.Text(f"Modèle : {OLLAMA_MODEL} ({MODEL_SIZE_DISPLAY}) • 100% local",
                        size=12, color=c(T.L_TERTIARY, T.D_TERTIARY)),
                ft.Divider(color=c(T.L_BORDER, T.D_BORDER)),
                status, prog, speed,
            ]),
        ),
        actions=[
            ft.TextButton("Fermer", on_click=lambda e: page.pop_dialog()),
            action_btn,
        ],
    )
    page.show_dialog(dlg)
    threading.Timer(0.3, lambda: page.run_thread(check)).start()
