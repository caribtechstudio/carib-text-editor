"""
my_emoji.py — Dictionnaire d'émojis et sélecteur visuel pour Shadow Editor v0.7.2
===================================================================================
Fournit :
  - EmojiDictionary   : 300+ émojis en 10 catégories, avec alias My_emoji
  - EmojiPickerDialog : sélecteur visuel avec recherche temps réel + onglets

Convention de nommage des codes :
  - Toujours en minuscules, sans accents
  - Mots séparés par _ (ex: :singe_bouche, :voiture_police)
  - Préfixe catégorie pour les groupes (ex: :animal_chat, :drapeau_fr)

Utilisation :
  - Tapez :code dans l'éditeur suivi d'un espace → insertion automatique
  - Ctrl+E → ouvre le sélecteur visuel

Auteur  : Arnaud
Licence : CC BY-NC-ND 4.0
Version : 0.7.2
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


# ===========================================================================
# Dictionnaires par catégorie
# ===========================================================================

_VISAGES = {
    ":sourire":           "😊", ":rire":              "😂", ":rire_fort":         "🤣",
    ":clin_oeil":         "😉", ":amoureux":          "😍", ":love":              "🥰",
    ":bisou":             "😘", ":langue":            "😛", ":langue_clin":       "😜",
    ":lunette":           "😎", ":reflechi":          "🤔", ":bouche_fermee":     "🤐",
    ":neutre":            "😐", ":confus":            "😕", ":inquiet":           "😟",
    ":triste":            "😢", ":pleur":             "😭", ":larme":             "🥲",
    ":peur":              "😱", ":choc":              "😨", ":anxieux":           "😰",
    ":transpire":         "😓", ":sueur":             "😅", ":gene":              "😳",
    ":colere":            "😡", ":fache":             "😠", ":fumee":             "🤬",
    ":malade":            "🤒", ":masque":            "😷", ":blessure":          "🤕",
    ":nausee":            "🤢", ":vomit":             "🤮", ":eternue":           "🤧",
    ":chaud":             "🥵", ":froid":             "🥶", ":assomme":           "😵",
    ":spirale":           "😵‍💫", ":cerveau":           "🤯", ":fete":              "🥳",
    ":yeux_etoile":       "🤩", ":fondre":            "🫠", ":content":           "😄",
    ":heureux":           "😃", ":tres_heureux":      "😁", ":grand_sourire":     "😀",
    ":ange":              "😇", ":diable":            "😈", ":demon":             "👿",
    ":crane":             "💀", ":fantome":           "👻", ":alien":             "👽",
    ":robot":             "🤖", ":clown":             "🤡", ":chat_sourire":      "😸",
    ":chat_coeur":        "😻", ":chat_pleur":        "😿", ":singe_yeux":        "🙈",
    ":singe_oreille":     "🙉", ":singe_bouche":      "🙊", ":singe_tete":        "🐵",
    ":singe_assis":       "🐒", ":caca":              "💩",
}

_MAINS = {
    ":bien":              "👍", ":mal":               "👎", ":poing":             "✊",
    ":poing_droite":      "👉", ":poing_gauche":      "👈", ":poing_haut":        "👆",
    ":poing_bas":         "👇", ":index":             "☝️", ":victoire":          "✌️",
    ":croix_doigts":      "🤞", ":rock":              "🤘", ":telephone_main":    "🤙",
    ":main_ouverte":      "✋", ":main_haute":        "🖐️", ":salut":             "👋",
    ":main_coeur":        "🫶", ":clap":              "👏", ":priere":            "🙏",
    ":poignee_main":      "🤝", ":muscle":            "💪", ":bras":              "🦾",
    ":ecriture":          "✍️", ":manucure":          "💅", ":pince":             "🤌",
    ":pincer":            "🤏", ":ok_main":           "👌", ":coeur_main":        "🫰",
    ":paume":             "🫲", ":yeux":              "👀", ":oeil":              "👁️",
    ":nez":               "👃", ":oreille":           "👂", ":cerveau_corps":     "🧠",
    ":dent":              "🦷", ":os":                "🦴", ":empreinte":         "🦶",
    ":pied":              "🦵",
}

_PERSONNES = {
    ":medecin_h":         "👨‍⚕️", ":medecin_f":         "👩‍⚕️", ":etudiant_h":       "👨‍🎓",
    ":etudiant_f":        "👩‍🎓", ":enseignant_h":      "👨‍🏫", ":enseignant_f":     "👩‍🏫",
    ":juge_h":            "👨‍⚖️", ":juge_f":            "👩‍⚖️", ":fermier_h":         "👨‍🌾",
    ":fermier_f":         "👩‍🌾", ":cuisinier_h":       "👨‍🍳", ":cuisinier_f":      "👩‍🍳",
    ":mecanicien_h":      "👨‍🔧", ":mecanicien_f":      "👩‍🔧", ":artiste_h":         "👨‍🎨",
    ":artiste_f":         "👩‍🎨", ":pompier_h":         "👨‍🚒", ":pompier_f":         "👩‍🚒",
    ":policier_h":        "👮‍♂️", ":policier_f":        "👮‍♀️", ":astronaute_h":     "👨‍🚀",
    ":astronaute_f":      "👩‍🚀", ":pilote_h":          "👨‍✈️", ":pilote_f":          "👩‍✈️",
    ":bebe":              "👶", ":enfant":            "🧒", ":garcon":            "👦",
    ":fille":             "👧", ":homme":             "👨", ":femme":             "👩",
    ":vieux":             "👴", ":vieille":           "👵", ":santa":             "🎅",
    ":fee":               "🧚", ":vampire":           "🧛", ":zombie":            "🧟",
    ":ninja":             "🥷", ":prince":            "🤴", ":princesse":         "👸",
    ":superhero":         "🦸", ":supervillain":      "🦹", ":garde":             "💂",
}

_ANIMAUX = {
    ":chien":             "🐶", ":chat":              "🐱", ":souris":            "🐭",
    ":hamster":           "🐹", ":lapin":             "🐰", ":renard":            "🦊",
    ":ours":              "🐻", ":panda":             "🐼", ":koala":             "🐨",
    ":tigre":             "🐯", ":lion":              "🦁", ":vache":             "🐮",
    ":cochon":            "🐷", ":grenouille":        "🐸", ":poulet":            "🐔",
    ":poussin":           "🐤", ":canard":            "🦆", ":aigle":             "🦅",
    ":hibou":             "🦉", ":chauve_souris":     "🦇", ":loup":              "🐺",
    ":sanglier":          "🐗", ":cheval":            "🐴", ":licorne":           "🦄",
    ":abeille":           "🐝", ":papillon":          "🦋", ":escargot":          "🐌",
    ":serpent":           "🐍", ":dragon":            "🐲", ":tortue":            "🐢",
    ":lezard":            "🦎", ":dinosaure":         "🦕", ":baleine":           "🐳",
    ":dauphin":           "🐬", ":requin":            "🦈", ":pieuvre":           "🐙",
    ":crabe":             "🦀", ":poisson":           "🐟", ":pingouin":          "🐧",
    ":flamant":           "🦩", ":paon":              "🦚", ":perroquet":         "🦜",
    ":elephant":          "🐘", ":rhinoceros":        "🦏", ":girafe":            "🦒",
    ":zebre":             "🦓", ":gorille":           "🦍", ":kangourou":         "🦘",
    ":chameau":           "🐫", ":mouton":            "🐑", ":cerf":              "🦌",
    ":oiseau":            "🐦", ":scarabee":          "🐞", ":fourmi":            "🐜",
    ":meduse":            "🪼", ":ver":               "🪱", ":rat":               "🐀",
}

_NATURE = {
    ":soleil":            "☀️", ":nuage":             "☁️", ":pluie":             "🌧️",
    ":orage":             "⛈️", ":eclair":            "⚡", ":neige":             "❄️",
    ":bonhomme_neige":    "⛄", ":vent":              "💨", ":tornade":           "🌪️",
    ":arc_en_ciel":       "🌈", ":lune":              "🌙", ":lune_pleine":       "🌕",
    ":etoile_filante":    "🌠", ":planete":           "🌍", ":globe_amerique":    "🌎",
    ":globe_asie":        "🌏", ":volcan":            "🌋", ":montagne":          "⛰️",
    ":plage":             "🏖️", ":foret":             "🌲", ":arbre":             "🌳",
    ":feuille":           "🍃", ":fleur":             "🌸", ":rose":              "🌹",
    ":tulipe":            "🌷", ":tournesol":         "🌻", ":cactus":            "🌵",
    ":champignon":        "🍄", ":feu":               "🔥", ":eau":               "💧",
    ":vague":             "🌊", ":herbe":             "🌿", ":feuille_erable":    "🍁",
    ":palmier":           "🌴", ":bouquet":           "💐", ":graine":            "🌱",
    ":comete":            "☄️", ":aurore":            "🌅", ":coucher_soleil":    "🌇",
    ":nuit_etoilee":      "🌃", ":desert":            "🏜️",
}

_NOURRITURE = {
    ":pizza":             "🍕", ":hamburger":         "🍔", ":frites":            "🍟",
    ":hotdog":            "🌭", ":sandwich":          "🥪", ":taco":              "🌮",
    ":burrito":           "🌯", ":salade":            "🥗", ":spaghetti":         "🍝",
    ":riz":               "🍚", ":ramen":             "🍜", ":soupe":             "🍲",
    ":sushi":             "🍣", ":oeuf":              "🥚", ":fromage":           "🧀",
    ":pain":              "🍞", ":croissant":         "🥐", ":baguette":          "🥖",
    ":crepe":             "🥞", ":gateau":            "🎂", ":gateau_part":       "🍰",
    ":muffin":            "🧁", ":cookie":            "🍪", ":glace":             "🍦",
    ":chocolat":          "🍫", ":bonbon":            "🍬", ":popcorn":           "🍿",
    ":pomme":             "🍎", ":poire":             "🍐", ":orange":            "🍊",
    ":citron":            "🍋", ":banane":            "🍌", ":raisin":            "🍇",
    ":fraise":            "🍓", ":myrtille":          "🫐", ":ananas":            "🍍",
    ":mangue":            "🥭", ":cerise":            "🍒", ":peche":             "🍑",
    ":kiwi":              "🥝", ":tomate":            "🍅", ":avocat":            "🥑",
    ":carotte":           "🥕", ":brocoli":           "🥦", ":cafe":              "☕",
    ":the":               "🍵", ":biere":             "🍺", ":vin":               "🍷",
    ":champagne":         "🥂", ":cocktail":          "🍹", ":lait":              "🥛",
}

_OBJETS = {
    ":telephone":         "📱", ":ordinateur":        "💻", ":clavier":           "⌨️",
    ":camera":            "📷", ":video":             "📹", ":television":        "📺",
    ":radio":             "📻", ":ecouteurs":         "🎧", ":micro":             "🎤",
    ":batterie":          "🔋", ":ampoule":           "💡", ":lampe":             "🔦",
    ":bougie":            "🕯️", ":loupe":             "🔍", ":cle":               "🔑",
    ":cadenas":           "🔒", ":marteau":           "🔨", ":outil":             "🛠️",
    ":reparation":        "🔧", ":cle_anglaise":      "🔩", ":epee":              "⚔️",
    ":bouclier":          "🛡️", ":couteau":           "🔪", ":bombe":             "💣",
    ":livre":             "📖", ":livres":            "📚", ":crayon":            "✏️",
    ":stylo":             "🖊️", ":trombone":          "📎", ":ciseaux":           "✂️",
    ":calendrier":        "📅", ":horloge":           "🕐", ":sablier":           "⏳",
    ":montre":            "⌚", ":alarme":            "⏰", ":courrier":          "📧",
    ":boite_mail":        "📬", ":colis":             "📦", ":corbeille":         "🗑️",
    ":dossier":           "📁", ":presse_papier":     "📋", ":punaise":           "📌",
    ":signet":            "🔖", ":argent":            "💰", ":billet":            "💵",
    ":carte_credit":      "💳", ":trophee":           "🏆", ":medaille":          "🥇",
    ":cadeau":            "🎁", ":ballon":            "🎈", ":confettis":         "🎊",
    ":chapeau_fete":      "🎉", ":puzzle":            "🧩", ":des":               "🎲",
    ":manette":           "🎮", ":fusee":             "🚀", ":telescope":         "🔭",
    ":microscope":        "🔬", ":pilule":            "💊", ":seringue":          "💉",
    ":thermometre":       "🌡️", ":bandage":           "🩹", ":stethoscope":       "🩺",
    ":magnet":            "🧲", ":eprouvette":        "🧪", ":atome":             "⚛️",
    ":adn":               "🧬", ":cadre":             "🖼️", ":palette":           "🎨",
    ":musique":           "🎵", ":notes":             "🎶", ":guitare":           "🎸",
    ":piano":             "🎹", ":trompette":         "🎺", ":tambour":           "🥁",
    ":bug":               "🪲", ":disque":            "💾", ":satellite":         "🛰️",
}

_TRANSPORTS = {
    ":voiture":           "🚗", ":taxi":              "🚕", ":bus":               "🚌",
    ":camion":            "🚛", ":moto":              "🏍️", ":velo":              "🚲",
    ":trottinette":       "🛴", ":train":             "🚂", ":metro":             "🚇",
    ":avion":             "✈️", ":helicoptere":       "🚁", ":bateau":            "🚢",
    ":voilier":           "⛵", ":ambulance":         "🚑", ":voiture_police":    "🚓",
    ":camion_pompier":    "🚒", ":tracteur":          "🚜", ":sous_marin":        "🤿",
    ":maison":            "🏠", ":immeuble":          "🏢", ":hopital":           "🏥",
    ":banque":            "🏦", ":hotel":             "🏨", ":ecole":             "🏫",
    ":eglise":            "⛪", ":mosque":            "🕌", ":temple":            "🛕",
    ":chateau":           "🏰", ":pont":              "🌉", ":stade":             "🏟️",
    ":feu_rouge":         "🚦", ":panneau":           "🛑", ":ancre":             "⚓",
    ":essence":           "⛽", ":gyrophare":         "🚨",
}

_SYMBOLES = {
    ":ok":                "✅", ":croix":             "❌", ":attention":         "⚠️",
    ":interdit":          "🚫", ":stop":              "🛑", ":etoile":            "⭐",
    ":etoile_brillante":  "✨", ":coeur":             "❤️", ":coeur_orange":      "🧡",
    ":coeur_jaune":       "💛", ":coeur_vert":        "💚", ":coeur_bleu":        "💙",
    ":coeur_violet":      "💜", ":coeur_noir":        "🖤", ":coeur_blanc":       "🤍",
    ":coeur_brun":        "🤎", ":coeur_rose":        "🩷", ":coeur_brise":       "💔",
    ":coeur_fleche":      "💘", ":coeur_feu":         "❤️‍🔥", ":infini":            "♾️",
    ":check":             "☑️", ":plus":              "➕", ":moins":             "➖",
    ":fois":              "✖️", ":division":          "➗", ":pourcentage":       "💯",
    ":question":          "❓", ":exclamation":       "❗", ":fleche_droite":     "➡️",
    ":fleche_gauche":     "⬅️", ":fleche_haut":       "⬆️", ":fleche_bas":        "⬇️",
    ":fleche_boucle":     "🔄", ":recycler":          "♻️", ":nouveau":           "🆕",
    ":top":               "🔝", ":musique_note":      "🎵", ":pause":             "⏸️",
    ":play":              "▶️", ":stop_btn":          "⏹️", ":suivant":           "⏭️",
    ":volume_haut":       "🔊", ":muet":              "🔇", ":cloche":            "🔔",
    ":cloche_muette":     "🔕", ":megaphone":         "📣", ":haut_parleur":      "📢",
    ":virus":             "🦠", ":radioactif":        "☢️", ":biohazard":         "☣️",
    ":paix":              "☮️", ":dollar":            "💲", ":euro":              "💶",
    ":couronne":          "👑", ":diamant":           "💎", ":cle_securite":      "🔐",
}

_DRAPEAUX = {
    ":drapeau_fr":        "🇫🇷", ":drapeau_us":       "🇺🇸", ":drapeau_gb":        "🇬🇧",
    ":drapeau_de":        "🇩🇪", ":drapeau_es":       "🇪🇸", ":drapeau_it":        "🇮🇹",
    ":drapeau_pt":        "🇵🇹", ":drapeau_br":       "🇧🇷", ":drapeau_ca":        "🇨🇦",
    ":drapeau_mx":        "🇲🇽", ":drapeau_ru":       "🇷🇺", ":drapeau_cn":        "🇨🇳",
    ":drapeau_jp":        "🇯🇵", ":drapeau_kr":       "🇰🇷", ":drapeau_in":        "🇮🇳",
    ":drapeau_au":        "🇦🇺", ":drapeau_za":       "🇿🇦", ":drapeau_ma":        "🇲🇦",
    ":drapeau_dz":        "🇩🇿", ":drapeau_sn":       "🇸🇳", ":drapeau_ci":        "🇨🇮",
    ":drapeau_cm":        "🇨🇲", ":drapeau_gp":       "🇬🇵", ":drapeau_mq":        "🇲🇶",
    ":drapeau_re":        "🇷🇪", ":drapeau_eu":       "🇪🇺", ":drapeau_blanc":     "🏳️",
    ":drapeau_arc_ciel":  "🏳️‍🌈", ":pirate":           "🏴‍☠️",
}


# ===========================================================================
# Classe : EmojiDictionary (remplace My_emoji)
# ===========================================================================

class EmojiDictionary:
    """
    Dictionnaire complet des codes → émojis organisé par catégories.
    Rétrocompatible avec l'ancienne interface My_emoji.emoji_dictionnary.
    """

    categories: dict = {
        "Visages & émotions":   _VISAGES,
        "Mains & gestes":       _MAINS,
        "Personnes":            _PERSONNES,
        "Animaux":              _ANIMAUX,
        "Nature & météo":       _NATURE,
        "Nourriture":           _NOURRITURE,
        "Objets & tech":        _OBJETS,
        "Transports":           _TRANSPORTS,
        "Symboles":             _SYMBOLES,
        "Drapeaux":             _DRAPEAUX,
    }

    # Dictionnaire plat (toutes catégories fusionnées)
    all_emojis: dict = {}
    for _d in categories.values():
        all_emojis.update(_d)

    # Rétrocompatibilité avec l'ancienne interface
    emoji_dictionnary: dict = all_emojis


# Alias de rétrocompatibilité — le code existant utilise My_emoji.emoji_dictionnary
My_emoji = EmojiDictionary


# ===========================================================================
# Classe : EmojiPickerDialog
# Sélecteur visuel avec onglets par catégorie + recherche temps réel.
# ===========================================================================

class EmojiPickerDialog(QDialog):
    """
    Fenêtre de sélection d'émojis.

    Fonctionnalités :
      - 10 onglets par catégorie avec grilles scrollables
      - Barre de recherche filtre par nom de code en temps réel
      - Clic sur un émoji → émission du signal + fermeture
      - Tooltip sur chaque bouton affiche le code utilisable

    Signal :
      emoji_selected(str) : caractère émoji sélectionné
    """

    emoji_selected = Signal(str)
    COLS = 8  # colonnes dans la grille

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Sélecteur d'émojis  —  Ctrl+E")
        self.setMinimumSize(530, 480)
        self.resize(570, 520)
        self._build_ui()

    # -- Construction de l'UI --------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 10)

        # Barre de recherche
        search_row = QHBoxLayout()
        lbl = QLabel("🔍")
        lbl.setStyleSheet("font-size: 14px;")
        self._search = QLineEdit()
        self._search.setPlaceholderText(
            "Rechercher… (ex: coeur, chat, feu, drapeau)"
        )
        self._search.textChanged.connect(self._on_search)
        self._search.setStyleSheet("padding: 4px 8px; font-size: 13px;")
        search_row.addWidget(lbl)
        search_row.addWidget(self._search, 1)
        layout.addLayout(search_row)

        # Zone résultats de recherche (masquée par défaut)
        self._result_content = QWidget()
        self._result_grid    = QGridLayout(self._result_content)
        self._result_grid.setSpacing(2)
        self._result_grid.setContentsMargins(6, 6, 6, 6)

        self._result_scroll = QScrollArea()
        self._result_scroll.setWidgetResizable(True)
        self._result_scroll.setWidget(self._result_content)
        self._result_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._result_scroll.setStyleSheet("QScrollArea { border: none; }")
        self._result_scroll.hide()
        layout.addWidget(self._result_scroll)

        # Onglets par catégorie
        self._tab_widget = QTabWidget()
        self._tab_widget.setStyleSheet(
            "QTabBar::tab { padding: 5px 9px; font-size: 11px; }"
        )
        for cat_name, cat_dict in EmojiDictionary.categories.items():
            scroll = self._build_tab(cat_dict)
            # Nom court (avant le &)
            short = cat_name.split("&")[0].strip().split(" ")[0]
            idx   = self._tab_widget.addTab(scroll, short)
            self._tab_widget.setTabToolTip(idx, cat_name)
        layout.addWidget(self._tab_widget, 1)

        # Barre inférieure
        bottom = QHBoxLayout()
        self._info = QLabel(
            f"{len(EmojiDictionary.all_emojis)} émojis  •  "
            "cliquez pour insérer, ou tapez :code dans l'éditeur"
        )
        self._info.setStyleSheet("color: gray; font-size: 11px;")
        bottom.addWidget(self._info, 1)
        btn_close = QPushButton("Fermer")
        btn_close.setFixedWidth(72)
        btn_close.clicked.connect(self.reject)
        bottom.addWidget(btn_close)
        layout.addLayout(bottom)

    def _build_tab(self, cat_dict: dict) -> QScrollArea:
        """Construit une grille scrollable pour une catégorie."""
        scroll  = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; }")

        content = QWidget()
        grid    = QGridLayout(content)
        grid.setSpacing(2)
        grid.setContentsMargins(6, 6, 6, 6)

        for idx, (code, char) in enumerate(cat_dict.items()):
            grid.addWidget(
                self._make_btn(char, code),
                idx // self.COLS,
                idx % self.COLS,
            )

        scroll.setWidget(content)
        return scroll

    def _make_btn(self, char: str, code: str) -> QPushButton:
        """Crée un bouton émoji avec tooltip."""
        btn = QPushButton(char)
        btn.setFixedSize(48, 48)
        btn.setToolTip(f"{code}  →  {char}")
        btn.setStyleSheet(
            "QPushButton {"
            "  font-size: 24px; border-radius: 6px;"
            "  border: 0.5px solid transparent; background: transparent;"
            "}"
            "QPushButton:hover {"
            "  background: rgba(128,128,128,0.13);"
            "  border: 0.5px solid rgba(128,128,128,0.25);"
            "}"
            "QPushButton:pressed { background: rgba(128,128,128,0.22); }"
        )
        btn.clicked.connect(
            lambda checked=False, e=char: self._on_clicked(e)
        )
        return btn

    def _on_clicked(self, char: str) -> None:
        """Émet l'émoji et ferme la fenêtre."""
        self.emoji_selected.emit(char)
        self.accept()

    def _on_search(self, query: str) -> None:
        """Filtre les émojis en temps réel selon la requête."""
        q = query.strip().lower()

        if not q:
            self._result_scroll.hide()
            self._tab_widget.show()
            self._info.setText(
                f"{len(EmojiDictionary.all_emojis)} émojis  •  "
                "cliquez pour insérer, ou tapez :code dans l'éditeur"
            )
            return

        # Recherche dans le nom du code (sans les deux-points)
        results = [
            (code, char)
            for code, char in EmojiDictionary.all_emojis.items()
            if q in code.strip(":")
        ]

        # Vider la grille de résultats
        while self._result_grid.count():
            item = self._result_grid.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

        for idx, (code, char) in enumerate(results):
            self._result_grid.addWidget(
                self._make_btn(char, code),
                idx // self.COLS,
                idx % self.COLS,
            )

        self._tab_widget.hide()
        self._result_scroll.show()

        n = len(results)
        self._info.setText(
            f"{n} résultat{'s' if n != 1 else ''} pour « {q} »"
        )
