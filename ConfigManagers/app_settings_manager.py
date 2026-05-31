from ConfigManagers.base_json_manager import BaseJsonConfigManager
from ConfigManagers.defaults import APP_SETTINGS_DEFAULT


DEFAULT_COLLECTIVE_NAME = "DuoPaccotti"


class AppSettingsManager(BaseJsonConfigManager):
    """Impostazioni generali + default utente (IVA, metodo, visibilita')."""

    file_name = "app_settings.json"
    default_data = APP_SETTINGS_DEFAULT

    # --- nome del collettivo ---

    def get_collective_name(self) -> str:
        return self._get_value("general", "collective_name", DEFAULT_COLLECTIVE_NAME)

    def set_collective_name(self, name: str):
        cleaned = (name or "").strip() or DEFAULT_COLLECTIVE_NAME
        self._set_value("general", "collective_name", cleaned)

    # --- default utente ---

    def get_default_iva(self) -> str:
        return self._get_value("defaults", "default_iva", "0.22")

    def get_default_payment_method(self) -> str:
        return self._get_value("defaults", "default_payment_method", "CARTA")

    def get_default_visibility(self) -> str:
        return self._get_value("defaults", "default_visibility", "PUBBLICA")

    def set_default(self, key: str, value: str):
        self._set_value("defaults", key, value)

    # --- helpers ---

    def _get_value(self, section: str, key: str, fallback: str) -> str:
        try:
            data = self.load()
        except Exception:
            return fallback
        section_data = data.get(section) if isinstance(data, dict) else None
        if not isinstance(section_data, dict):
            return fallback
        node = section_data.get(key)
        value = node.get("value") if isinstance(node, dict) else node
        if not isinstance(value, str) or not value.strip():
            return fallback
        return value.strip()

    def _set_value(self, section: str, key: str, value: str):
        data = self.load()
        section_data = data.setdefault(section, {})
        node = section_data.get(key)
        if isinstance(node, dict):
            node["value"] = value
        else:
            section_data[key] = {"value": value, "description": ""}
        self.save(data)
