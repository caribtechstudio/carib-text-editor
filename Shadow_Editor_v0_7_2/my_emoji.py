"""
my_emoji.py — Dictionnaire d'émojis pour Shadow Editor v0.8.0
==============================================================
Fournit :
  - EmojiDictionary   : 400+ émojis en 10 catégories, avec alias My_emoji
  - EMOJI_CATEGORIES  : dict ordonné {nom_catégorie: {code: char}}

Convention de nommage des codes :
  - Toujours en minuscules, sans accents
  - Mots séparés par _ (ex: :singe_bouche, :voiture_police)
  - Préfixe catégorie pour les groupes (ex: :animal_chat, :drapeau_fr)

Utilisation :
  - Tapez :code dans l'éditeur suivi d'un espace → insertion automatique
  - Ctrl+E → ouvre le sélecteur visuel

Auteur  : Arnaud
Licence : CC BY-NC-ND 4.0
Version : 0.8.0
"""


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
# Classe : EmojiDictionary
# ===========================================================================

class EmojiDictionary:
    """
    Dictionnaire complet des codes -> emojis organise par categories.
    Retrocompatible avec l'ancienne interface My_emoji.emoji_dictionnary.
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

    # Dictionnaire plat (toutes categories fusionnees)
    all_emojis: dict = {}
    for _d in categories.values():
        all_emojis.update(_d)

    # Retrocompatibilite avec l'ancienne interface
    emoji_dictionnary: dict = all_emojis


# Alias — le code existant utilise My_emoji.emoji_dictionnary
My_emoji = EmojiDictionary

# Export pratique pour le nouveau code Flet
EMOJI_CATEGORIES = EmojiDictionary.categories
EMOJI_DICT = EmojiDictionary.all_emojis
