# Carib Text Editor

Éditeur de texte moderne pour Windows, avec assistance par IA — locale ou en
ligne, au choix. Écrit en Python avec [Flet](https://flet.dev).

> **Windows 10 (1809) ou supérieur.** Le stockage chiffré des clés (DPAPI), la
> dictée intégrée et l'association de fichiers reposent sur des API Windows.

---

## Ce que fait Carib

- **Onglets multiples**, session restaurée au lancement, récupération après
  coupure (journal réécrit toutes les 15 s)
- **Écriture atomique** : l'encodage et les fins de ligne d'un fichier sont
  préservés, un enregistrement interrompu ne peut pas le tronquer
- **Recherche et remplacement** : expressions régulières, casse, mot entier
- **Palette de commandes** (`Ctrl+Maj+P`) et barre IA (`Ctrl+K`)
- **IA multi-fournisseurs** : ChatGPT, Claude, Gemini, ou Ollama en local
- **Revue des modifications IA** en diff inline — `Tab` accepte, `Échap` refuse
- **Mode confidentiel** : force le traitement 100 % local, globalement ou pour
  un document précis
- **Autocomplétion** locale, plus prédiction IA optionnelle
- Correction orthographique hors ligne, synthèse vocale, dictée Windows,
  emojis, mode calcul, thèmes clair et sombre

## Confidentialité en bref

Carib n'a **pas de serveur**, ne crée aucun compte, ne collecte rien, ne
mesure rien. Vos documents restent sur votre machine.

L'application ne se connecte à internet que dans trois cas, tous sous votre
contrôle :

1. **Recherche de mise à jour** chez GitHub — désactivable, aucune donnée
   personnelle transmise, et votre accord est demandé au premier lancement.
2. **IA en ligne** — uniquement si vous avez configuré une clé *et* accepté
   l'avertissement. Le consentement est révocable à tout moment.
3. **Ollama** — sur `localhost`, donc sur votre propre ordinateur.

Le détail complet : [CONFIDENTIALITE.md](CONFIDENTIALITE.md), également
accessible dans l'application via *Options ▸ Confidentialité*.

---

## Installation

Téléchargez le dernier installeur depuis la
[page des releases](https://github.com/caribtechstudio/carib-text-editor/releases).

Carib vérifie ensuite lui-même les nouvelles versions et vous propose de les
installer en un clic.

## Développement

```bash
git clone https://github.com/caribtechstudio/carib-text-editor.git
cd carib-text-editor
pip install -r requirements.txt -r requirements-dev.txt
python carib.py
```

### Tests

```bash
python -m pytest tests/ -q
```

### Construire l'exécutable et l'installeur

```bash
build.bat
```

Puis ouvrez `installer/setup.iss` dans [Inno Setup](https://jrsoftware.org/isinfo.php)
et compilez (`Ctrl+F9`). La procédure complète de publication est décrite dans
[RELEASE.md](RELEASE.md).

### Numéro de version

`core/constants.py` (`APP_VERSION`) est la **source de vérité unique**.
`tools/sync_version.py` le propage dans `pyproject.toml` et
`installer/setup.iss` ; `build.bat` l'appelle automatiquement.

### Organisation

| Dossier | Rôle |
|---|---|
| `core/` | Constantes, thème, prompts IA, journalisation |
| `models/` | Logique métier sans interface : documents, fichiers, IA, mise à jour |
| `controllers/` | Orchestration entre modèles et vues |
| `views/` | Construction de l'interface Flet |
| `tests/` | Suite pytest |
| `tools/` | Scripts de build et de maintenance |

---

## Licence

Carib applique deux textes distincts, et c'est volontaire :

- **Le binaire distribué** (l'installeur Windows) est régi par
  [EULA.txt](EULA.txt), présenté et accepté lors de l'installation.
- **Le code source** de ce dépôt est publié sous
  [PolyForm Noncommercial 1.0.0](LICENSE.txt) : lecture, exécution,
  modification et redistribution libres pour tout usage **non commercial**.

Tout usage commercial requiert une licence distincte — écrivez à l'adresse
indiquée ci-dessous.

Les composants tiers embarqués (Flet, Python, Requests, pyspellchecker,
pyttsx3, la police Nunito et les icônes Flaticon) restent soumis à leurs
propres licences. Voir [TIERS.txt](TIERS.txt), également consultable dans
l'application via *Options ▸ Crédits ▸ Mentions légales*.

Icônes par [Flaticon](https://www.flaticon.com/uicons).

## Contact

- Bogues et suggestions : [issues](https://github.com/caribtechstudio/carib-text-editor/issues)
- Autre : `contact@caribtechstudio.com`
