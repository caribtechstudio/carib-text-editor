@echo off
chcp 65001 > nul
setlocal

echo ============================================
echo   Carib - Build Windows (mode dossier)
echo ============================================
echo.

where pyinstaller >nul 2>&1
if errorlevel 1 (
    echo [ERREUR] pyinstaller n'est pas dans le PATH.
    echo          Lance : pip install -r requirements-dev.txt
    pause
    exit /b 1
)

echo [1/6] Propagation du numero de version...
REM core\constants.py est la seule source de verite : ce script le recopie
REM dans pyproject.toml et installer\setup.iss. Sans lui, l'installeur
REM repartait avec un numero perime.
python tools\sync_version.py
if errorlevel 1 (
    echo [ERREUR] La synchronisation de version a echoue.
    pause
    exit /b 1
)

echo [2/6] Verification des documents legaux...
REM Carib.spec les embarque : s'ils manquent, le build echoue plus loin avec
REM un message obscur. Autant s'en apercevoir tout de suite.
for %%F in (LICENSE.txt EULA.txt TIERS.txt CONFIDENTIALITE.md) do (
    if not exist "%%F" (
        echo [ERREUR] %%F est introuvable a la racine du projet.
        pause
        exit /b 1
    )
)

echo [3/6] Suppression de l'ancien build...
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build

echo [4/6] Compilation (Carib.spec, mode dossier)...
REM Le mode dossier evite la decompression de ~145 Mo dans %%TEMP%% a chaque
REM lancement, qui coutait 3 a 6 secondes de demarrage.
pyinstaller Carib.spec --noconfirm
if errorlevel 1 (
    echo.
    echo [ERREUR] Le build a echoue. Consulte les messages ci-dessus.
    pause
    exit /b 1
)

echo [5/6] Verification du resultat...
if not exist "dist\Carib\Carib.exe" (
    echo [ERREUR] dist\Carib\Carib.exe est introuvable.
    pause
    exit /b 1
)

echo      Francisation des textes du client Flet...
REM « Working... » est compile dans l'instantane Dart de Flet : il ne peut
REM etre change qu'ici, apres la copie du client dans dist\.
python tools\patch_flet_strings.py "dist\Carib"
if errorlevel 1 (
    echo [AVERTISSEMENT] Le texte de chargement n'a pas pu etre remplace.
    echo                 Le build reste utilisable.
)

echo [6/6] Mesure du temps de demarrage...
powershell -NoProfile -Command ^
  "$sw=[Diagnostics.Stopwatch]::StartNew();" ^
  "$p=Start-Process 'dist\Carib\Carib.exe' -PassThru;" ^
  "$p.WaitForInputIdle(20000) | Out-Null;" ^
  "$sw.Stop();" ^
  "Write-Host ('    Premiere image en {0:N2} s' -f $sw.Elapsed.TotalSeconds);" ^
  "Start-Sleep -Milliseconds 800; $p.CloseMainWindow() | Out-Null"

echo.
echo Build termine !
echo.
echo   Dossier    : dist\Carib\
echo   Executable : dist\Carib\Carib.exe
echo.
echo Etapes suivantes pour publier :
echo.
echo   1. Ouvre installer\setup.iss avec Inno Setup, puis Ctrl+F9.
echo      (le .iss embarque TOUT le dossier dist\Carib\, pas seulement l'exe)
echo   2. Signe l'installeur produit dans installer\Output\.
echo   3. Lance release.bat : il calcule SHA256SUMS.txt et le verifie.
echo      IMPORTANT : apres la signature, jamais avant.
echo   4. Cree la release GitHub, en attachant l'installeur ET
echo      SHA256SUMS.txt. Sans ce dernier, l'updater ne peut pas
echo      verifier l'integrite du telechargement.
echo.
echo   Voir RELEASE.md pour la procedure detaillee.
echo.
pause
