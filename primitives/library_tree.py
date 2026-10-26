"""Persistent catalog folders, independent of content-addressed library files."""
import json
import uuid

from .dataset import validate_description


class LibraryFolders:
    def _organization(self):
        path = self.root / "folders.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return {"schema": 1, "folders": [
            {"id": "functions", "parent": None, "name": "Funktionen",
             "description": "Konkrete Funktionen mit Sollvektoren und ihren NAND-Implementierungen."},
            {"id": "templates", "parent": None, "name": "Templates",
             "description": "Abstrakte Vorlagen mit symbolischen Bitbreiten."}], "entries": {}}

    def _write_organization(self, organization):
        from .library import write_json
        write_json(self.root / "folders.json", organization)

    def tree(self):
        with self._lock:
            organization = self._organization()
            entries = {}
            for kind, items, default in (("function", self.datasets(), "functions"),
                                         ("template", self.templates(), "templates")):
                for item in items:
                    key = f"{kind}:{item['function_id'] if kind == 'function' else item['id']}"
                    entries[key] = organization["entries"].get(key, default)
            return {"schema": 1, "folders": organization["folders"], "entries": entries}

    def save_folder(self, name, description="", parent=None, key=None):
        if not isinstance(name, str) or not name.strip() or len(name) > 120:
            raise ValueError("Der Ordnername braucht 1–120 Zeichen.")
        description = validate_description(description)
        with self._lock:
            organization = self._organization()
            folders = {f["id"]: f for f in organization["folders"]}
            if parent is not None and (not isinstance(parent, str) or parent not in folders):
                raise ValueError("Übergeordneter Ordner nicht gefunden.")
            if key is not None and (not isinstance(key, str) or key not in folders):
                raise FileNotFoundError("Ordner nicht gefunden.")
            ancestor = parent
            while ancestor is not None:
                if ancestor == key:
                    raise ValueError("Ein Ordner darf nicht in sich selbst oder seine Unterordner verschoben werden.")
                ancestor = folders[ancestor]["parent"]
            if any(f["parent"] == parent and f["name"].casefold() == name.strip().casefold()
                   and f["id"] != key for f in folders.values()):
                raise ValueError("In diesem Ordner gibt es bereits einen Ordner mit diesem Namen.")
            folder = {"id": key or uuid.uuid4().hex, "parent": parent,
                      "name": name.strip(), "description": description}
            if key is None:
                organization["folders"].append(folder)
            else:
                folders[key].update(folder)
            self._write_organization(organization)
            return folder

    def move_entry(self, kind, key, folder):
        if kind not in ("function", "template") or not isinstance(key, str):
            raise ValueError("Ungültiger Bibliothekseintrag.")
        with self._lock:
            organization = self._organization()
            if not isinstance(folder, str) or folder not in {f["id"] for f in organization["folders"]}:
                raise ValueError("Zielordner nicht gefunden.")
            entry = f"{kind}:{key}"
            if entry not in self.tree()["entries"]:
                raise FileNotFoundError("Bibliothekseintrag nicht gefunden.")
            organization["entries"][entry] = folder
            self._write_organization(organization)
            return {"entry": entry, "folder": folder}

    def delete_folder(self, key):
        with self._lock:
            organization = self._organization()
            if key in ("functions", "templates"):
                raise ValueError("Die Standardordner werden für neue Einträge benötigt.")
            if key not in {f["id"] for f in organization["folders"]}:
                raise FileNotFoundError("Ordner nicht gefunden.")
            if (any(f["parent"] == key for f in organization["folders"])
                    or key in self.tree()["entries"].values()):
                raise ValueError("Nur leere Ordner können gelöscht werden.")
            organization["folders"] = [f for f in organization["folders"] if f["id"] != key]
            organization["entries"] = {k: v for k, v in organization["entries"].items() if v != key}
            self._write_organization(organization)
            return {"id": key}
