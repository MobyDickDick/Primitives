"""Export and independently verify GEN-06. Run: python -m tools.export_prefixes."""
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
KINDS = ("prefix_and", "prefix_xor")
WIDTHS = (1, 2, 4)


def definition(kind):
    if kind not in KINDS:
        raise ValueError(f"Unknown prefix operation: {kind}")
    operation = "AND" if kind == "prefix_and" else "XOR"
    return {
        "schema": 1, "kind": "template", "name": f"{kind.upper()}<t>",
        "description": f"Inklusive Präfix-{operation} ab Bit 0: c[i]={operation}(a[0],...,a[i]). "
            "a[t] und c[t], LSB-first; t ist eine positive Zweierpotenz bis 128. "
            "Präfix-XOR ist entgegengesetzt zur Gray-Dekodierung orientiert. "
            "Rekursive Halbierung mit Übertragung des unteren Gesamtpräfixes; "
            "NAND-Netze/F-Boxen unterliegen der 512-Gattergrenze.",
        "parameters": ["t"],
        "conditions": ["t >= 1", "t <= 128", "is_power_of_two(t)"],
        "interface": ports([("a", "t")], [("c", "t")]),
        "source": (TEMPLATES / f"recursive-{kind}.prim").read_text(encoding="utf-8"),
        "limits": {"steps": 100000, "iterations": 10000, "total_steps": 5000000},
    }


def merge_program(kind, width):
    document = definition(kind)
    name = "PrefixANDMerge" if kind == "prefix_and" else "PrefixXORMerge"
    document["name"] = f"{name}<{width}>"
    document["interface"] = ports([("a", width), ("sel", 1)], [("c", width)])
    document["source"] = document["source"].split("# Ergebnisport", 1)[0] + f"return {name}<{width}>(a, sel)\n"
    return Template(document).instantiate({"t": 1})


@lru_cache(maxsize=None)
def bundle(kind, width):
    program = Template(definition(kind)).instantiate({"t": width})
    name = f"{kind.upper()}<{width}>"
    if width == 1:
        return BlockBundle.from_circuit(name, synthesize(program), program.ports)
    k = width // 2
    child = bundle(kind, k)
    merge = merge_program(kind, k)
    combine = BlockBundle.from_circuit(f"{kind.upper()}_MERGE<{k}>", synthesize(merge), merge.ports)
    lo = [out("lower", "c", i) for i in range(k)]
    nodes = [instance("lower", child, a=[inp("a", i) for i in range(k)]),
             instance("upper", child, a=[inp("a", k + i) for i in range(k)]),
             instance("prefix", combine, a=[out("upper", "c", i) for i in range(k)], sel=[lo[-1]])]
    return BlockBundle.create({"name": name, "version": 1, "interface": program.ports,
                               "nodes": nodes, "outputs": {"c": lo + [out("prefix", "c", i) for i in range(k)]}},
                              [child, combine])


def reference(kind, width, value):
    """Integer mask oracle, independent of the recursive construction."""
    if kind not in KINDS:
        raise ValueError(f"Unknown prefix operation: {kind}")
    result = 0
    for i in range(width):
        mask = (1 << (i + 1)) - 1
        prefix = value & mask
        bit = int(prefix == mask) if kind == "prefix_and" else prefix.bit_count() % 2
        result |= bit << i
    return result


def export():
    for kind in KINDS:
        template = Template(definition(kind))
        write_json(TEMPLATES / f"recursive-{kind}.abstract.json", template.to_dict())
        folder = OUTPUT / f"recursive-{kind}"
        folder.mkdir(parents=True, exist_ok=True)
        reports = []
        for width in WIDTHS:
            name = f"{kind.upper()}<{width}>"
            program = template.instantiate({"t": width})
            hierarchy = bundle(kind, width)
            expanded = hierarchy.expand()
            circuit, compiled = expanded.simplify(), synthesize(program)
            rows = []
            for value in range(1 << width):
                expected = reference(kind, width, value)
                inputs, outputs = bits(value, width), bits(expected, width)
                if program.run(value) != [expected] or any(
                        impl.evaluate(inputs) != outputs for impl in (hierarchy, expanded, circuit, compiled)):
                    raise ValueError(f"{kind}<{width}> failed for input {value}")
                rows.append(inputs + outputs)
            dataset = Dataset(name, width, width, rows,
                              {"program": program.spec, "interface": program.ports,
                               "description": template.document["description"]})
            checked = fitness(circuit, dataset)
            if not checked["verified_truth_table"]:
                raise ValueError("Export requires a fully verified truth table")
            prefix = folder / f"{kind}-{width}"
            for suffix, document in (("block", hierarchy.to_dict()), ("circuit", circuit.to_dict()),
                                     ("template", program.spec), ("vectors", dataset.to_dict())):
                write_json(prefix.with_suffix(f".{suffix}.json"), document)
            prefix.with_suffix(".nand.txt").write_text(netlist(circuit, program, name), encoding="utf-8")
            reports.append({"name": name, "parameters": {"t": width}, "interface": program.ports,
                            "fitness": checked, "hierarchy": hierarchy.summary(),
                            "synthesis": {"method": "hierarchy-expansion-and-simplification", "version": 1},
                            "files": {key: f"{kind}-{width}.{suffix}" for key, suffix in (
                                ("block", "block.json"), ("circuit", "circuit.json"), ("template", "template.json"),
                                ("vectors", "vectors.json"), ("netlist", "nand.txt"))}})
            print(f"{name}: {len(circuit.gates)} NANDs, depth {circuit.depth}, {len(rows)} inputs verified", flush=True)
        write_json(folder / "verification.json", reports)


if __name__ == "__main__":
    export()
