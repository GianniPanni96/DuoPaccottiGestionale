import json
from pathlib import Path

from Utils.App_paths import get_runtime_paths

from ConfigManagers.defaults import clone_default_config
from ConfigManagers.type_utils import merge_with_defaults


class BaseJsonConfigManager:
    """Base per i manager di file JSON: load/save con merge sui default.

    Le sottoclassi impostano ``file_name`` e ``default_data`` (o fanno
    override di ``build_default_data``)."""

    file_name = ""
    default_data = {}

    def __init__(self):
        runtime_paths = get_runtime_paths()
        self.storage_root = runtime_paths.storage_root
        self.file_path = self.storage_root / self.file_name

    def build_default_data(self):
        return clone_default_config(self.default_data)

    def ensure_exists(self):
        if not self.file_path.exists():
            self.save(self.build_default_data())

    def load(self):
        self.ensure_exists()
        with open(self.file_path, "r", encoding="utf-8") as file:
            data = json.load(file)
        return merge_with_defaults(data, self.build_default_data())

    def save(self, data):
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        normalized = merge_with_defaults(data, self.build_default_data())
        with open(self.file_path, "w", encoding="utf-8") as file:
            json.dump(normalized, file, indent=4, ensure_ascii=False)

    def exists(self):
        return self.file_path.exists()

    def path(self) -> Path:
        return self.file_path
