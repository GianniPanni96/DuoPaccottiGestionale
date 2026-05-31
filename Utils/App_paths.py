"""Risoluzione centralizzata dei percorsi runtime dell'app.

Ispirato a ``willowGestionale2.0/Utils/App_paths.py`` ma semplificato:
non gestiamo libri contabili ne' backup. In sviluppo (non-frozen) tutti
i dati vivono nella root del progetto; in produzione (PyInstaller) sotto
la cartella dati utente della piattaforma.
"""

from __future__ import annotations

import os
import sys
import threading
from dataclasses import dataclass
from pathlib import Path


APP_NAME = "DuoPaccottiGestionale"
DATA_PATH_ENV_VAR = "DUOPACCOTTI_DATA_PATH"


@dataclass(frozen=True)
class RuntimePaths:
    storage_root: Path        # root scrivibile: db + file di config
    install_root: Path        # root di installazione (exe, Data/)
    db_file: Path
    catalogs_file: Path
    app_settings_file: Path
    gui_preferences_file: Path
    category_hints_file: Path
    data_dir: Path
    images_dir: Path


def is_macos() -> bool:
    return sys.platform == "darwin"


def is_windows() -> bool:
    return os.name == "nt"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _default_data_root() -> Path:
    """Default per-piattaforma della cartella dati scrivibile."""
    if is_macos():
        return Path.home() / "Library" / "Application Support" / APP_NAME
    if is_windows():
        local_appdata = os.environ.get("LOCALAPPDATA")
        if local_appdata:
            return Path(local_appdata) / APP_NAME
        return Path.home() / "AppData" / "Local" / APP_NAME
    return Path.home() / f".{APP_NAME}"


def _resolve_storage_root() -> Path:
    """In dev (non-frozen) usa la root del progetto; in produzione la
    cartella dati di piattaforma (override con la env var)."""
    env_value = os.environ.get(DATA_PATH_ENV_VAR)
    if env_value:
        return Path(env_value).expanduser()
    if not is_frozen():
        return _project_root()
    return _default_data_root()


def _resolve_install_root() -> Path:
    if not is_frozen():
        return _project_root()
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(sys.executable).parent


_runtime_paths_cache: RuntimePaths | None = None
_runtime_paths_lock = threading.Lock()


def initialize_runtime_paths() -> RuntimePaths:
    global _runtime_paths_cache
    with _runtime_paths_lock:
        if _runtime_paths_cache is not None:
            return _runtime_paths_cache

        storage_root = _resolve_storage_root().resolve()
        storage_root.mkdir(parents=True, exist_ok=True)

        install_root = _resolve_install_root().resolve()
        data_dir = install_root / "Data"
        images_dir = data_dir / "images"

        _runtime_paths_cache = RuntimePaths(
            storage_root=storage_root,
            install_root=install_root,
            db_file=storage_root / "duopaccotti.db",
            catalogs_file=storage_root / "catalogs.json",
            app_settings_file=storage_root / "app_settings.json",
            gui_preferences_file=storage_root / "gui_preferences.json",
            category_hints_file=storage_root / "category_hints.json",
            data_dir=data_dir,
            images_dir=images_dir,
        )
        return _runtime_paths_cache


def get_runtime_paths() -> RuntimePaths:
    return initialize_runtime_paths()
