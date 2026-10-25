"""Content-addressed local library; names describe observed, not assumed behaviour."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from .circuit import Circuit
from .dataset import Dataset


def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:12]


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:60] or "programm"


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Unique temp name makes independent jobs safe; replace is atomic on one volume.
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False, suffix=".tmp") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
        temporary = Path(file.name)
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


class Library:
    def __init__(self, root):
        self.root = Path(root)

    def save_dataset(self, dataset):
        key = f"{slug(dataset.name)}-{digest(dataset.to_dict())}"
        write_json(self.root / "datasets" / f"{key}.json", dataset.to_dict())
        return key

    def load_dataset(self, key):
        self._key(key)
        return Dataset.from_dict(json.loads((self.root / "datasets" / f"{key}.json").read_text(encoding="utf-8")))

    @staticmethod
    def _key(key):
        if not isinstance(key, str) or not re.fullmatch(r"[a-z0-9-]{1,180}", key):
            raise ValueError("Ungültige Bibliothekskennung.")

    def save_program(self, result, dataset):
        dataset_id = self.save_dataset(dataset)
        c, f = Circuit.from_dict(result["circuit"]), result["fitness"]
        status = "exakt" if f["verified_truth_table"] else "stichprobe" if f["exact_on_dataset"] else "annaeherung"
        key = f"{slug(dataset.name)}-{c.inputs}zu{len(c.outputs)}-g{len(c.gates)}-t{c.depth}-{status}-{digest([c.to_dict(), dataset_id])}"
        obj = {**result, "id": key, "name": key, "dataset_id": dataset_id,
               "dataset_name": dataset.name, "created_at": datetime.now(timezone.utc).isoformat(), "schema": 1}
        try:
            obj["expressions"] = c.expressions()
        except ValueError:
            obj["expressions"] = None
        path = self.root / "programs" / f"{key}.json"
        if path.exists():
            obj["created_at"] = self.load_program(key)["created_at"]
        write_json(path, obj)
        return obj

    def load_program(self, key):
        self._key(key)
        obj = json.loads((self.root / "programs" / f"{key}.json").read_text(encoding="utf-8"))
        Circuit.from_dict(obj["circuit"])
        return obj

    def programs(self):
        return [self.load_program(p.stem) for p in sorted((self.root / "programs").glob("*.json"))]

    def datasets(self):
        return [{"id": p.stem, "name": d.name, "inputs": d.inputs, "outputs": d.outputs,
                 "count": len(d.rows), "exhaustive": d.exhaustive}
                for p in sorted((self.root / "datasets").glob("*.json")) for d in [self.load_dataset(p.stem)]]

