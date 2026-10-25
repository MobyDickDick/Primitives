"""Local library retaining the best circuit for each set of assignments."""
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import threading
from .circuit import Circuit
from .dataset import Dataset, validate_description
from .operations import operation_label
from .blocks import BlockBundle


def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:12]


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:60] or "programm"


def task_id(dataset):
    # Labels, generation seeds and metadata do not change the actual task.
    return digest([dataset.inputs, dataset.outputs, dataset.rows])


def function_id(dataset):
    """A reference function exists independently of its sampled vectors or circuits."""
    meta = dataset.metadata
    if "program" in meta:
        return digest(["program", dataset.inputs, dataset.outputs, meta["interface"],
                       meta["program"]["version"], meta["program"]["source"]])
    if "hierarchy" in meta:
        return digest(["block", meta["hierarchy"]["root"]])
    if "operation" in meta:
        return digest(["operation", meta["operation"]])
    if "expression" in meta or "reference_circuit" in meta:
        return digest([dataset.inputs, dataset.outputs, meta.get("interface"),
                       meta.get("expression"), meta.get("reference_circuit"), meta.get("oracle_file"),
                       meta.get("formula", {}).get("version")])
    return task_id(dataset)


def fitness(circuit, dataset):
    """Recheck saved and new circuits against the same assignment bits."""
    if circuit.inputs != dataset.inputs or len(circuit.outputs) != dataset.outputs:
        raise ValueError("Programm und Datensatz haben verschiedene Bitbreiten.")
    columns = [0] * (dataset.inputs + dataset.outputs)
    for i, row in enumerate(dataset.rows):
        for j, bit in enumerate(row):
            columns[j] |= bit << i
    values = columns[:dataset.inputs]
    mask = (1 << len(dataset.rows)) - 1
    for a, b in circuit.gates:
        values.append(mask ^ (values[a] & values[b]))
    errors = sum((values[o] ^ target).bit_count()
                 for o, target in zip(circuit.outputs, columns[dataset.inputs:]))
    total = len(dataset.rows) * dataset.outputs
    return {"errors": errors, "total_bits": total, "accuracy": (total - errors) / total,
            "exact_on_dataset": errors == 0,
            "verified_truth_table": errors == 0 and dataset.exhaustive,
            "gates": len(circuit.active()), "depth": circuit.depth}


def rank(program):
    f = program["fitness"]
    return f["errors"], f["gates"], f["depth"]


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
        self._lock = threading.RLock()

    def save_dataset(self, dataset):
        key = f"{slug(dataset.name)}-{digest(dataset.to_dict())}"
        with self._lock:
            write_json(self.root / "datasets" / f"{key}.json", dataset.to_dict())
        return key

    def load_dataset(self, key):
        self._key(key)
        with self._lock:
            return Dataset.from_dict(json.loads((self.root / "datasets" / f"{key}.json").read_text(encoding="utf-8")))

    def _function_details(self):
        path = self.root / "function-details.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    def dataset_document(self, dataset):
        """Apply editable labels at the boundary, keeping stored IDs and search inputs stable."""
        with self._lock:
            details = self._function_details().get(function_id(dataset))
            document = dataset.to_dict()
            if details is not None:
                document = {**document, "name": details["name"],
                            "metadata": {**document["metadata"], "description": details["description"]}}
            return document

    def update_function(self, key, name, description):
        if not isinstance(key, str) or not re.fullmatch(r"[a-f0-9]{12}", key):
            raise ValueError("Ungültige Funktionskennung.")
        if not isinstance(name, str) or not name.strip() or len(name) > 120:
            raise ValueError("Der Funktionsname braucht 1–120 Zeichen.")
        description = validate_description(description)
        with self._lock:
            ids = [d["id"] for d in self.datasets() if d["function_id"] == key]
            if not ids:
                raise FileNotFoundError("Funktion nicht gefunden.")
            details = self._function_details()
            details[key] = {"name": name.strip(), "description": description}
            write_json(self.root / "function-details.json", details)
            return {"function_id": key, "dataset_ids": ids, **details[key]}

    def delete_function(self, key):
        """Remove all vector sets and private circuits; retain shared implementations."""
        if not isinstance(key, str) or not re.fullmatch(r"[a-f0-9]{12}", key):
            raise ValueError("Ungültige Funktionskennung.")
        with self._lock:
            datasets = self.datasets()
            removed = [d for d in datasets if d["function_id"] == key]
            if not removed:
                raise FileNotFoundError("Funktion nicht gefunden.")
            dataset_ids = {d["id"] for d in removed}
            tasks = {d["task_id"] for d in removed}
            remaining = {d["task_id"]: d for d in datasets if d["id"] not in dataset_ids}
            # Include historical versions, not only the winners shown in the catalog.
            programs = [(p, self.load_program(p.stem)) for p in sorted((self.root / "programs").glob("*.json"))]
            program_ids = []
            for path, program in programs:
                if program["dataset_id"] not in dataset_ids:
                    continue
                replacement = remaining.get(program["task_id"])
                if replacement:
                    # Equal assignment vectors share one implementation, even across functions.
                    program.update(dataset_id=replacement["id"], dataset_name=replacement["name"],
                                   dataset_metadata=replacement["metadata"])
                    write_json(path, program)
                else:
                    path.unlink()
                    program_ids.append(program["id"])
            for dataset_id in dataset_ids:
                (self.root / "datasets" / f"{dataset_id}.json").unlink()
            settings = self._settings()
            for task in tasks - remaining.keys():
                settings.pop(task, None)
            if (self.root / "task-settings.json").exists():
                write_json(self.root / "task-settings.json", settings)
            details = self._function_details()
            if key in details:
                del details[key]
                write_json(self.root / "function-details.json", details)
            return {"function_id": key, "dataset_ids": sorted(dataset_ids), "program_ids": sorted(program_ids)}

    def save_block(self, bundle):
        if not isinstance(bundle, BlockBundle):
            bundle = BlockBundle(bundle)
        with self._lock:
            path = self.root / "blocks" / f"{bundle.root}.json"
            if path.exists():
                if self.load_block(bundle.root).to_dict() != bundle.to_dict():
                    raise ValueError("Eine feste Bausteinversion darf nicht überschrieben werden.")
            else:
                write_json(path, bundle.to_dict())
        return bundle.summary()

    def load_block(self, key):
        self._key(key)
        bundle = BlockBundle(json.loads((self.root / "blocks" / f"{key}.json").read_text(encoding="utf-8")))
        if bundle.root != key:
            raise ValueError("Bausteindatei und Definitionskennung stimmen nicht überein.")
        return bundle

    def blocks(self):
        with self._lock:
            return [self.load_block(p.stem).summary() for p in sorted((self.root / "blocks").glob("*.json"))]

    def block_from_program(self, key, name=None, ports=None, version=1):
        program = self.load_program(key)
        c = Circuit.from_dict(program["circuit"])
        ports = program["dataset_metadata"].get("interface") if ports is None else ports
        if "hierarchy" in program:
            bundle = BlockBundle(program["hierarchy"]).wrap(name or program["dataset_name"], ports, version, key)
        else:
            bundle = BlockBundle.from_circuit(name or program["dataset_name"], c, ports, version, key)
        self.save_block(bundle)
        return bundle

    def load_layout(self, circuit):
        return self.load_layout_data(circuit)["positions"]

    def load_layout_data(self, circuit, *, identity=None):
        path = self.root / "layouts" / f"{digest(circuit.to_dict() if identity is None else identity)}.json"
        with self._lock:
            if not path.exists():
                return {"positions": None, "wires": {}}
            data = json.loads(path.read_text(encoding="utf-8"))
            return {"positions": data["positions"], "wires": data.get("wires", {})}

    def save_layout(self, circuit, positions, wires=None, *, identity=None, nodes=None):
        count = len(nodes) if nodes is not None else circuit.inputs + len(circuit.gates) + len(circuit.outputs)
        if not isinstance(positions, list) or len(positions) != count:
            raise ValueError("Für jede Box wird eine Position benötigt.")
        cleaned = []
        for point in positions:
            if (not isinstance(point, dict) or set(point) != {"x", "y"}
                    or any(type(point[k]) not in (int, float) or not math.isfinite(point[k])
                           or not 0 <= point[k] <= 100000 for k in ("x", "y"))):
                raise ValueError("Ungültige Boxposition.")
            cleaned.append({"x": point["x"], "y": point["y"]})
        # Logical input indices are stable even when the renderer swaps visual ports.
        connections = {f"{source}:{circuit.inputs + i}:{port}"
                       for i, sources in enumerate(circuit.gates) for port, source in enumerate(sources)}
        connections.update(f"{source}:{circuit.inputs + len(circuit.gates) + i}:0"
                           for i, source in enumerate(circuit.outputs))
        if nodes is not None:
            connections = {f"{source}:{node['ref']}:{port}:{node['sourceBits'][port]}"
                           for node in nodes for port, source in enumerate(node["sources"])}
        wires = {} if wires is None else wires
        if not isinstance(wires, dict) or not set(wires) <= connections:
            raise ValueError("Ungültige Leitungskennung.")
        cleaned_wires = {}
        for key, points in wires.items():
            if not isinstance(points, list) or not 2 <= len(points) <= 128:
                raise ValueError("Eine Leitung benötigt 2–128 Stützpunkte.")
            for i, point in enumerate(points):
                if (not isinstance(point, dict) or set(point) != {"x", "y"}
                        or any(type(point[k]) not in (int, float) or not math.isfinite(point[k])
                               or not 0 <= point[k] <= 100000 for k in ("x", "y"))):
                    raise ValueError("Ungültiger Leitungsstützpunkt.")
                if i and point["x"] != points[i - 1]["x"] and point["y"] != points[i - 1]["y"]:
                    raise ValueError("Leitungssegmente müssen waagrecht oder senkrecht sein.")
            cleaned_wires[key] = [{"x": p["x"], "y": p["y"]} for p in points]
        with self._lock:
            write_json(self.root / "layouts" / f"{digest(circuit.to_dict() if identity is None else identity)}.json",
                       {"schema": 2, "positions": cleaned, "wires": cleaned_wires})
        return cleaned

    @staticmethod
    def _key(key):
        if not isinstance(key, str) or not re.fullmatch(r"[a-z0-9-]{1,180}", key):
            raise ValueError("Ungültige Bibliothekskennung.")

    def _settings(self):
        path = self.root / "task-settings.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    def is_frozen(self, key):
        with self._lock:
            return self._settings().get(key, {}).get("frozen", False)

    def set_frozen(self, program_id, frozen):
        if type(frozen) is not bool:
            raise ValueError("frozen muss ein Wahrheitswert sein.")
        with self._lock:
            program = self.load_program(program_id)
            settings = self._settings()
            settings[program["task_id"]] = {"frozen": frozen}
            write_json(self.root / "task-settings.json", settings)
            return {"task_id": program["task_id"], "frozen": frozen}

    def save_program(self, result, dataset, *, background=False):
        with self._lock:
            if background and self.is_frozen(task_id(dataset)):
                return None
            return self._save_program(result, dataset)

    def _save_program(self, result, dataset):
        c = Circuit.from_dict(result["circuit"])
        self._check_hierarchy(result, c)
        result = {**result, "fitness": fitness(c, dataset)}
        previous = next((p for p in self.programs() if p["task_id"] == task_id(dataset)), None)
        # Preserve the requested interface even when an existing circuit wins a retest.
        dataset_id = self.save_dataset(dataset)
        comparison = None
        if previous:
            comparison = {"accepted": rank(result) < rank(previous), "previous_id": previous["id"],
                          "previous_fitness": previous["fitness"], "candidate_fitness": result["fitness"]}
            if not comparison["accepted"]:
                return {**previous, "comparison": comparison}
        f = result["fitness"]
        status = "exakt" if f["verified_truth_table"] else "stichprobe" if f["exact_on_dataset"] else "annaeherung"
        key = f"{slug(dataset.name)}-{c.inputs}zu{len(c.outputs)}-g{len(c.gates)}-t{c.depth}-{status}-{digest([c.to_dict(), dataset_id])}"
        obj = {**result, "id": key, "name": key, "dataset_id": dataset_id,
               "task_id": task_id(dataset),
               "frozen": self.is_frozen(task_id(dataset)),
               "dataset_name": dataset.name, "dataset_metadata": dataset.metadata,
               "created_at": datetime.now(timezone.utc).isoformat(), "schema": 1}
        try:
            obj["expressions"] = c.expressions()
        except ValueError:
            obj["expressions"] = None
        path = self.root / "programs" / f"{key}.json"
        if path.exists():
            obj["created_at"] = self.load_program(key)["created_at"]
        write_json(path, obj)
        obj = self.load_program(key)
        return {**obj, "comparison": comparison} if comparison else obj

    def load_program(self, key):
        with self._lock:
            return self._load_program(key)

    def _load_program(self, key):
        self._key(key)
        obj = json.loads((self.root / "programs" / f"{key}.json").read_text(encoding="utf-8"))
        circuit = Circuit.from_dict(obj["circuit"])
        self._check_hierarchy(obj, circuit)
        try:
            obj["expressions"] = circuit.expressions()
        except ValueError:
            obj["expressions"] = None
        dataset = self.load_dataset(obj["dataset_id"])
        obj["task_id"] = task_id(dataset)
        obj["dataset_metadata"] = dataset.metadata
        document = self.dataset_document(dataset)
        obj["dataset_name"] = document["name"]
        obj["dataset_metadata"] = document["metadata"]
        obj["frozen"] = self.is_frozen(obj["task_id"])
        return obj

    @staticmethod
    def _check_hierarchy(result, circuit):
        if "hierarchy" in result:
            bundle = BlockBundle(result["hierarchy"])
            if bundle.expand() != circuit:
                raise ValueError("Hierarchie stimmt nicht mit der konkreten NAND-Implementierung überein.")

    def programs(self):
        # Older versions remain loadable by ID; the catalog shows one winner per task.
        with self._lock:
            winners, datasets = {}, {}
            programs = [self.load_program(p.stem) for p in sorted((self.root / "programs").glob("*.json"))]
            for program in sorted(programs, key=lambda p: (p["created_at"], p["id"])):
                dataset_id = program["dataset_id"]
                if dataset_id not in datasets:
                    datasets[dataset_id] = self.load_dataset(dataset_id)
                dataset = datasets[dataset_id]
                key = task_id(dataset)
                program["task_id"] = key
                program["fitness"] = fitness(Circuit.from_dict(program["circuit"]), dataset)
                if key not in winners or rank(program) < rank(winners[key]):
                    winners[key] = program
            return sorted(winners.values(), key=lambda p: p["id"])

    def datasets(self):
        with self._lock:
            return [{"id": p.stem, "name": doc["name"], "inputs": d.inputs, "outputs": d.outputs,
                     "count": len(d.rows), "exhaustive": d.exhaustive,
                     "function_id": function_id(d), "task_id": task_id(d), "metadata": doc["metadata"],
                     "function_name": doc["name"], "description": doc["metadata"].get("description", ""),
                     "operation_label": operation_label(d.metadata["operation"]) if "operation" in d.metadata else None}
                    for p in sorted((self.root / "datasets").glob("*.json")) for d in [self.load_dataset(p.stem)]
                    for doc in [self.dataset_document(d)]]

