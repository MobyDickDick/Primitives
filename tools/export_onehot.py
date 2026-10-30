"""Export GEN-03 decoder/one-hot encoder with independently verified hardware.

Run: python -m tools.export_onehot
"""
from functools import lru_cache
from pathlib import Path

from primitives.blocks import BlockBundle
from primitives.dataset import Dataset, bits
from primitives.library import fitness, write_json
from primitives.synthesis import synthesize
from primitives.templates import Template
from tools.export_blocks import inp, instance, out, ports
from tools.export_generative import netlist


ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "examples/templates"
OUTPUT = ROOT / "examples/circuits"
KINDS = ("decoder", "onehot-encoder")


def label(kind, w):
    if kind not in KINDS:
        raise ValueError(f"Unknown one-hot template: {kind}")
    return f"{'DEC' if kind == 'decoder' else 'OHE'}<{w}>"


def definition(kind):
    decoder = kind == "decoder"
    return {
        "schema": 1, "kind": "template", "name": label(kind, "w"),
        "description": (
            "Decoder: w-Bit-Code a auf 2**w One-Hot-Ausgangsbits c. "
            "enable=1 setzt genau Bit a, enable=0 liefert null. Für Betrieb ohne Freigabe enable=1 verbinden. "
            if decoder else
            "One-Hot-Encoder: 2**w Eingangsbits a auf w Codebits c, valid und multiple. "
            "Genau ein gesetztes Bit liefert dessen Index und valid=1. "
            "Null liefert [0,0,0], Mehrfachbelegung [0,0,1]; ungültige Indizes bleiben null. "
        ) + "LSB-first; 1 <= w <= 7. Die One-Hot-Breite wächst exponentiell bis 128 Bits; "
            "NAND-Übersetzung und F-Boxen unterliegen der 512-Gattergrenze.",
        "parameters": ["w"], "conditions": ["w >= 1", "w <= 7"],
        "interface": ports([("a", "w"), ("enable", 1)] if decoder else [("a", "2 ** w")],
                           [("c", "2 ** w")] if decoder else [("c", "w"), ("valid", 1), ("multiple", 1)]),
        "source": (TEMPLATES / f"recursive-{kind}.prim").read_text(encoding="utf-8"),
        "limits": {"steps": 100000, "iterations": 10000, "total_steps": 5000000},
    }


def merge_program(r):
    document = definition("onehot-encoder")
    document["name"] = f"OneHotMerge<{r}>"
    document["interface"] = ports([("lo", r), ("hi", r), ("lv", 1), ("hv", 1), ("lm", 1), ("hm", 1)],
                                  [("c", r + 1), ("valid", 1), ("multiple", 1)])
    document["source"] = document["source"].split("# Ergebnisports", 1)[0] + f"""
result = bits(OneHotMerge<{r}>(lo, hi, lv, hv, lm, hm), {r + 3})
return pack(result[:{r + 1}]), result[{r + 1}], result[{r + 2}]
"""
    return Template(document).instantiate({"w": 1})


@lru_cache(maxsize=None)
def bundle(kind, w):
    program = Template(definition(kind)).instantiate({"w": w})
    name = label(kind, w)
    if w == 1:
        return BlockBundle.from_circuit(name, synthesize(program), program.ports)
    child = bundle(kind, w - 1)
    k = 1 << (w - 1)
    if kind == "decoder":
        stage = bundle(kind, 1)
        nodes = [instance("split", stage, a=[inp("a", w - 1)], enable=[inp("enable")])]
        nodes.extend(instance(half, child, a=[inp("a", i) for i in range(w - 1)],
                              enable=[out("split", "c", bit)])
                     for half, bit in (("lower", 0), ("upper", 1)))
        outputs = {"c": [out(half, "c", i) for half in ("lower", "upper") for i in range(k)]}
    else:
        r = w - 1
        merge = merge_program(r)
        stage = BlockBundle.from_circuit(f"OneHotMerge<{r}>", synthesize(merge), merge.ports)
        nodes = [instance(half, child, a=[inp("a", offset + i) for i in range(k)])
                 for half, offset in (("lower", 0), ("upper", k))]
        nodes.append(instance("merge", stage,
                              lo=[out("lower", "c", i) for i in range(r)],
                              hi=[out("upper", "c", i) for i in range(r)],
                              lv=[out("lower", "valid")], hv=[out("upper", "valid")],
                              lm=[out("lower", "multiple")], hm=[out("upper", "multiple")]))
        outputs = {"c": [out("merge", "c", i) for i in range(w)],
                   "valid": [out("merge", "valid")], "multiple": [out("merge", "multiple")]}
    return BlockBundle.create({"name": name, "version": 1, "interface": program.ports,
                               "nodes": nodes, "outputs": outputs}, [child, stage])


def reference(kind, w, value):
    """Independent integer oracle; never used to construct circuits."""
    if kind == "decoder":
        code, enable = value & ((1 << w) - 1), value >> w
        return [enable << code]
    count = value.bit_count()
    return [value.bit_length() - 1 if count == 1 else 0, int(count == 1), int(count > 1)]


def packed_result(program, result):
    return [bit for port, value in zip(program.ports["outputs"], result) for bit in bits(value, port["bits"])]


def export():
    for kind in KINDS:
        template = Template(definition(kind))
        write_json(TEMPLATES / f"recursive-{kind}.abstract.json", template.to_dict())
        folder = OUTPUT / f"recursive-{kind}"
        folder.mkdir(parents=True, exist_ok=True)
        reports = []
        for w in (1, 2, 4):
            program = template.instantiate({"w": w})
            hierarchy = bundle(kind, w)
            expanded = hierarchy.expand()
            circuit, compiled = expanded.simplify(), synthesize(program)
            n = sum(p["bits"] for p in program.ports["inputs"])
            m = sum(p["bits"] for p in program.ports["outputs"])
            rows = []
            for value in range(1 << n):
                expected = reference(kind, w, value)
                inputs, outputs = bits(value, n), packed_result(program, expected)
                if (program.run(value) != expected or any(
                        impl.evaluate(inputs) != outputs for impl in (hierarchy, expanded, circuit, compiled))):
                    raise ValueError(f"{label(kind, w)} failed for input {value}")
                rows.append(inputs + outputs)
            # Keep the program as the editable reference; rows were independently checked above.
            dataset = Dataset(label(kind, w), n, m, rows,
                              {"program": program.spec, "interface": program.ports,
                               "description": template.document["description"]})
            checked = fitness(circuit, dataset)
            if not checked["verified_truth_table"]:
                raise ValueError(f"{label(kind, w)} was not exhaustively verified")
            prefix = folder / f"{kind}-{w}"
            write_json(prefix.with_suffix(".block.json"), hierarchy.to_dict())
            write_json(prefix.with_suffix(".circuit.json"), circuit.to_dict())
            write_json(prefix.with_suffix(".template.json"), program.spec)
            write_json(prefix.with_suffix(".vectors.json"), dataset.to_dict())
            prefix.with_suffix(".nand.txt").write_text(netlist(circuit, program, label(kind, w)), encoding="utf-8")
            reports.append({"name": label(kind, w), "parameters": {"w": w}, "interface": program.ports,
                            "fitness": checked, "hierarchy": hierarchy.summary(),
                            "synthesis": {"method": "hierarchy-expansion-and-simplification", "version": 1},
                            "files": {key: f"{kind}-{w}.{suffix}" for key, suffix in (
                                ("block", "block.json"), ("circuit", "circuit.json"), ("template", "template.json"),
                                ("vectors", "vectors.json"), ("netlist", "nand.txt"))}})
            print(f"{label(kind, w)}: {len(circuit.gates)} NANDs, depth {circuit.depth}, {len(rows)} inputs verified", flush=True)
        write_json(folder / "verification.json", reports)


if __name__ == "__main__":
    export()
