"""Immutable, portable combinational blocks with named bit connections."""
import copy
import hashlib
import json
import re

from .circuit import Circuit
from .ports import interface


def block_id(definition):
    payload = json.dumps(definition, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return "block-" + hashlib.sha256(payload.encode()).hexdigest()


def default_interface(circuit):
    return interface({"inputs": [{"name": f"in{i}", "bits": 1} for i in range(circuit.inputs)],
                      "outputs": [{"name": f"out{i}", "bits": 1} for i in range(len(circuit.outputs))]})


class BlockBundle:
    """One root and a closed snapshot of its versioned dependencies.

    Validation produces a topological schedule and an independently usable NAND
    expansion. Evaluation below executes the hierarchy rather than that expansion.
    """
    def __init__(self, document):
        if (not isinstance(document, dict) or set(document) != {"schema", "root", "definitions"}
                or type(document["schema"]) is not int or document["schema"] != 1):
            raise ValueError("Bausteinpaket braucht schema 1, root und definitions.")
        definitions = document["definitions"]
        if not isinstance(definitions, dict) or not 1 <= len(definitions) <= 128:
            raise ValueError("Ein Paket braucht 1–128 Bausteindefinitionen.")
        if not isinstance(document["root"], str) or document["root"] not in definitions:
            raise ValueError("Die Wurzeldefinition fehlt im Bausteinpaket.")
        self._definitions = copy.deepcopy(definitions)
        self.root = document["root"]
        self._circuits, self._orders, self._costs, self._heights = {}, {}, {}, {}
        for key, d in self._definitions.items():
            if not isinstance(key, str) or not isinstance(d, dict):
                raise ValueError("Bausteindefinitionen brauchen Kennungen und Objekte.")
            if (set(d) - {"name", "version", "interface", "circuit", "nodes", "outputs", "source_program"}
                    or not isinstance(d.get("name"), str) or not 1 <= len(d["name"].strip()) <= 120
                    or type(d.get("version")) is not int or not 1 <= d["version"] <= 2**31-1):
                raise ValueError("Baustein braucht Name, positive Version und bekannte Felder.")
            if "source_program" in d and (not isinstance(d["source_program"], str) or len(d["source_program"]) > 180):
                raise ValueError("Ungültige Herkunftskennung.")
            d["interface"] = interface(d.get("interface"))
            if "circuit" in d:
                if "nodes" in d or "outputs" in d:
                    raise ValueError("Baustein hat entweder eine NAND-Schaltung oder Knoten und Portausgänge.")
                c = Circuit.from_dict(d["circuit"])
                if (c.inputs != sum(p["bits"] for p in d["interface"]["inputs"])
                        or len(c.outputs) != sum(p["bits"] for p in d["interface"]["outputs"])):
                    raise ValueError("Portbreiten passen nicht zur NAND-Implementierung.")
                d["circuit"] = c.to_dict()
            elif (not isinstance(d.get("nodes"), list) or len(d["nodes"]) > 512 or not isinstance(d.get("outputs"), dict)):
                raise ValueError("Hierarchie braucht höchstens 512 Knoten und benannte Ausgänge.")
        for key in self._definitions:
            self._expand(key, set(), 0)
        # Check after traversing dependencies to report missing references/cycles clearly.
        if any(block_id(d) != key for key, d in self._definitions.items()):
            raise ValueError("Bausteinkennung stimmt nicht mit dem unveränderlichen Definitionsinhalt überein.")
        reachable, queue = set(), [self.root]
        while queue:
            current = queue.pop()
            if current not in reachable:
                reachable.add(current)
                queue.extend(node["definition"] for node in self._definitions[current].get("nodes", []) if node["type"] == "instance")
        self._definitions = {key: d for key, d in self._definitions.items() if key in reachable}

    @classmethod
    def create(cls, definition, dependencies=()):
        if not isinstance(definition, dict):
            raise ValueError("Eine neue Bausteindefinition muss ein Objekt sein.")
        definitions = {}
        for bundle in dependencies:
            if not isinstance(bundle, cls):
                bundle = cls(bundle)
            definitions.update(bundle.to_dict()["definitions"])
        d = copy.deepcopy(definition)
        d["interface"] = interface(d.get("interface"))
        if "circuit" in d:
            d["circuit"] = Circuit.from_dict(d["circuit"]).to_dict()
        key = block_id(d)
        definitions[key] = d
        return cls({"schema": 1, "root": key, "definitions": definitions})

    @classmethod
    def from_circuit(cls, name, circuit, ports=None, version=1, source_program=None):
        d = {"name": name, "version": version, "interface": default_interface(circuit) if ports is None else ports,
             "circuit": circuit.to_dict()}
        if source_program is not None:
            d["source_program"] = source_program
        return cls.create(d)

    @property
    def definition(self):
        return copy.deepcopy(self._definitions[self.root])

    def to_dict(self):
        return {"schema": 1, "root": self.root, "definitions": copy.deepcopy(self._definitions)}

    def wrap(self, name, ports=None, version=1, source_program=None):
        own = interface(self.definition["interface"] if ports is None else ports, self.expand().inputs, len(self.expand().outputs))
        child = self.definition["interface"]
        refs = [{"input": p["name"], "bit": i} for p in own["inputs"] for i in range(p["bits"])]
        outputs = [{"node": "body", "port": p["name"], "bit": i} for p in child["outputs"] for i in range(p["bits"])]
        d = {"name": name, "version": version, "interface": own,
             "nodes": [{"id": "body", "type": "instance", "definition": self.root,
                        "inputs": {p["name"]: refs[p["offset"]:p["offset"] + p["bits"]] for p in child["inputs"]}}],
             "outputs": {p["name"]: outputs[p["offset"]:p["offset"] + p["bits"]] for p in own["outputs"]}}
        if source_program is not None:
            d["source_program"] = source_program
        return self.create(d, [self])

    def expand(self):
        return self._circuits[self.root]

    def _expand(self, key, visiting, depth):
        if key in visiting:
            raise ValueError("Zyklische oder rekursive Bausteinabhängigkeit.")
        if depth > 32:
            raise ValueError("Bausteinhierarchie darf höchstens 32 Ebenen enthalten.")
        if key in self._circuits:
            return self._circuits[key]
        if key not in self._definitions:
            raise ValueError(f"Fehlende Bausteinabhängigkeit: {key}.")
        d = self._definitions[key]
        if "circuit" in d:
            self._circuits[key] = Circuit.from_dict(d["circuit"])
            self._costs[key], self._heights[key] = 1, 0
            return self._circuits[key]
        visiting = visiting | {key}
        spec = d["interface"]
        n = sum(p["bits"] for p in spec["inputs"])
        nodes, signatures, dependencies = {}, {}, {}
        cost, height = 1, 0
        for node in d["nodes"]:
            if (not isinstance(node, dict) or not isinstance(node.get("id"), str)
                    or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,31}", node["id"]) or node["id"] in nodes):
                raise ValueError("Knoten brauchen eindeutige Namen mit höchstens 32 Zeichen.")
            node_id = node["id"]
            nodes[node_id] = node
            dependencies[node_id] = set()
            if node.get("type") == "instance" and set(node) == {"id", "type", "definition", "inputs"}:
                target = node["definition"]
                if not isinstance(target, str):
                    raise ValueError("Eine Instanz braucht eine konkrete Definitionskennung.")
                self._expand(target, visiting, depth + 1)
                signatures[node_id] = self._definitions[target]["interface"]
                cost += self._costs[target]
                height = max(height, 1 + self._heights[target])
            elif node.get("type") == "nand" and set(node) == {"id", "type", "inputs"}:
                signatures[node_id] = {"outputs": [{"name": "out", "bits": 1}]}
                cost += 1
            else:
                raise ValueError("Knoten sind NAND-Gatter oder Instanzen mit einer festen Definitionskennung.")
            if cost > 2048 or height > 32:
                raise ValueError("Hierarchie überschreitet 2048 expandierte Knoten oder 32 Ebenen.")

        def endpoint(ref, consumer=None):
            if not isinstance(ref, dict) or type(ref.get("bit")) is not int:
                raise ValueError("Verbindung braucht einen Port und einen ganzzahligen Bitindex.")
            if set(ref) == {"input", "bit"}:
                ports, name = spec["inputs"], ref["input"]
            elif set(ref) == {"node", "port", "bit"} and isinstance(ref["node"], str) and ref["node"] in nodes:
                ports, name = signatures[ref["node"]]["outputs"], ref["port"]
                if consumer is not None:
                    dependencies[consumer].add(ref["node"])
            else:
                raise ValueError("Verbindung verweist auf einen fehlenden Knoten oder unbekannte Felder.")
            port = next((p for p in ports if p["name"] == name), None)
            if port is None or not 0 <= ref["bit"] < port["bits"]:
                raise ValueError("Verbindung verweist auf einen unbekannten Port oder ein Bit ausserhalb seiner Breite.")

        def check_mapping(mapping, ports, consumer=None):
            if not isinstance(mapping, dict) or set(mapping) != {p["name"] for p in ports}:
                raise ValueError("Portzuordnung muss alle benannten Ports genau einmal enthalten.")
            for p in ports:
                refs = mapping[p["name"]]
                if not isinstance(refs, list) or len(refs) != p["bits"]:
                    raise ValueError(f"Port {p['name']}: falsche Verbindungsbreite.")
                for ref in refs:
                    endpoint(ref, consumer)

        for node_id, node in nodes.items():
            if node["type"] == "nand":
                if not isinstance(node["inputs"], list) or len(node["inputs"]) != 2:
                    raise ValueError("NAND braucht genau zwei Eingangsverbindungen.")
                for ref in node["inputs"]:
                    endpoint(ref, node_id)
            else:
                check_mapping(node["inputs"], signatures[node_id]["inputs"], node_id)
        check_mapping(d["outputs"], spec["outputs"])
        order, pending = [], set()

        def schedule(node_id):
            if node_id in pending:
                raise ValueError("Zyklische Verbindung zwischen Bausteininstanzen oder Gattern.")
            if node_id in order:
                return
            pending.add(node_id)
            for dep in sorted(dependencies[node_id]):
                schedule(dep)
            pending.remove(node_id)
            order.append(node_id)
        for node_id in nodes:
            schedule(node_id)
        gates, wires = [], {}
        inputs = {p["name"]: list(range(p["offset"], p["offset"] + p["bits"])) for p in spec["inputs"]}

        def resolve(ref):
            return (inputs[ref["input"]] if "input" in ref else wires[ref["node"]][ref["port"]])[ref["bit"]]

        for node_id in order:
            node = nodes[node_id]
            if node["type"] == "nand":
                wires[node_id] = {"out": [n + len(gates)]}
                gates.append(tuple(resolve(ref) for ref in node["inputs"]))
            else:
                child = self._circuits[node["definition"]]
                child_spec = signatures[node_id]
                mapping = [resolve(ref) for p in child_spec["inputs"] for ref in node["inputs"][p["name"]]]
                for a, b in child.gates:
                    gates.append((mapping[a], mapping[b]))
                    mapping.append(n + len(gates) - 1)
                out = [mapping[r] for r in child.outputs]
                wires[node_id] = {p["name"]: out[p["offset"]:p["offset"] + p["bits"]] for p in child_spec["outputs"]}
            if len(gates) > 512:
                raise ValueError("Expandierte Schaltung überschreitet 512 NAND-Gatter.")
        self._orders[key] = order
        self._costs[key], self._heights[key] = cost, height
        self._circuits[key] = Circuit(n, tuple(gates), tuple(resolve(ref) for p in spec["outputs"] for ref in d["outputs"][p["name"]]))
        return self._circuits[key]

    def evaluate(self, bits):
        if len(bits) != self.expand().inputs or any(type(b) is not int or b not in (0, 1) for b in bits):
            raise ValueError("Der Eingabevektor enthält nicht die erwarteten Bits.")

        def run(key, values):
            d = self._definitions[key]
            if "circuit" in d:
                return Circuit.from_dict(d["circuit"]).evaluate(values)
            spec = d["interface"]
            inputs = {p["name"]: values[p["offset"]:p["offset"] + p["bits"]] for p in spec["inputs"]}
            wires = {}
            def read(ref):
                return (inputs[ref["input"]] if "input" in ref else wires[ref["node"]][ref["port"]])[ref["bit"]]
            nodes = {node["id"]: node for node in d["nodes"]}
            for node_id in self._orders[key]:
                node = nodes[node_id]
                if node["type"] == "nand":
                    wires[node_id] = {"out": [1 - (read(node["inputs"][0]) & read(node["inputs"][1]))]}
                else:
                    child_spec = self._definitions[node["definition"]]["interface"]
                    output = run(node["definition"], [read(ref) for p in child_spec["inputs"] for ref in node["inputs"][p["name"]]])
                    wires[node_id] = {p["name"]: output[p["offset"]:p["offset"] + p["bits"]] for p in child_spec["outputs"]}
            return [read(ref) for p in spec["outputs"] for ref in d["outputs"][p["name"]]]
        return run(self.root, list(bits))

    def view(self, path=()):
        """Project one instance into boxes, retaining its exact expanded signals.

        Paths identify instances, not definitions: two uses of the same definition
        therefore have independent layouts and local debugger inputs.
        """
        if not isinstance(path, (list, tuple)) or len(path) > 32 or any(not isinstance(p, str) for p in path):
            raise ValueError("Instanzpfad muss eine Liste mit höchstens 32 Knotennamen sein.")
        key = self.root
        for part in path:
            node = next((n for n in self._definitions[key].get("nodes", [])
                         if n["id"] == part and n["type"] == "instance"), None)
            if node is None:
                raise ValueError("Instanzpfad verweist auf keinen Unterbaustein.")
            key = node["definition"]
        d, circuit = self._definitions[key], self._circuits[key]
        spec = d["interface"]
        if "circuit" in d:
            return {"definition": key, "name": d["name"], "version": d["version"],
                    "interface": copy.deepcopy(spec), "circuit": circuit.to_dict()}
        boxes, refs, signals = [], {}, {}
        for p in spec["inputs"]:
            for bit in range(p["bits"]):
                ref = len(boxes)
                refs[("input", p["name"], bit)] = (ref, 0)
                signals[("input", p["name"], bit)] = ref
                boxes.append({"ref": ref, "kind": "input", "index": ref, "sources": [],
                              "level": 0, "signalRefs": [ref], "label": f"{p['name']}[{bit}]"})

        def endpoint(r):
            return ("input", r["input"], r["bit"]) if "input" in r else (r["node"], r["port"], r["bit"])

        nodes = {n["id"]: n for n in d["nodes"]}
        gate_count = 0
        for node_id in self._orders[key]:
            node = nodes[node_id]
            child = self._definitions[node["definition"]] if node["type"] == "instance" else None
            child_spec = child["interface"] if child else {"inputs": [{"name": "in", "bits": 2, "offset": 0}],
                                                             "outputs": [{"name": "out", "bits": 1, "offset": 0}]}
            incoming = [r for p in child_spec["inputs"] for r in node["inputs"][p["name"]]] if child else node["inputs"]
            mapping = [signals[endpoint(r)] for r in incoming]
            input_refs = list(mapping)
            if child:
                expansion = self._circuits[node["definition"]]
                for _ in expansion.gates:
                    mapping.append(circuit.inputs + gate_count)
                    gate_count += 1
                output_refs = [mapping[r] for r in expansion.outputs]
            else:
                output_refs = [circuit.inputs + gate_count]
                gate_count += 1
            ref = len(boxes)
            sources = [refs[endpoint(r)][0] for r in incoming]
            source_bits = [refs[endpoint(r)][1] for r in incoming]
            box = {"ref": ref, "kind": "instance" if child else "gate", "index": ref - circuit.inputs,
                   "id": node_id, "sources": sources, "sourceBits": source_bits,
                   "level": 1 + max((boxes[r]["level"] for r in sources), default=0),
                   "signalRefs": output_refs, "inputRefs": input_refs, "interface": copy.deepcopy(child_spec)}
            if child:
                box.update(definition=node["definition"], name=child["name"], version=child["version"],
                           height=max(84, 44 + 16 * max(len(input_refs), len(output_refs))))
            boxes.append(box)
            for p in child_spec["outputs"]:
                for bit in range(p["bits"]):
                    slot = p["offset"] + bit
                    refs[(node_id, p["name"], bit)] = (ref, slot)
                    signals[(node_id, p["name"], bit)] = output_refs[slot]
        level = 1 + max(b["level"] for b in boxes)
        for p in spec["outputs"]:
            for bit, r in enumerate(d["outputs"][p["name"]]):
                source, slot = refs[endpoint(r)]
                boxes.append({"ref": len(boxes), "kind": "output", "index": p["offset"] + bit,
                              "sources": [source], "sourceBits": [slot], "level": level,
                              "signalRefs": [signals[endpoint(r)]], "label": f"{p['name']}[{bit}]"})
        return {"definition": key, "name": d["name"], "version": d["version"],
                "interface": copy.deepcopy(spec), "circuit": {**circuit.to_dict(), "view_nodes": boxes}}

    def dataset(self, samples=None, seed=1):
        from .dataset import bits, generate, integer
        c = self.expand()
        ds = generate(self.definition["name"], c.inputs, len(c.outputs), "NAND-Bausteinreferenz", samples, seed,
                      oracle=lambda x: integer(self.evaluate(bits(x, c.inputs))))
        ds.metadata.pop("expression")
        ds.metadata.update(hierarchy=self.to_dict(), interface=self.definition["interface"])
        return ds

    def summary(self):
        d, c = self.definition, self.expand()
        return {"id": self.root, "name": d["name"], "version": d["version"], "interface": d["interface"],
                "gates": len(c.gates), "depth": c.depth, "definitions": len(self._definitions),
                "instances": sum(n["type"] == "instance" for n in d.get("nodes", []))}
