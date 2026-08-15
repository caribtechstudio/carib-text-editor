# -*- mode: python ; coding: utf-8 -*-
"""
Spécification PyInstaller pour Carib.

Deux choix décisifs pour le temps de démarrage :

1. **COLLECT au lieu de onefile.** Un exécutable « onefile » de 145 Mo se
   décompresse dans %TEMP% à *chaque* lancement — 3 à 6 secondes de pure
   entrée/sortie disque avant même que Python ne démarre. En mode dossier,
   cette extraction disparaît totalement. L'installeur Inno Setup masque le
   dossier à l'utilisateur, qui ne voit qu'un raccourci.

2. **Exclusions.** Chaque module écarté, c'est du poids en moins à charger.
   `pyautogui` ne sert qu'à la dictée Windows et tire tout PIL ; il est
   importé à la demande dans voice_manager, donc il ne doit pas être
   embarqué en dur.

Construire :  pyinstaller Carib.spec --noconfirm
"""

block_cipher = None

EXCLUDES = [
    # Interfaces graphiques concurrentes
    'tkinter', 'PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'wx',
    # Calcul scientifique / données — jamais utilisés par Carib
    'numpy', 'pandas', 'scipy', 'matplotlib', 'IPython', 'jupyter',
    'notebook', 'sympy', 'sklearn',
    # Outils de développement
    'pytest', 'unittest', 'doctest', 'pydoc', 'test',
    'setuptools', 'pip', 'distutils',
    # Automatisation d'interface : remplacée par un appel ctypes direct
    # dans voice_manager. Elle entraînait Pillow et Xlib — ~30 Mo.
    'pyautogui', 'PIL', 'Pillow', 'pyscreeze', 'pytweening', 'pygetwindow',
    'mouseinfo', 'pymsgbox', 'Xlib',
    # Reconnaissance vocale : entièrement retirée en 0.14.0. La dictée passe
    # par celle de Windows (Win+H), donc par un simple appel ctypes. Ces
    # modules ne doivent plus entrer dans le paquet, ni directement ni par
    # une dépendance transitive.
    'speech_recognition', 'pocketsphinx', 'torch', 'whisper', 'vosk',
    'soundfile', 'numpy.core', 'pyaudio',
    # Clients Google Cloud, qui n'étaient tirés que par speech_recognition.
    'grpc', 'google.cloud', 'google.protobuf', 'google.auth',
]

a = Analysis(
    ['carib.py'],
    pathex=[],
    binaries=[],
    # Les documents légaux voyagent avec l'application : l'EULA et les
    # mentions des tiers doivent être consultables hors ligne, et la
    # politique de confidentialité est ouverte depuis Options.
    datas=[
        ('ressource', 'ressource'),
        ('LICENSE.txt', '.'),
        ('EULA.txt', '.'),
        ('TIERS.txt', '.'),
        ('CONFIDENTIALITE.md', '.'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
    noarchive=False,
    optimize=1,          # retire les assertions et les docstrings du bytecode
)

# --- Élagage des données inutiles ------------------------------------------
# Les données de `speech_recognition` (modèle acoustique PocketSphinx, ~40 Mo,
# et binaires `flac`) restent filtrées : la dépendance a disparu en 0.14.0,
# mais un environnement de build où elle traîne encore ne doit pas la
# réintroduire dans le paquet.
#
# `ressource/icon/_original` conserve les icônes avant épaississement
# (`tools/thicken_icons.py`) : indispensable au dépôt pour pouvoir revenir en
# arrière, parfaitement inutile dans l'exécutable livré.
_DATA_PRUNE = ('pocketsphinx-data', 'flac-linux', 'flac-mac',
               'ressource/icon/_original')

a.datas = [entry for entry in a.datas
           if not any(token in entry[0].replace('\\', '/') for token in _DATA_PRUNE)]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,          # ← mode dossier : rien n'est embarqué dans l'exe
    name='Carib',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,                      # UPX ralentit le démarrage (décompression en RAM)
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['ressource\\icon\\icon.ico'],
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='Carib',
)
