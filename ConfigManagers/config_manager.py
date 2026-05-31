from ConfigManagers.app_settings_manager import AppSettingsManager
from ConfigManagers.catalogs_manager import CatalogsManager
from ConfigManagers.category_hints_manager import CategoryHintsManager
from ConfigManagers.gui_preferences_manager import GuiPreferencesManager


class ConfigManager:
    """Aggregatore dei manager dei file di configurazione JSON."""

    def __init__(self):
        self.app_settings_manager = AppSettingsManager()
        self.catalogs_manager = CatalogsManager()
        self.category_hints_manager = CategoryHintsManager()
        self.gui_preferences_manager = GuiPreferencesManager()

    def ensure_all_exist(self):
        self.app_settings_manager.ensure_exists()
        self.catalogs_manager.ensure_exists()
        self.category_hints_manager.ensure_exists()
        self.gui_preferences_manager.ensure_exists()

    def load_config(self) -> dict:
        catalogs = self.catalogs_manager.load()
        return {
            "expense_categories": catalogs.get("expense_categories", {}),
            "income_categories": catalogs.get("income_categories", {}),
            "collective_name": self.app_settings_manager.get_collective_name(),
            "default_iva": self.app_settings_manager.get_default_iva(),
            "default_payment_method": self.app_settings_manager.get_default_payment_method(),
            "default_visibility": self.app_settings_manager.get_default_visibility(),
        }

    # Passthrough comodi per la UI.
    def update_catalog_field(self, section_name, key, value=None, operation="update"):
        self.catalogs_manager.update_list_field(section_name, key, value, operation)
