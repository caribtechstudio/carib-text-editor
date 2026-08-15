# Publier une version de Carib

Procédure complète, du numéro de version à la release GitHub que l'updater
saura lire.

> **Le point critique** : l'updater intégré vérifie l'empreinte SHA-256 du
> fichier téléchargé avant de l'exécuter. Cette empreinte vient d'un fichier
> `SHA256SUMS.txt` attaché à la release. **Sans lui, la vérification
> d'intégrité ne peut pas avoir lieu** — l'installation reste possible, mais
> vous perdez le garde-fou principal. Ne sautez pas l'étape 5.

---

## 1. Préparer la version

Modifiez `APP_VERSION` dans `core/constants.py` — et **nulle part ailleurs** :

```python
APP_VERSION = "0.15.0"
```

Complétez `CHANGELOG.md`. Ce texte servira de corps à la release GitHub.

## 2. Vérifier

```bash
python -m pytest tests/ -q
```

La suite doit être entièrement verte. La CI le vérifie aussi, mais autant le
savoir avant de construire.

## 3. Construire

```bash
build.bat
```

Le script propage le numéro de version, contrôle la présence des documents
légaux, compile avec PyInstaller, francise les textes du client Flet et
mesure le temps de démarrage.

Ouvrez ensuite `installer/setup.iss` dans Inno Setup et compilez (`Ctrl+F9`).
L'installeur apparaît dans `installer/Output/`.

## 4. Signer

```bash
signtool sign /tr http://timestamp.digicert.com /td sha256 /fd sha256 ^
  /a "installer\Output\Carib_v0.15.0_Setup.exe"
```

Signez **l'installeur** et, idéalement, `dist\Carib\Carib.exe` avant de
construire l'installeur.

> Sans signature, chaque téléchargeur verra l'écran SmartScreen « Windows a
> protégé votre PC — Éditeur inconnu », et la majorité renoncera. C'est le
> premier frein à l'adoption, avant toute considération de fonctionnalité.
>
> Depuis 2023, la clé privée doit résider sur un HSM ou un service cloud
> (Azure Trusted Signing, ~100 $/an ; certificat OV classique, 200–400 €/an).
> La réputation SmartScreen se construit ensuite sur quelques centaines
> d'installations.

Vérifiez :

```bash
signtool verify /pa /v "installer\Output\Carib_v0.15.0_Setup.exe"
```

## 5. Générer `SHA256SUMS.txt`

```bash
release.bat
```

C'est tout — le script trouve l'installeur, calcule son empreinte SHA-256,
écrit `installer/Output/SHA256SUMS.txt`, puis **revérifie** ce qu'il vient
d'écrire. Il signale au passage si l'installeur n'est pas signé, et affiche la
commande `gh release create` prête à coller.

**Lancez-le après la signature**, jamais avant : signer modifie le fichier,
donc son empreinte. Une empreinte calculée avant la signature ne correspondra
à rien et l'updater refusera la mise à jour chez tous vos utilisateurs. Le
script détecte ce cas — `release.bat` échoue plutôt que de publier un fichier
incohérent.

Le fichier produit est au format `sha256sum` classique :

```
a3f5...c9  Carib_v0.15.0_Setup.exe
```

L'updater accepte aussi le format avec astérisque (`a3f5...c9 *Carib_...exe`),
celui produit par `Get-FileHash`, et une empreinte isolée si le fichier n'en
contient qu'une.

Pour revérifier plus tard, sans rien réécrire :

```bash
python tools/make_release.py --verify
```

## 6. Publier la release

```bash
gh release create v0.15.0 ^
  "installer\Output\Carib_v0.15.0_Setup.exe" ^
  "SHA256SUMS.txt" ^
  --title "Carib 0.15.0" ^
  --notes-file CHANGELOG_EXTRAIT.md
```

Contraintes que l'updater impose :

| Élément | Règle |
|---|---|
| Étiquette | `v0.15.0` ou `0.15.0` — doit être analysable en numéro de version |
| Statut | **Ni brouillon, ni préversion.** L'updater interroge `/releases/latest`, qui les exclut |
| Installeur | Un actif `.exe` dont le nom contient `Setup` |
| Empreintes | Un actif `SHA256SUMS.txt` |
| Notes | Le corps de la release s'affiche dans le dialogue de mise à jour |

## 7. Vérifier de bout en bout

Depuis une machine où une version **antérieure** est installée :

1. Lancez Carib et attendez la proposition — ou forcez-la par
   *Options ▸ Rechercher une mise à jour*.
2. Vérifiez le numéro de version, la taille et les notes affichés.
3. Cliquez « Mettre à jour maintenant » : le téléchargement doit se terminer
   par « Vérification de l'intégrité », puis proposer l'installation.
4. Confirmez que Carib se ferme, que l'installeur démarre, et que la session
   est rouverte telle quelle après l'installation.

Pour tester un échec d'intégrité, publiez volontairement un `SHA256SUMS.txt`
erroné : la mise à jour doit être **refusée** avec un message explicite, et
le fichier téléchargé supprimé.

---

## En cas de problème

- **La mise à jour n'est jamais proposée** — vérifiez que la release n'est ni
  un brouillon ni une préversion, et que `GITHUB_REPO` dans
  `core/constants.py` désigne le bon dépôt.
- **« L'empreinte ne correspond pas »** — le `SHA256SUMS.txt` publié ne
  correspond pas au binaire attaché. Recalculez après signature : signer
  modifie le fichier, donc son empreinte.
- **« Le fichier ne provient pas de GitHub »** — l'actif est hébergé
  ailleurs. L'updater n'accepte que les domaines GitHub, y compris après
  redirection.
- **Diagnostic utilisateur** : `~/.carib/logs/carib.log` trace chaque étape
  de la vérification et du téléchargement.
