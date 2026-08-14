@echo off
chcp 65001 > nul
setlocal

echo ============================================
echo   Glyph v0.13.2 - Build Windows (mode dossier)
echo ============================================
echo.

where pyinstaller >nul 2>&1
if errorlevel 1 (
    echo [ERREUR] pyinstaller n'est pas dans le PATH.
    echo          Lance : pip install pyinstaller
    pause
    exit /b 1
)

echo [1/5] Suppression de l'ancien build...
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build

echo [2/5] Compilation (Glyph.spec, mode dossier)...
REM Le mode dossier evite la decompression de ~145 Mo dans %%TEMP%% a chaque
REM lancement, qui coutait 3 a 6 secondes de demarrage.
pyinstaller Glyph.spec --noconfirm
if errorlevel 1 (
    echo.
    echo [ERREUR] Le build a echoue. Consulte les messages ci-dessus.
    pause
    exit /b 1
)

echo [3/5] Verification du resultat...
if not exist "dist\Glyph\Glyph.exe" (
    echo [ERREUR] dist\Glyph\Glyph.exe est introuvable.
    pause
    exit /b 1
)

echo [4/5] Francisation des textes du client Flet...
REM « Working... » est compile dans l'instantane Dart de Flet : il ne peut
REM etre change qu'ici, apres la copie du client dans dist\.
python tools\patch_flet_strings.py "dist\Glyph"
if errorlevel 1 (
    echo [AVERTISSEMENT] Le texte de chargement n'a pas pu etre remplace.
    echo                 Le build reste utilisable.
)

echo [5/5] Mesure du temps de demarrage...
powershell -NoProfile -Command ^
  "$sw=[Diagnostics.Stopwatch]::StartNew();" ^
  "$p=Start-Process 'dist\Glyph\Glyph.exe' -PassThru;" ^
  "$p.WaitForInputIdle(20000) | Out-Null;" ^
  "$sw.Stop();" ^
  "Write-Host ('    Premiere image en {0:N2} s' -f $sw.Elapsed.TotalSeconds);" ^
  "Start-Sleep -Milliseconds 800; $p.CloseMainWindow() | Out-Null"

echo.
echo Build termine !
echo.
echo   Dossier    : dist\Glyph\
echo   Executable : dist\Glyph\Glyph.exe
echo.
echo Pour l'installeur, ouvre installer\setup.iss avec Inno Setup.
echo IMPORTANT : le .iss doit embarquer TOUT le dossier dist\Glyph\,
echo             pas seulement Glyph.exe.
echo.
pause
