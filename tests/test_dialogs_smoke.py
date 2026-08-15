"""Construction des dialogues redessinés sans moteur Flutter."""

import flet as ft

from models.document import Document


class FakePage:
    def __init__(self):
        self.dialogs = []
        self.height = 820

    def show_dialog(self, dialog):
        self.dialogs.append(dialog)

    def pop_dialog(self):
        return None

    def update(self, *controls):
        return None


def c(light, dark):
    return light


def noop(*args, **kwargs):
    return None


def test_dialogues_principaux_se_construisent():
    from views.dialogs.emoji_picker import show_emoji_picker
    from views.dialogs.help_dialog import show_help
    from views.dialogs.options_dialog import show_options
    from views.dialogs.rename_dialog import show_rename_dialog
    from views.dialogs.voice_dialog import show_voice_menu

    page = FakePage()
    show_emoji_picker(page, c, {"insert_emoji": noop})
    show_help(page, c)
    show_voice_menu(page, c, {"read_text": noop, "dictation": noop})
    show_rename_dialog(page, c, Document(title="notes.txt"), {"do_rename": noop})

    callbacks = {key: noop for key in (
        "set_mode", "toggle_theme", "toggle_auto_save", "toggle_autocomplete",
        "show_model_manager", "show_privacy", "check_updates", "show_help",
        "show_info", "show_credits",
    )}
    callbacks.update(
        is_auto_save=lambda: False,
        is_autocomplete=lambda: True,
        current_mode=lambda: "text",
        current_ai=lambda: "ChatGPT · gpt-4o-mini",
    )
    show_options(page, c, lambda: False, callbacks)

    assert len(page.dialogs) == 5
    assert all(isinstance(dialog, ft.AlertDialog) for dialog in page.dialogs)


def test_dialogues_information_et_erreur_se_construisent(tmp_path):
    from views.dialogs.error_dialog import show_crash_report
    from views.dialogs.info_dialog import show_credits, show_info

    page = FakePage()
    show_info(page, c)
    show_credits(page, c)
    show_crash_report(page, c, "Erreur", "Détail", str(tmp_path / "carib.log"))

    assert len(page.dialogs) == 3
    assert all(isinstance(dialog, ft.AlertDialog) for dialog in page.dialogs)
