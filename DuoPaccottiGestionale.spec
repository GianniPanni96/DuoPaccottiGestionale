# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — build single-file (.exe) di DuoPaccottiGestionale.

Build (dalla root del progetto, con il venv attivo):

    pyinstaller DuoPaccottiGestionale.spec --noconfirm --clean

Output: dist/DuoPaccottiGestionale.exe (eseguibile unico, GUI).

Note runtime:
- DB e file di config NON sono inclusi nell'exe: vengono creati al primo
  avvio in %LOCALAPPDATA%\\DuoPaccottiGestionale (vedi Utils/App_paths.py).
  Si possono reindirizzare con la env var DUOPACCOTTI_DATA_PATH.
- App senza risorse proprie (palette programmatica, config generata da
  ConfigManagers/defaults.py): l'unico bundling necessario riguarda le
  dipendenze di terze parti (matplotlib, pdfplumber/pdfminer/pypdfium2,
  pycryptodome).
"""

from PyInstaller.utils.hooks import collect_all

block_cipher = None

datas = []
binaries = []
hiddenimports = [
    # matplotlib seleziona il backend a runtime: lo esplicitiamo (Qt/PySide6).
    "matplotlib.backends.backend_qtagg",
    "matplotlib.backends.backend_qt",
]

# Pacchetti con data files / librerie native da raccogliere esplicitamente:
# - pdfminer: tabelle CMap (.pickle) usate dal parsing PDF;
# - pypdfium2: libreria nativa (pdfium) usata da pdfplumber;
# - pdfplumber: metadati del pacchetto;
# - Crypto (pycryptodome): moduli di estensione nativi.
for _pkg in ("pdfplumber", "pdfminer", "pypdfium2", "Crypto"):
    _datas, _binaries, _hidden = collect_all(_pkg)
    datas += _datas
    binaries += _binaries
    hiddenimports += _hidden


a = Analysis(
    ["MainQT.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Altri binding Qt e toolkit GUI non usati: evitano conflitti e peso.
        "PyQt5",
        "PyQt6",
        "PySide2",
        "tkinter",
        "matplotlib.backends.backend_tkagg",
        # Strumenti di sviluppo non necessari a runtime.
        "pytest",
        "IPython",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="DuoPaccottiGestionale",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,           # app GUI: nessuna console
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon="path/to/app.ico",  # nessuna icona disponibile nel repo
)
