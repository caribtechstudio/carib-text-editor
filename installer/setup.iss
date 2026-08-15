; ============================================================
;  Carib — Script d'installation Inno Setup
;  Générer l'installeur : ouvrir ce fichier dans Inno Setup
;  puis Build > Compile (ou Ctrl+F9)
; ============================================================

; Nom affiche : fenetre d'installation, menu Demarrer, « Programmes et
; fonctionnalites ». « Text Editor » est descriptif ; le signe distinctif,
; c'est « Carib » seul, qui sert au dossier et aux noms de fichiers.
#define AppName        "Carib Text Editor"
#define AppShortName   "Carib"
#define AppVersion     "0.14.1"
#define AppPublisher   "Arnaud"
#define AppExeName     "Carib.exe"
; Dossier produit par PyInstaller en mode dossier (voir Carib.spec).
; Le mode dossier evite la decompression de ~145 Mo dans %TEMP% a chaque
; lancement ; l'utilisateur ne voit qu'un raccourci, comme avant.
#define BuildDir       "..\dist\Carib"

[Setup]
AppId={{8F3A2C1E-4B7D-4F9A-B2E6-1D5C8A0F3E72}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL=https://github.com/caribtechstudio/carib-text-editor
AppSupportURL=https://github.com/caribtechstudio/carib-text-editor/issues
AppUpdatesURL=https://github.com/caribtechstudio/carib-text-editor/releases
DefaultDirName={autopf}\{#AppShortName}
DefaultGroupName={#AppName}
AllowNoIcons=yes
; Icône de l'installeur (générée dans le dossier Output)
SetupIconFile=..\ressource\icon\icon.ico
; Dossier de sortie de l'installeur
OutputDir=Output
OutputBaseFilename={#AppShortName}_v{#AppVersion}_Setup
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
; Contrat de licence utilisateur final — présenté et à accepter avant
; l'installation. C'est lui qui rend la distribution régulière : sans écran
; d'acceptation, aucune des clauses de garantie et de responsabilité n'est
; opposable à l'utilisateur.
LicenseFile=..\EULA.txt
; Fermer proprement Carib s'il tourne, au lieu d'échouer sur un fichier
; verrouillé — indispensable pour la mise à jour depuis l'application.
CloseApplications=yes
RestartApplications=no
; WizardImageFile=wizard_banner.bmp

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon";    Description: "Créer un raccourci sur le Bureau";     GroupDescription: "Raccourcis :"; Flags: unchecked
Name: "fileassoc";      Description: "Associer les fichiers .txt, .md et .log à Carib"; GroupDescription: "Association de fichiers :";

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
; Association .txt → Carib (seulement si la tâche est cochée)
Root: HKCU; Subkey: "Software\Classes\.txt\OpenWithProgids"; ValueType: string; ValueName: "Carib.txt"; ValueData: ""; Flags: uninsdeletevalue; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\Carib.txt"; ValueType: string; ValueName: ""; ValueData: "Fichier texte Carib"; Flags: uninsdeletekey; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\Carib.txt\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#AppExeName},0"; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\Carib.txt\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExeName}"" ""%1"""; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\.md\OpenWithProgids"; ValueType: string; ValueName: "Carib.txt"; ValueData: ""; Flags: uninsdeletevalue; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\.log\OpenWithProgids"; ValueType: string; ValueName: "Carib.txt"; ValueData: ""; Flags: uninsdeletevalue; Tasks: fileassoc
; Notifier Windows du changement d'association
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\.txt"; ValueType: string; ValueName: "Progid"; ValueData: "Carib.txt"; Flags: uninsdeletevalue; Tasks: fileassoc

[Run]
; Lancer Carib à la fin de l'installation (optionnel)
Filename: "{app}\{#AppExeName}"; Description: "Lancer {#AppName}"; Flags: nowait postinstall skipifsilent

; ============================================================
;  Désinstallation — les données de l'utilisateur ne partent
;  JAMAIS sans qu'il l'ait demandé.
;
;  L'ancienne section [UninstallDelete] supprimait en silence
;  %USERPROFILE%\.carib, qui contient la session ET le contenu
;  des documents jamais enregistrés. Désinstaller pour
;  réinstaller effaçait donc du travail, sans le moindre
;  avertissement. On demande désormais, et la réponse par
;  défaut est de tout conserver.
; ============================================================
[Code]
function CaribDataDir(): String;
begin
  Result := ExpandConstant('{%USERPROFILE}') + '\.carib';
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Dir: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    Dir := CaribDataDir();
    if DirExists(Dir) then
    begin
      if MsgBox('Supprimer aussi vos données Carib ?' + #13#10 + #13#10 +
                'Cela effacera votre session, vos fichiers récents, vos ' +
                'réglages, vos clés API enregistrées et le contenu des ' +
                'documents que vous n''avez jamais enregistrés.' + #13#10 + #13#10 +
                'Vos fichiers enregistrés sur le disque ne sont pas ' +
                'concernés.' + #13#10 + #13#10 +
                'Dossier : ' + Dir + #13#10 + #13#10 +
                'Répondez Non pour les conserver (recommandé si vous ' +
                'comptez réinstaller Carib).',
                mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
      begin
        DelTree(Dir, True, True, True);
      end;
    end;
  end;
end;
