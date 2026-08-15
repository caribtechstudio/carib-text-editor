# Journal des modifications

Format inspiré de [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/).
Carib suit le [versionnage sémantique](https://semver.org/lang/fr/).

---

## [0.14.2] — 2026-08-15

### Corrections

- Boîte d'options : le contenu débordait de la boîte de dialogue sans
  pouvoir défiler, si bien que le bouton « Fermer » se superposait au
  dernier élément (« Rechercher une mise à jour »), le rendant impossible à
  cliquer. La liste défile désormais correctement dans une hauteur fixe.

## [0.14.1] — 2026-08-15

### Corrections

- Boîte d'options : les boutons (dont « Rechercher une mise à jour ») ne
  remplissaient que la largeur de leur icône et de leur texte, laissant une
  bonne partie de leur ligne insensible au clic. Ils occupent maintenant
  toute la largeur de la boîte de dialogue.

## [0.14.0] — 2026-08-15

Première version préparée pour une distribution grand public. L'essentiel du
travail porte sur ce qui entoure l'application — licence, confidentialité,
mises à jour, diagnostic — plutôt que sur ses fonctions.

### Renommage : Glyph → Carib Text Editor

Le projet s'appelait **Glyph** jusqu'ici. Une recherche d'antériorité a révélé
deux marques verbales « GLYPH » **enregistrées et en vigueur** couvrant
précisément des logiciels :

- **FR 5017202** (RTWEB, déposée le 26/12/2023) — classe 9, « logiciels
  d'intelligence artificielle », « logiciels d'application web » ;
- **EU 018942721** (Nothing Technology Limited, déposée le 26/10/2023) —
  classe 9, « applications logicielles informatiques téléchargeables ».

Signe identique et produits identiques : le risque de confusion était direct.
Le renommage a été fait avant toute publication, donc sans installation à
migrer.

Conséquences pour qui utilisait une version de développement :

- l'exécutable devient `Carib.exe` ;
- les données passent de `%USERPROFILE%\.glyph` à `%USERPROFILE%\.carib` —
  **aucune migration automatique**, une session de développement précédente
  n'est pas reprise ;
- l'association de fichiers utilise l'identifiant `Carib.txt` ;
- le dépôt devient `caribtechstudio/carib-text-editor`.

### Sécurité et confidentialité

- **La dictée n'envoie plus rien à Google.** Jusqu'ici, `F4` transmettait
  l'audio du microphone à un service tiers **sans demander de consentement**,
  via une clé de démonstration partagée non utilisable en production. Le mode
  confidentiel ne bloquait même pas cet envoi. La reconnaissance vocale
  distante est entièrement retirée : la dictée passe désormais par celle de
  Windows (`Win`+`H`), et Carib n'accède jamais au microphone.
- **Le consentement d'envoi à une IA en ligne est révocable.** Il ne pouvait
  jusqu'ici qu'être accordé, jamais retiré.
- **Le dialogue de consentement énumère ce qui part** — texte sélectionné,
  instruction — et **ce qui ne part jamais** : nom du fichier, chemin, autres
  onglets, informations sur la machine. Il donne un lien direct vers la
  politique du fournisseur concerné.
- **Nouveau centre de confidentialité** (*Options ▸ Confidentialité*) :
  inventaire de ce qui est stocké localement, avec sa taille, et bouton
  **« Effacer mes données locales »**.
- **La désinstallation ne supprime plus vos données en silence.** Elle
  demande, et conserve par défaut. L'ancien comportement effaçait sans
  avertissement les documents jamais enregistrés.
- **Politique de confidentialité** ([CONFIDENTIALITE.md](CONFIDENTIALITE.md)),
  consultable depuis l'application.

### Mises à jour

- **Recherche automatique des nouvelles versions** sur GitHub, au plus une
  fois par jour, avec proposition d'installer **maintenant**, **plus tard**,
  ou d'ignorer une version.
- L'autorisation est demandée **au premier lancement** : aucune connexion
  n'a lieu avant la réponse. Désactivable à tout moment.
- Téléchargement vérifié avant toute exécution : origine restreinte aux
  domaines GitHub (y compris après redirection), taille annoncée, **empreinte
  SHA-256** publiée avec la release, et signature Authenticode — une signature
  présente mais invalide annule la mise à jour.
- Téléchargement annulable, avec barre de progression.

### Licences et mentions légales

- **Contrat de licence utilisateur final** ([EULA.txt](EULA.txt)), présenté
  et accepté par l'installeur.
- **Code source sous PolyForm Noncommercial 1.0.0** ([LICENSE.txt](LICENSE.txt)),
  écrite pour du logiciel — contrairement à la licence CC BY-NC-ND
  précédemment annoncée, que Creative Commons déconseille pour du code.
- **Mentions légales des composants tiers** ([TIERS.txt](TIERS.txt)), avec les
  textes intégraux des licences Apache 2.0, MPL 2.0, MIT et BSD, comme ces
  licences l'exigent à la redistribution d'un binaire.
- **Attribution Flaticon** ajoutée aux crédits, condition de la licence
  gratuite sous laquelle les icônes sont utilisées.

### Diagnostic

- **Journal technique** dans `~/.carib/logs/`, en rotation sur 1,5 Mo. Il
  n'enregistre **jamais** le contenu des documents, et les clés API y sont
  masquées automatiquement à l'écriture.
- **Filet à exceptions** sur le thread principal, les threads de travail et
  la boucle asyncio. Une erreur inattendue affiche désormais un dialogue avec
  de quoi la signaler, au lieu de laisser une fenêtre morte.

### Corrections

- **Les ressources sont de nouveau trouvées hors build.** Depuis le
  regroupement dans `core/`, `resource_path()` pointait vers `core/ressource/`,
  qui n'existe pas : le dictionnaire orthographique était introuvable quand on
  lançait Carib depuis les sources.
- **Les coûts IA sont affichés en dollars**, la devise dans laquelle les
  fournisseurs publient leurs tarifs et facturent. Les mêmes montants
  s'affichaient jusqu'ici avec un « € », soit un prix faux d'environ 8 %.
- **`Carib.spec` est de nouveau versionné.** La règle `*.spec` du
  `.gitignore` l'excluait, alors que `build.bat` en dépend : un clone frais du
  dépôt ne pouvait pas construire l'application.
- **Un seul numéro de version.** `pyproject.toml` annonçait 0.12 quand tout le
  reste affichait 0.13.2. `core/constants.py` fait désormais foi, et
  `tools/sync_version.py` le propage au build.

### Divers

- `README.md` et ce journal, qui n'existaient pas.
- Dépendances épinglées à une version exacte, pour que le binaire soit
  reproductible.
- Intégration continue GitHub Actions : tests sur Windows à chaque poussée.
- Les icônes sources Flaticon (`ressource/icon/_original/`) sortent du dépôt
  public : la licence gratuite en autorise l'usage dans l'application, pas la
  redistribution en tant que fichiers autonomes.
- L'exécutable embarque les documents légaux, consultables hors ligne.

---

## [0.13.2] et antérieures

Développement initial, non distribué publiquement. Historique dans les
messages de commit.
