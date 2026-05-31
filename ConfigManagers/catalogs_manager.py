from ConfigManagers.base_json_manager import BaseJsonConfigManager
from ConfigManagers.defaults import CATALOG_ADD_TRIGGERS, CATALOGS_DEFAULT


class CatalogsManager(BaseJsonConfigManager):
    """Categorie di spese ed entrate, editabili dal menu 'Categorie'."""

    file_name = "catalogs.json"
    default_data = CATALOGS_DEFAULT

    def get_section(self, section_name: str) -> dict:
        return self.load().get(section_name, {})

    def update_list_field(self, section_name: str, key: str, value: str = None, operation: str = "update"):
        config = self.load()

        if section_name not in config:
            if operation == "update":
                config[section_name] = {}
            else:
                raise Exception(f"La sezione '{section_name}' non esiste.")

        section_dict = config[section_name]

        if operation == "update":
            if key in section_dict:
                section_dict[key] = value
            else:
                # Inserisce la nuova voce mantenendo in coda il trigger
                # "AGGIUNGI…" (come la logica catalogs di Willow).
                trigger_key = CATALOG_ADD_TRIGGERS.get(section_name)
                items = list(section_dict.items())
                trigger_item = None
                if trigger_key and items and items[-1][0] == trigger_key:
                    trigger_item = items.pop(-1)

                new_section = {}
                for current_key, current_value in items:
                    new_section[current_key] = current_value
                new_section[key] = value
                if trigger_item:
                    new_section[trigger_item[0]] = trigger_item[1]
                config[section_name] = new_section

        elif operation == "delete":
            section_dict.pop(key, None)
        else:
            raise Exception("Operazione non riconosciuta. Usare 'update' o 'delete'.")

        self.save(config)
