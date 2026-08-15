# Politique de confidentialité de Carib

**Version 1.0 — applicable à partir de Carib 0.14.0**
**Responsable du traitement :** Arnaud — contact@caribtechstudio.com

---

## En une phrase

Carib n'a pas de serveur, ne crée pas de compte, ne collecte rien et ne
mesure rien. Vos documents restent sur votre ordinateur, sauf si **vous**
demandez explicitement à une intelligence artificielle en ligne de les
traiter.

---

## 1. Ce que Carib ne fait pas

Ces points sont vérifiables dans le code source, publié à l'adresse
<https://github.com/caribtechstudio/carib-text-editor> :

- aucun compte utilisateur, aucune inscription, aucune authentification ;
- aucune mesure d'audience, aucune télémétrie, aucun traceur, aucun cookie ;
- aucun identifiant unique de machine ou d'installation n'est généré ;
- aucun envoi automatique de rapport d'erreur ;
- aucune publicité, aucun partage ou revente de données ;
- aucun serveur exploité par l'éditeur ne reçoit quoi que ce soit.

---

## 2. Données stockées sur votre ordinateur

Tout est conservé dans le dossier `%USERPROFILE%\.carib`, lisible par votre
seul compte Windows. Rien n'en sort.

| Fichier | Contenu | Remarque |
|---|---|---|
| `session.json` | Onglets ouverts, chemins des fichiers récents, réglages (thème, zoom, mode), **contenu intégral des documents non enregistrés ou modifiés** | En clair. Nécessaire pour restaurer votre session au lancement. |
| `recovery/` | Copie de travail des documents, réécrite toutes les 15 s | En clair. Limite la perte à 15 s en cas de coupure. Effacée à la fermeture normale. |
| `credentials.dat` | Vos clés API | **Chiffré** par Windows (DPAPI), lié à votre compte. Illisible depuis un autre compte ou une autre machine. |
| `llm.json` | Réglages IA : fournisseur actif, modèles, mode confidentiel, consentement | Ne contient **jamais** de clé API. |
| `update.json` | Préférences de mise à jour, date de la dernière vérification | Aucune donnée personnelle. |
| `logs/carib.log` | Journal technique : erreurs, versions, noms de modules | **N'enregistre jamais le contenu de vos documents.** Les clés API y sont masquées automatiquement. Rotation sur 3 fichiers de 512 Ko. |
| `ipc.token` | Secret local permettant à Carib de n'ouvrir qu'une seule fenêtre | Jamais transmis. |

**Pour tout effacer :** Options ▸ Confidentialité ▸ « Effacer mes données
locales », ou supprimez le dossier `%USERPROFILE%\.carib` à la main.

À la désinstallation, Carib **vous demande** si vous souhaitez conserver ces
données. Elles ne sont jamais supprimées sans votre accord.

---

## 3. Les trois seuls cas où Carib se connecte à internet

### 3.1 — Recherche de mise à jour

**Destinataire :** GitHub, Inc. — `api.github.com`
**Fréquence :** au plus une fois par jour, au démarrage
**Envoyé :** rien d'autre que la requête HTTPS elle-même. Aucun identifiant,
aucune version, aucune donnée personnelle ne sont transmis dans la requête.
**Reçu :** la description de la dernière version publiée.

Comme pour toute connexion, GitHub voit votre adresse IP et votre agent
utilisateur ; c'est inhérent au protocole et hors du contrôle de Carib.
Voir la politique de GitHub : <https://docs.github.com/site-policy>

**Désactivation :** Options ▸ Mises à jour ▸ décochez « Vérifier
automatiquement ». Aucune connexion n'a alors plus lieu.

### 3.2 — Fonctions d'intelligence artificielle en ligne

**Ne se déclenche jamais sans :** (a) que vous ayez enregistré une clé API,
(b) que vous ayez déclenché une action IA, et (c) que vous ayez accepté
l'avertissement de sortie de données.

**Destinataire :** le fournisseur que **vous** avez choisi.

| Fournisseur | Point d'accès | Politique |
|---|---|---|
| OpenAI (ChatGPT) | `api.openai.com` | <https://openai.com/policies/privacy-policy> |
| Anthropic (Claude) | `api.anthropic.com` | <https://www.anthropic.com/legal/privacy> |
| Google (Gemini) | `generativelanguage.googleapis.com` | <https://policies.google.com/privacy> |

**Envoyé :** le texte sélectionné, ou le document entier si aucune sélection
n'est active, accompagné de l'instruction correspondant à l'action demandée.
**Jamais envoyés :** le nom du fichier, son chemin, les autres onglets, ni
aucune information sur votre machine.

Une fois le texte transmis, il est traité **sous la responsabilité du
fournisseur**, selon ses conditions et sa durée de conservation. L'éditeur de
Carib n'y a aucun accès et aucun contrôle. Consultez leur politique avant
d'activer la fonction.

**Consentement :** demandé une fois, explicitement, avant le premier envoi.
Il est **révocable à tout moment** dans Options ▸ Intelligence artificielle ▸
« Retirer mon consentement ». La révocation rétablit la demande d'accord.

**Pour ne jamais rien envoyer :** activez le **mode confidentiel** (Options ▸
IA). Tout traitement passe alors par Ollama, qui s'exécute sur votre machine.
Vous pouvez aussi marquer un document précis comme privé.

### 3.3 — Ollama (local)

**Destinataire :** `localhost:11434`, c'est-à-dire votre propre ordinateur.
Aucune donnée ne quitte la machine. Ollama est un logiciel tiers que vous
installez vous-même ; Carib ne fait que lui parler.

---

## 4. Fonctions vocales

- **Lecture à voix haute (F3)** — synthèse vocale de Windows, 100 % locale.
  Aucun envoi.
- **Dictée (F4)** — appelle la dictée intégrée de Windows (`Win`+`H`). Le
  traitement est celui de Windows et relève de la politique de confidentialité
  de Microsoft, selon vos réglages de reconnaissance vocale.
  <https://privacy.microsoft.com/privacystatement>

Carib n'enregistre, ne stocke et ne transmet aucun son. Il n'accède pas
lui-même à votre microphone.

> **Note de version :** jusqu'à la 0.13.2, la dictée passait par un service de
> reconnaissance vocale de Google. Cette fonction a été **supprimée** en
> 0.14.0 : l'audio ne sort plus de votre machine par l'intermédiaire de Carib.

---

## 5. Correction orthographique

Entièrement locale. Le dictionnaire français est embarqué dans
l'application. Aucun mot, aucune phrase n'est transmis.

---

## 6. Vos droits (RGPD)

L'éditeur de Carib ne détenant **aucune** donnée vous concernant, il n'a rien
à vous communiquer, rectifier ni effacer : les droits d'accès, de
rectification, d'effacement, de limitation, d'opposition et de portabilité
prévus aux articles 15 à 21 du RGPD s'exercent directement sur votre
ordinateur, où vous contrôlez la totalité des fichiers listés en section 2.

Pour les données que vous avez transmises à un fournisseur d'IA, ces droits
s'exercent **auprès de ce fournisseur**, aux coordonnées figurant dans sa
propre politique.

Vous pouvez introduire une réclamation auprès de la CNIL :
<https://www.cnil.fr/fr/plaintes>

---

## 7. Enfants

Carib n'est pas destiné aux moins de 15 ans et ne collecte sciemment aucune
donnée les concernant. Les fonctions d'IA en ligne relèvent des conditions
d'âge de chaque fournisseur.

---

## 8. Sécurité

- Les clés API sont chiffrées par DPAPI et liées à votre compte Windows.
  Elles ne sont jamais écrites dans un fichier de configuration en clair,
  jamais journalisées, et l'interface ne les affiche que masquées.
- Toutes les connexions sortantes utilisent HTTPS avec vérification du
  certificat.
- Les mises à jour ne sont téléchargées que depuis les domaines de GitHub,
  et leur empreinte SHA-256 est vérifiée avant toute exécution.
- Carib n'exécute jamais de script téléchargé.

Aucune mesure n'est infaillible. Si vous découvrez une faille, signalez-la à
contact@caribtechstudio.com plutôt que publiquement.

---

## 9. Modifications

Toute évolution de cette politique sera publiée avec la version de Carib
concernée et signalée dans `CHANGELOG.md`. La version applicable est celle
livrée avec votre version du logiciel.

---

*Document consultable à tout moment depuis Options ▸ Confidentialité.*
