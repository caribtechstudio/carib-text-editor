"""
controllers/command_registry.py — Catalogue des commandes de la palette.

Séparé d'`AppController` : c'est une **table de données**, pas de la logique
d'orchestration. La garder à part évite qu'ajouter une commande ne fasse
grossir le contrôleur principal, et rend le catalogue lisible d'un coup d'œil.

Toute action de Carib doit figurer ici : la palette (Ctrl+Maj+P) est le point
d'entrée universel, et une fonctionnalité absente du catalogue est une
fonctionnalité que l'utilisateur ne découvrira jamais.
"""

from views.command_palette import Command


def build_commands(app) -> list[Command]:
    """Construit le catalogue à partir des contrôleurs d'`app`."""

    def cmd(cid, label, action, group="", hint="", icon="bolt"):
        return Command(cid, label, action, group, hint, icon)

    return [
        cmd("file.new", "Nouveau document", app._new_tab,
            "Fichier", "Ctrl+N", "add-document"),
        cmd("file.open_folder", "Ouvrir un dossier…",
            lambda: app.page.run_task(app.open_workspace),
            "Fichier", "", "folder-open"),
        cmd("file.close_folder", "Fermer le dossier", app.close_workspace,
            "Fichier", "", "folder"),
        cmd("file.open", "Ouvrir un fichier…",
            lambda: app.page.run_task(app.file_ctrl.open_file),
            "Fichier", "Ctrl+O", "folder-open"),
        cmd("file.save", "Enregistrer",
            lambda: app.page.run_task(app.file_ctrl.save_file),
            "Fichier", "Ctrl+S", "disk"),
        cmd("file.saveas", "Enregistrer sous…",
            lambda: app.page.run_task(app.file_ctrl.save_file_as),
            "Fichier", "Ctrl+Maj+S", "floppy-disk-pen"),
        cmd("file.rename", "Renommer le document",
            app.file_ctrl.rename_current_file, "Fichier", "", "edit"),
        cmd("file.print", "Imprimer", app.file_ctrl.print_file,
            "Fichier", "Ctrl+P", "print"),

        cmd("tab.close", "Fermer l'onglet",
            lambda: app._confirm_close_tab(app.state.idx),
            "Onglets", "Ctrl+W", "trash-xmark"),
        cmd("tab.next", "Onglet suivant", app.tab_ctrl.next_tab,
            "Onglets", "Ctrl+Tab", "arrow-circle-right"),
        cmd("tab.prev", "Onglet précédent", app.tab_ctrl.prev_tab,
            "Onglets", "Ctrl+Maj+Tab", "arrow-circle-left"),

        cmd("edit.undo", "Annuler", app.undo, "Édition", "Ctrl+Z", "rotate-left"),
        cmd("edit.redo", "Rétablir", app.redo, "Édition", "Ctrl+Y", "turn-right"),
        cmd("edit.find", "Rechercher", app.search_ctrl.toggle_search,
            "Édition", "Ctrl+F", "search"),
        cmd("edit.replace", "Rechercher et remplacer",
            app.search_ctrl.toggle_replace, "Édition", "Ctrl+H", "duplicate"),
        cmd("edit.goto", "Aller à la ligne…", app.show_goto_line,
            "Édition", "Ctrl+G", "list"),
        cmd("edit.emoji", "Insérer un emoji", app._show_emoji_picker,
            "Édition", "Ctrl+E", "laugh-beam"),
        cmd("edit.clear", "Effacer tout le contenu", app.clip_ctrl.clear,
            "Édition", "", "trash-xmark"),

        cmd("ai.ask", "IA — Demander (prompt libre)",
            app.ux_ctrl.open_command_bar, "IA", "Ctrl+K", "sparkles"),
        cmd("ai.correct", "IA — Corriger l'orthographe",
            app.ai_ctrl.run_correction, "IA", "F7", "badge-check"),
        cmd("ai.reformulate", "IA — Reformuler",
            app.ai_ctrl.run_reformulate, "IA", "F9", "sparkles"),
        cmd("ai.natural", "IA — Ton naturel", app.ai_ctrl.run_natural,
            "IA", "", "sparkles"),
        cmd("ai.professional", "IA — Ton professionnel",
            app.ai_ctrl.run_professional, "IA", "", "sparkles"),
        cmd("ai.summarize", "IA — Résumer", app.ai_ctrl.run_summarize,
            "IA", "", "bars-staggered"),
        cmd("ai.keywords", "IA — Extraire les mots-clés",
            app.ai_ctrl.run_keywords, "IA", "", "bullseye"),
        cmd("ai.fr_en", "IA — Traduire français → anglais",
            app.ai_ctrl.run_translate_fr_en, "IA", "F8", "language-exchange"),
        cmd("ai.en_fr", "IA — Traduire anglais → français",
            app.ai_ctrl.run_translate_en_fr, "IA", "", "language-exchange"),
        cmd("ai.setup", "IA — Configurer les moteurs", app._show_ai_setup,
            "IA", "", "user-robot"),
        cmd("ai.privacy", "IA — Mode confidentiel global",
            app._toggle_privacy_mode, "IA", "", "shield-trust"),
        cmd("ai.privacy_doc", "IA — Ce document reste local",
            app.toggle_document_private, "IA", "", "shield-check"),

        cmd("view.theme", "Basculer le thème clair / sombre", app.toggle_theme,
            "Affichage", "", "moon-stars"),
        cmd("view.toolbar", "Afficher / masquer la barre d'outils",
            app.toggle_toolbar, "Affichage", "Ctrl+T", "tile"),
        cmd("view.sidebar", "Afficher / masquer la barre latérale",
            app.toggle_sidebar, "Affichage", "", "menu-burger"),
        cmd("view.zoom_in", "Zoom avant", app.zoom_in, "Affichage",
            "Ctrl++", "square-plus"),
        cmd("view.zoom_out", "Zoom arrière", app.zoom_out, "Affichage",
            "Ctrl+-", "minus-circle"),
        cmd("view.zoom_reset", "Zoom 100 %", app.zoom_reset, "Affichage",
            "Ctrl+0", "bullseye"),
        cmd("view.mode_text", "Mode Texte", lambda: app.set_mode("text"),
            "Affichage", "Ctrl+1", "pen-field"),
        cmd("view.mode_calc", "Mode Calcul", lambda: app.set_mode("calc"),
            "Affichage", "Ctrl+2", "calculator-simple"),
        cmd("view.mode_read", "Mode Lecture", lambda: app.set_mode("read"),
            "Affichage", "Ctrl+3", "book-open-cover"),
        cmd("view.syntax", "Coloration syntaxique", app.toggle_syntax,
            "Affichage", "", "customization"),
        cmd("view.linenumbers", "Numéros de ligne", app.toggle_line_numbers,
            "Affichage", "", "list"),
        cmd("view.mdpreview", "Aperçu Markdown côte à côte", app.toggle_md_preview,
            "Affichage", "Ctrl+Maj+M", "book"),

        cmd("tool.spell", "Vérifier l'orthographe (local)", app.check_spelling,
            "Outils", "F6", "filter-check"),
        cmd("tool.voice", "Lecture et dictée vocale", app._show_voice_menu,
            "Outils", "F3", "circle-microphone-lines"),
        cmd("tool.autocomplete", "Activer / désactiver l'autocomplétion",
            app.toggle_autocomplete, "Outils", "", "text"),
        cmd("tool.autosave", "Activer / désactiver la sauvegarde auto",
            app.toggle_auto_save, "Outils", "", "disk"),
        cmd("tool.resident", "Garder Carib actif en arrière-plan",
            app.toggle_stay_resident, "Outils", "", "bolt"),
        cmd("tool.options", "Options", app._show_options, "Outils", "", "settings"),
        cmd("tool.recovery", "Récupérer un document non enregistré",
            app.show_recovery, "Outils", "", "shield-check"),
        cmd("tool.help", "Aide", app._show_help, "Outils", "F1", "interrogation"),
    ]
