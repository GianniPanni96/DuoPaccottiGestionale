from copy import deepcopy

from ConfigManagers.base_json_manager import BaseJsonConfigManager
from ConfigManagers.defaults import DEFAULT_STARTUP_TAB, build_gui_preferences_default


class GuiPreferencesManager(BaseJsonConfigManager):
    """Preferenze GUI: tab di avvio + finestra temporale delle liste."""

    file_name = "gui_preferences.json"

    _CACHE_SENTINEL = object()

    def __init__(self):
        super().__init__()
        self._cached_data = self._CACHE_SENTINEL

    def build_default_data(self):
        return build_gui_preferences_default()

    def _data(self) -> dict:
        if self._cached_data is self._CACHE_SENTINEL:
            self._cached_data = self.load()
        return self._cached_data

    def invalidate_cache(self):
        self._cached_data = self._CACHE_SENTINEL

    # --- tab di avvio ---

    def get_startup_tab(self) -> str:
        general = self._data().get("general") or {}
        value = general.get("startup_tab")
        if isinstance(value, str) and value.strip():
            return value
        return DEFAULT_STARTUP_TAB

    def set_startup_tab(self, tab_name: str):
        data = self._data()
        data.setdefault("general", {})["startup_tab"] = str(tab_name)
        self.save(data)
        self.invalidate_cache()

    # --- finestra temporale liste ---

    def get_list_view_window_index(self, list_view_key: str, default: int = 0) -> int:
        list_views = self._data().get("list_views") or {}
        entry = list_views.get(list_view_key) or {}
        try:
            return int(entry.get("window_index", default))
        except (TypeError, ValueError):
            return default

    def set_list_view_window_index(self, list_view_key: str, idx: int):
        data = self._data()
        list_views = data.setdefault("list_views", {})
        list_views.setdefault(list_view_key, {})["window_index"] = int(idx)
        self.save(data)
        self.invalidate_cache()

    def list_views_snapshot(self) -> dict:
        return deepcopy(self._data().get("list_views") or {})
