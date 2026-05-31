"""Bootstrap indipendente dalla UI: risolve i percorsi, crea lo schema
del DB se assente, carica/crea i file di config, costruisce l'AppContext.
"""

import Schema
from App_context import AppContext
from ConfigManagers import ConfigManager
from Utils.App_paths import get_runtime_paths


def build_app_context() -> AppContext:
    runtime_paths = get_runtime_paths()

    db_path = str(runtime_paths.db_file)
    Schema.create_schema(db_path)

    config_manager = ConfigManager()
    config_manager.ensure_all_exist()

    print(f"Avvio DuoPaccottiGestionale — DB: {db_path}")

    return AppContext(
        config_manager=config_manager,
        db_path=db_path,
        images_path=str(runtime_paths.images_dir),
    )
