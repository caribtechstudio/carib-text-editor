import random

class PhrasePlaceHolder:
    def __init__(self):
        self.placeholders = [
            "Laissez libre cours à votre imagination, commencez à écrire ici...",
            "Chaque mot compte, débutez votre histoire maintenant...",
            "Un texte inspiré commence par une pensée, écrivez-la...",
            "Exprimez-vous, vos idées méritent d'être notées...",
            "Un mot peut changer le monde, écrivez-le ici...",
            "L'inspiration frappe à tout moment, saisissez-la ici...",
            "Votre aventure commence maintenant...",
            "Les grandes idées commencent par de petits mots...",
            "Laissez vos pensées s'envoler sur cette page...",
            "Écrivez ce qui vous passe par la tête, chaque mot compte...",
            "Les mots sont puissants, utilisez-les bien...",
            "Un voyage de mille mots commence par un seul ici...",
            "Laissez vos idées s'exprimer librement...",
            "Chaque histoire mérite d'être racontée, commencez ici...",
            "Un mot peut ouvrir un univers de possibilités...",
            "La première phrase est toujours la plus difficile, commencez ici...",
            "Libérez votre créativité, commencez à écrire...",
            "Les mots peuvent faire des miracles, commencez maintenant...",
            "Un mot écrit ici peut inspirer des milliers...",
            "Un mot en amène un autre, écrivez ce premier mot ici...",
            "L'inspiration vient en écrivant, laissez votre plume s'exprimer ici...",
            "Chaque idée commence par une première lettre, écrivez la vôtre ci-dessous...",
            "Les mots se tissent au fur et à mesure, commencez par celui-ci...",
            "Écrire, c'est donner vie aux pensées, débutez ici...",
            "Un texte naît d'une première pensée, posez-la ici...",
            "Tout récit débute par une simple phrase, la vôtre commence ici...",
            "De petites idées naissent de grandes créations, laissez la vôtre s'épanouir ici...",
            "Le début d'une histoire est souvent le plus simple, commencez ici...",
            "Chaque mot que vous tapez ouvre une nouvelle porte, commencez par celle-ci...",
            "Écrire, c'est voyager avec des mots, commencez le vôtre ici...",
            "Laissez votre plume danser sur la page, l'histoire commence ici...",
            "Chaque mot que vous écrivez est une étoile dans votre univers littéraire...",
            "Écrivez avec le cœur, laissez vos émotions guider chaque ligne...",
            "Transformez vos pensées en poésie, commencez maintenant...",
            "Un mot à la fois, créez un chef-d'œuvre littéraire...",
            "Les mots ont des ailes, laissez-les s'envoler sur cette page...",
            "Écrire, c'est peindre avec des mots, commencez votre tableau ici...",
            "Un simple mot peut déclencher une avalanche d'idées, écrivez-le...",
            "Chaque phrase est une brique dans le château de votre imagination...",
            "Plongez votre plume dans l'encre de vos rêves, commencez ici...",
            "Écrivez comme si personne ne lisait, laissez libre cours à votre créativité...",
            "Les mots sont des trésors, trouvez les vôtres et partagez-les...",
            "Chaque idée est une graine, plantez-la et regardez-la grandir ici...",
            "Laissez vos pensées couler comme une rivière sur cette page...",
            "Un mot peut illuminer l'obscurité, écrivez-le et partagez sa lumière..."
        ]

    def get_random_phrase(self):
        return random.choice(self.placeholders)
