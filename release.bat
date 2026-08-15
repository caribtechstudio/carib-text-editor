@echo off
chcp 65001 > nul
setlocal

REM ============================================================
REM  Carib - Preparation des fichiers a publier
REM
REM  A lancer APRES avoir compile installer\setup.iss avec Inno
REM  Setup, et APRES avoir signe l'installeur produit.
REM
REM  Signer modifie le fichier, donc son empreinte : calculer
REM  avant la signature produirait un SHA256SUMS.txt qui ne
REM  correspond a rien, et l'updater refuserait la mise a jour
REM  chez tous vos utilisateurs.
REM ============================================================

echo ============================================
echo   Carib - Preparation de la release
echo ============================================
echo.

if not exist "installer\Output" (
    echo [ERREUR] installer\Output est introuvable.
    echo          Compilez d'abord installer\setup.iss avec Inno Setup.
    pause
    exit /b 1
)

echo [1/2] Calcul des empreintes SHA-256...
python tools\make_release.py
if errorlevel 1 (
    echo.
    echo [ERREUR] Le calcul des empreintes a echoue.
    pause
    exit /b 1
)

echo.
echo [2/2] Verification croisee...
python tools\make_release.py --verify
if errorlevel 1 (
    echo.
    echo [ERREUR] La verification a echoue.
    pause
    exit /b 1
)

echo.
echo Les fichiers sont prets dans installer\Output\ :
echo   - l'installeur
echo   - SHA256SUMS.txt
echo.
echo Attachez LES DEUX a la release GitHub. Sans SHA256SUMS.txt,
echo Carib ne peut pas verifier l'integrite du telechargement.
echo.
echo Voir RELEASE.md pour la suite.
echo.
pause
