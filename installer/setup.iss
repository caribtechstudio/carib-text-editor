; ============================================================
;  Glyph — Script d'installation Inno Setup
;  Générer l'installeur : ouvrir ce fichier dans Inno Setup
;  puis Build > Compile (ou Ctrl+F9)
; ============================================================

#define AppName        "Glyph"
#define AppVersion     "0.13.1"
#define AppPublisher   "Arnaud"
#define AppExeName     "Glyph.exe"
; Dossier produit par PyInstaller en mode dossier (voir Glyph.spec).
; Le mode dossier evite la decompression de ~145 Mo dans %TEMP% a chaque
; lancement ; l'utilisateur ne voit qu'un raccourci, comme avant.
#define BuildDir       "..\dist\Glyph"

[Setup]
AppId={{8F3A2C1E-4B7D-4F9A-B2E6-1D5C8A0F3E72}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL=https://github.com/arnaud/glyph
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes
; Icône de l'installeur (générée dans le dossier Output)
SetupIconFile=..\ressource\icon\icon.ico
; Dossier de sortie de l'installeur
OutputDir=Output
OutputBaseFilename=Glyph_v{#AppVersion}_Setup
Compression=lzma2/ultra64
SolidCompression=yes
; Métadonnées Windows
VersionInfoVersion={#AppVersion}.0.0
VersionInfoProductName={#AppName}
VersionInfoCompany={#AppPublisher}
VersionInfoDescription=Éditeur de texte moderne
; Demander les droits admin pour écrire dans Program Files
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
; Minimum Windows 10
MinVersion=10.0.17763
WizardStyle=modern
WizardSizePercent=120
; Licence / image facultatives — décommenter si tu les ajoutes
; LicenseFile=..\LICENSE.txt
; WizardImageFile=wizard_banner.bmp

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon";    Description: "Créer un raccourci sur le Bureau";     GroupDescription: "Raccourcis :"; Flags: unchecked
Name: "quicklaunchicon"; Description: "Épingler dans la barre des tâches";   GroupDescription: "Raccourcis :"; Flags: unchecked; OnlyBelowVersion: 6.1
Name: "fileassoc";      Description: "Associer les fichiers .txt, .md et .log à Glyph"; GroupDescription: "Association de fichiers :";

[Files]
; Tous les fichiers produits par flet build windows
; IMPORTANT : tout le dossier doit etre embarque, pas seulement l'exe.
Source: "{#BuildDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Raccourci Menu Démarrer
Name: "{group}\{#AppName}";            Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\{#AppExeName}"
Name: "{group}\Désinstaller {#AppName}"; Filename: "{uninstallexe}"
; Bureau (optionnel, selon tâche)
Name: "{autodesktop}\{#AppName}";      Filename: "{app}\{#AppExeName}"; Tasks: desktopicon; IconFilename: "{app}\{#AppExeName}"

[Registry]
; Association .txt → Glyph (seulement si la tâche est cochée)
Root: HKCU; Subkey: "Software\Classes\.txt\OpenWithProgids"; ValueType: string; ValueName: "Glyph.txt"; ValueData: ""; Flags: uninsdeletevalue; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\Glyph.txt"; ValueType: string; ValueName: ""; ValueData: "Fichier texte Glyph"; Flags: uninsdeletekey; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\Glyph.txt\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#AppExeName},0"; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\Glyph.txt\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExeName}"" ""%1"""; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\.md\OpenWithProgids"; ValueType: string; ValueName: "Glyph.txt"; ValueData: ""; Flags: uninsdeletevalue; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\.log\OpenWithProgids"; ValueType: string; ValueName: "Glyph.txt"; ValueData: ""; Flags: uninsdeletevalue; Tasks: fileassoc
; Notifier Windows du changement d'association
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\.txt"; ValueType: string; ValueName: "Progid"; ValueData: "Glyph.txt"; Flags: uninsdeletevalue; Tasks: fileassoc

[Run]
; Lancer Glyph à la fin de l'installation (optionnel)
Filename: "{app}\{#AppExeName}"; Description: "Lancer {#AppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Nettoyer les fichiers créés par l'app (session, logs)
; Session, configuration IA et cles API chiffrees vivent dans %USERPROFILE%\.glyph
Type: filesandordirs; Name: "{%USERPROFILE}\.glyph"
