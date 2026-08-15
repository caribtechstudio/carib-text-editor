# Audit de mise en production — Glyph v0.13.2

Date : 14 août 2026 · Cible : distribution grand public, Windows 10+ (1809 min.)

---

## 1. Ce qui est prêt

Le socle technique est sérieux et au-dessus de la moyenne pour un projet solo.

| Domaine | État |
|---|---|
| Tests | 326 tests, tous verts en 34 s (`python -m pytest tests/`) |
| Intégrité des données | Écriture atomique via `tempfile` + `os.replace`, encodage et fins de ligne préservés (`models/file_manager.py`) |
| Récupération | `models/recovery.py` + session restaurée, contenu non enregistré conservé même si le fichier disparaît |
| Secrets | Clés API chiffrées DPAPI avec entropie secondaire, jamais dans `session.json` (`models/llm/credentials.py`) |
| Consentement IA | Demande explicite avant le premier envoi de texte à un service distant (`views/dialogs/ai_setup_dialog.py:618`) |
| Mode confidentiel | Force Ollama, global **et** par document (`models/llm/manager.py:298`) |
| Coût | Suivi par session + seuil d'alerte budgétaire |
| Instance unique | IPC par jeton partagé dans `~/.glyph/ipc.token` |
| Démarrage | Imports différés systématiques, mode dossier PyInstaller — travail visiblement soigné |
| Installeur | Inno Setup fonctionnel : associations `.txt/.md/.log`, désinstallation, FR/EN |

Rien dans cette colonne ne bloque la mise en production.

---

## 2. Bloquants juridiques — copyright et licences

C'est la zone la plus faible du projet, et la plus risquée en distribution grand public.

### 2.1 — Aucun fichier de licence n'existe *(bloquant)*

`CC BY-NC-ND 4.0` est déclarée dans trois docstrings et deux dialogues, mais :
- il n'y a **aucun** `LICENSE` / `LICENSE.txt` dans le dépôt ;
- `installer/setup.iss:45` a sa ligne `LicenseFile=` commentée — l'installeur ne présente donc aucune condition d'utilisation ;
- rien ne distingue la licence du **code** de celle du **binaire distribué**.

### 2.2 — CC BY-NC-ND est un mauvais choix pour un logiciel *(à trancher)*

Creative Commons déconseille explicitement ses licences pour le logiciel. Concrètement :
- pas de clause adaptée sur le code source vs. le binaire ;
- la clause de non-garantie / limitation de responsabilité est faible face à un EULA — or vous distribuez un éditeur de texte à des inconnus, qui peuvent perdre des données ;
- `ND` interdit toute œuvre dérivée : ni fork, ni patch, ni contribution. Est-ce l'intention ?
- `NC` est notoirement flou (un usage en entreprise interne est-il commercial ?).

**Recommandation :** si l'objectif est « gratuit, pas de revente, pas de fork », partez sur un **EULA propriétaire court** pour le binaire (c'est ce que présente l'installeur), éventuellement doublé de **PolyForm Noncommercial 1.0.0** pour le code du dépôt. Les deux sont écrites pour du logiciel et couvrent la responsabilité.

### 2.3 — Icônes : ~240 SVG sans attribution *(bloquant, risque le plus concret)*

`ressource/icon/` contient environ 240 SVG dont le format (`viewBox="0 0 24 24"`, `id="Layer_1" data-name="Layer_1"`) correspond aux **UIcons de Flaticon**. La licence gratuite Flaticon impose :
1. une **attribution visible** dans l'application ;
2. l'**interdiction de redistribuer les fichiers sources** — or les SVG sont embarqués tels quels dans le build *et* publiés dans le dépôt Git, y compris `_original/`.

Le dialogue Crédits (`views/dialogs/info_dialog.py:27`) ne mentionne aucune icône.

**Trois issues :** licence Flaticon payante (~10 €/mois, lève l'attribution), attribution complète dans les crédits, ou remplacement par un jeu sous licence permissive (Lucide — ISC, Phosphor — MIT, Tabler — MIT).

### 2.4 — Licences des dépendances non exposées *(bloquant)*

Distribuer un `.exe` PyInstaller **est** une redistribution binaire de chaque dépendance. Chacune l'exige :

| Composant | Licence | Obligation à la redistribution |
|---|---|---|
| Flet | Apache-2.0 | Copie de la licence + fichier NOTICE |
| pyttsx3 | MPL-2.0 | Mention + accès au source du module |
| SpeechRecognition | BSD-3-Clause | Reproduction du copyright et du disclaimer |
| pyspellchecker | MIT | Reproduction de la notice |
| Nunito | OFL 1.1 | `OFL.txt` livré (✅ présent) mais à exposer dans l'app |
| Python, requests, … | PSF / Apache-2.0 | Mentions |

**À faire :** un fichier `TIERS.txt` livré par l'installeur + une entrée « Mentions légales » dans le dialogue Crédits. C'est mécanique, comptez une demi-journée.

### 2.5 — Marque « Glyph » non vérifiée *(à vérifier avant lancement)*

Le nom est déjà utilisé pour des produits logiciels (notamment le launcher de jeux *Glyph* de Trion/Gamigo). Une recherche d'antériorité INPI/EUIPO s'impose avant toute communication publique. Le dépôt de marque n'est pas obligatoire, mais découvrir un conflit après 5 000 installations coûte cher.

### 2.6 — Modèle Ollama cité dans les crédits

Les crédits mentionnent « ministral-3:3b ». Vérifiez la licence du modèle recommandé : les modèles Ministral 3B de Mistral sont sous licence de recherche non commerciale. Recommander un téléchargement est sans risque ; l'embarquer ou le présenter comme composant du produit ne l'est pas.

---

## 3. Bloquants confidentialité

### 3.1 — La dictée F4 envoie votre micro à Google sans consentement *(bloquant sérieux)*

`models/voice_manager.py:96` appelle `recognizer.recognize_google(audio, language="fr-FR")`. Deux problèmes distincts :

**Juridique/technique :** sans argument `key`, SpeechRecognition utilise une **clé de démonstration Google partagée**, destinée aux tests, sans contrat, sans SLA, révocable à tout moment. Elle n'est pas utilisable en production.

**Vie privée :** l'audio du micro part chez un tiers. Or :
- le garde-fou `requires_consent()` ne couvre **que** les appels LLM ;
- le **mode confidentiel ne bloque pas cet envoi** — un utilisateur qui active « Aucune action IA n'envoie de texte en ligne » voit malgré tout son micro transiter par Google ;
- `views/dialogs/help_dialog.py:56` et `voice_dialog.py:26` l'annoncent comme « Dictée Google » sans plus d'explication.

**Recommandation :** supprimer purement `recognize_google` et ne conserver que la dictée Windows native (`trigger_windows_dictation`, déjà implémentée et sans réseau). C'est un gain net : moins de dépendances, moins de poids, zéro exposition.

### 3.2 — Aucune politique de confidentialité *(bloquant)*

L'application transmet du contenu utilisateur à OpenAI, Anthropic et Google. Même sans compte ni serveur à vous, le RGPD impose une information claire. Il faut un document accessible depuis l'app **et** depuis la page de téléchargement, disant : quelles données, vers qui, quand, combien de temps, comment les effacer, qui contacter.

### 3.3 — Le dialogue de consentement est trop vague

Il demande un accord sans énumérer ce qui part. Il devrait nommer : le texte sélectionné (ou le document entier selon l'action), le fournisseur concerné, un lien vers **sa** politique de rétention, et le fait que l'accord vaut pour la suite.

### 3.4 — Le consentement est irrévocable

`cloud_consent` passe à `True` (`ai_setup_dialog.py:630`) et **aucun chemin de l'interface ne le remet à `False`**. Le RGPD exige que retirer son consentement soit aussi simple que le donner. Ajoutez un interrupteur dans les options IA.

### 3.5 — `session.json` stocke le contenu des documents en clair

`~/.glyph/session.json` contient le texte intégral des documents non enregistrés ou modifiés, plus `recent_files` (chemins complets). C'est un choix défendable, mais il doit être documenté dans la politique de confidentialité, et accompagné d'un bouton **« Effacer mes données locales »** dans les options.

### 3.6 — La désinstallation supprime les données sans demander *(risque de perte de données)*

`installer/setup.iss:87` supprime `%USERPROFILE%\.glyph` en silence. Cela emporte les **documents non enregistrés** en plus des réglages. Il faut une case à cocher explicite, décochée par défaut.

---

## 4. Bloquants de distribution

### 4.1 — Rien n'est signé *(bloquant n°1 pour l'adoption)*

`Glyph.spec:87` : `codesign_identity=None`. L'installeur ne l'est pas davantage. Résultat : **chaque** téléchargeur verra « Windows a protégé votre PC — Éditeur inconnu », et la majorité abandonnera. C'est, de très loin, l'obstacle le plus coûteux à l'adoption.

Comptez un certificat de signature de code OV (~200–400 €/an ; depuis 2023 la clé doit résider sur un HSM ou un service cloud type Azure Trusted Signing, ~100 $/an). La réputation SmartScreen se construit ensuite sur quelques centaines d'installations.

### 4.2 — Aucun mécanisme de mise à jour *(bloquant)*

Ni vérification de version, ni updater. Une fois la v1.0 chez des inconnus, **aucun correctif ne peut les atteindre**. Le minimum viable : un `version.json` sur une URL stable, vérifié au démarrage (de façon non bloquante et désactivable), qui affiche une notification et ouvre la page de téléchargement.

### 4.3 — Aucun log, aucune remontée de crash *(bloquant pour le support)*

`import logging` n'apparaît **nulle part** dans le projet, et il n'y a ni `sys.excepthook` ni `threading.excepthook`. Une exception non rattrapée donne une fenêtre morte et zéro information exploitable. Un utilisateur qui écrit « ça plante » sera impossible à aider.

Minimum : un log rotatif dans `~/.glyph/logs/`, un `excepthook` global qui affiche un dialogue « Une erreur est survenue » avec le chemin du log et un bouton copier. Notez que 35 blocs `except Exception` avalent actuellement des erreurs sans laisser de trace.

### 4.4 — Le build n'est pas reproductible *(bloquant)*

`Glyph.spec` est **ignoré par Git** : `.gitignore:34` contient `*.spec`, et `git ls-files` confirme que le fichier n'est pas suivi. Un clone frais du dépôt ne peut pas construire l'application — alors que `build.bat` en dépend directement.

```bash
git check-ignore -v Glyph.spec
```

Correctif : ajouter `!Glyph.spec` après la règle `*.spec`, puis `git add -f Glyph.spec`.

### 4.5 — Numéros de version incohérents

Quatre sources, deux valeurs différentes :

| Fichier | Version |
|---|---|
| `pyproject.toml:6` | **0.12** |
| `core/constants.py:11` | 0.13.2 |
| `installer/setup.iss:8` | 0.13.2 |
| `build.bat` | 0.13.2 |

Une seule source de vérité (`constants.py`), lue par les autres au build.

### 4.6 — Métadonnées de l'éditeur fictives

`installer/setup.iss:21` : `AppPublisherURL=https://github.com/arnaud/glyph` — cette URL n'existe pas. `AppPublisher=Arnaud` n'est pas un nom d'entité identifiable. Les propriétés du fichier .exe et l'entrée « Programmes et fonctionnalités » afficheront ces valeurs à tous les utilisateurs.

### 4.7 — Dépendances non épinglées

`requirements.txt` déclare `requests` sans version et `flet>=0.84.0`. Un build fait dans six mois ne produira pas le même logiciel. Épinglez les versions exactes et conservez un lockfile.

### 4.8 — Pas d'intégration continue

Les 326 tests ne s'exécutent que sur votre machine. Une GitHub Action Windows qui lance `pytest` sur chaque push est une heure de travail et évite de publier une régression.

### 4.9 — Pas de README, pas de CHANGELOG

Le dépôt n'a aucun `README.md`. Aucune note de version n'existe pour les utilisateurs.

---

## 5. Manques produit

- **Pas d'internationalisation.** Interface, prompts IA (`core/ai_prompts.py`), messages d'erreur, dictée : tout est en français, souvent codé en dur. L'installeur propose l'anglais, mais pas l'application — c'est incohérent. Décision à prendre : assumer un produit francophone, ou extraire les chaînes maintenant (le coût croît vite).
- **Coûts affichés en euros, tarifs saisis en dollars.** `models/llm/registry.py` stocke des `price_hint` qui sont les tarifs publics des fournisseurs, libellés en **USD** par million de jetons ; `manager.py:393` les affiche avec le symbole **€**. L'écart est d'environ 8 %, et affiché comme un prix. À corriger ou à afficher en `$`.
- **Pas d'onboarding.** Premier lancement sans visite guidée, sans explication du mode confidentiel, sans mise en avant du fonctionnement 100 % local possible — qui est pourtant votre meilleur argument face à Notepad++ ou VS Code.
- **Pas de canal de support.** Aucune adresse de contact, aucun lien de signalement de bug dans l'application.
- **Accessibilité non vérifiée.** Contrastes des thèmes non mesurés, comportement avec lecteur d'écran inconnu. La couverture clavier, en revanche, semble bonne.
- **Windows uniquement, de fait.** DPAPI, Win+H, zone de notification, associations de fichiers. C'est cohérent avec `MinVersion=10.0.17763`, mais à annoncer clairement (le code `credentials.py` prévoit un repli non chiffré ailleurs : ne publiez pas de build Linux/macOS en l'état).

---

## 6. Plan d'action

### Phase 1 — Bloquants absolus (~1 semaine)

| # | Action | Effort |
|---|---|---|
| 1 | Retirer `recognize_google`, garder la dictée Windows native | 1 h |
| 2 | Choisir la licence, écrire `LICENSE.txt`, l'activer dans `setup.iss` | 0,5 j |
| 3 | Régler la question des icônes (licence, attribution ou remplacement) | 0,5–2 j |
| 4 | `TIERS.txt` + entrée « Mentions légales » dans les Crédits | 0,5 j |
| 5 | Politique de confidentialité + consentement détaillé + révocation | 1 j |
| 6 | Logs + `sys.excepthook` + dialogue d'erreur | 0,5 j |
| 7 | Versionner `Glyph.spec`, unifier les numéros de version | 1 h |
| 8 | Désinstallation : demander avant d'effacer `~/.glyph` | 30 min |

### Phase 2 — Avant diffusion large (~1 semaine)

| # | Action | Effort |
|---|---|---|
| 9 | Certificat de signature de code, signer .exe et installeur | 1 j + délai d'émission |
| 10 | Vérification de mise à jour au démarrage | 1 j |
| 11 | Recherche d'antériorité sur « Glyph » | 2 h |
| 12 | README, CHANGELOG, page de téléchargement, contact support | 1 j |
| 13 | CI GitHub Actions sur Windows | 2 h |
| 14 | Épingler les dépendances | 1 h |
| 15 | Corriger l'affichage € / $ | 30 min |

### Phase 3 — Qualité (à planifier)

Internationalisation · onboarding premier lancement · audit d'accessibilité · télémétrie de crash avec opt-in.

---

## 7. Verdict

Le **produit** est prêt : l'architecture est propre, les tests passent, la gestion des secrets et du consentement IA est meilleure que celle de beaucoup de logiciels commerciaux.

Ce qui manque est **l'enveloppe de distribution** : licence, attributions, politique de confidentialité, signature, mises à jour, journalisation. Ce sont des tâches sans difficulté technique, mais aucune n'est optionnelle pour du grand public.

Les trois urgences, par ordre de risque :

1. **La dictée Google** — envoi de micro non consenti, sur une clé de démonstration. Un correctif d'une heure.
2. **Les icônes** — le seul risque de mise en demeure réelle.
3. **La signature de code** — sans elle, l'écran SmartScreen fera fuir la majorité des téléchargeurs, quelle que soit la qualité du reste.
