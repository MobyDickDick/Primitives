"""Export GEN-02: lowest-bit priority encoder, F-boxes and verified NAND nets.

Run: python -m tools.export_priority_encoder
"""
from functools import lru_cache
from pathlib import Path

from primitives.blocks import BlockBundle
from primitives.dataset import bits, generate
from primitives.library import fitness, write_json
from primitives.synthesis import synthesize
from primitives.templates import Template
from tools.export_blocks import inp, instance, out, ports
from tools.export_generative import netlist


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "examples/templates/recursive-priority-encoder.prim"
OUTPUT = ROOT / "examples/circuits/recursive-priority-encoder"


def definition():
    return {
        "schema": 1, "kind": "template", "name": "PE<t>",
        "description": "Prioritätsencoder: Index c des niedrigsten gesetzten Bits und valid. "
                       "Für a=0 gilt c=0, valid=0; sonst valid=1. Mehrfachbelegung wählt den kleinsten Index. "
                       "t ist eine positive Zweierpotenz bis 128; c hat max(1,LOG2(t)) Bits. "
                       "NAND-Übersetzung und F-Boxen unterliegen der 512-Gattergrenze.",
        "parameters": ["t"],
        "conditions": ["t >= 1", "t <= 128", "is_power_of_two(t)"],
        "interface": ports([("a", "t")], [("c", "max(1,LOG2(t))"), ("valid", 1)]),
        "source": SOURCE.read_text(encoding="utf-8"),
        "limits": {"steps": 100000, "iterations": 10000, "total_steps": 5000000},
    }


def merge_program(k):
    document = definition()
    r, w = max(1, k.bit_length() - 1), k.bit_length()
    document["name"] = f"PriorityMerge<{k}>"
    document["interface"] = ports([("lo", r), ("hi", r), ("lo_valid", 1), ("hi_valid", 1)],
                                  [("c", w), ("valid", 1)])
    document["source"] = document["source"].split("# Ergebnisports", 1)[0] + f"""
result = bits(PriorityMerge<{k}>(lo, hi, lo_valid, hi_valid), {w + 1})
return pack(result[:{w}]), result[{w}]
"""
    return Template(document).instantiate({"t": 1})


@lru_cache(maxsize=None)
def bundle(width):
    program = Template(definition()).instantiate({"t": width})
    name = f"PE<{width}>"
    if width == 1:
        return BlockBundle.from_circuit(name, synthesize(program), program.ports)
    k, w = width // 2, width.bit_length() - 1
    r = max(1, w - 1)
    child = bundle(k)
    merge = merge_program(k)
    select = BlockBundle.from_circuit(f"PriorityMerge<{k}>", synthesize(merge), merge.ports)
    nodes = [instance("lower", child, a=[inp("a", i) for i in range(k)]),
             instance("upper", child, a=[inp("a", k + i) for i in range(k)]),
             instance("merge", select,
                      lo=[out("lower", "c", i) for i in range(r)],
                      hi=[out("upper", "c", i) for i in range(r)],
                      lo_valid=[out("lower", "valid")], hi_valid=[out("upper", "valid")])]
    return BlockBundle.create({"name": name, "version": 1, "interface": program.ports,
                               "nodes": nodes, "outputs": {"c": [out("merge", "c", i) for i in range(w)],
                                                           "valid": [out("merge", "valid")]}}, [child, select])


def reference(value):
    """Independent integer oracle; never used to construct circuits."""
    return [(value & -value).bit_length() - 1, 1] if value else [0, 0]


def export():
    template = Template(definition())
    write_json(SOURCE.with_suffix(".abstract.json"), template.to_dict())
    OUTPUT.mkdir(parents=True, exist_ok=True)
    summary = []
    for width in (1, 2, 4):
        program = template.instantiate({"t": width})
        hierarchy = bundle(width)
        expanded = hierarchy.expand()
        circuit, compiled = expanded.simplify(), synthesize(program)
        w = max(1, width.bit_length() - 1)
        for value in range(1 << width):
            expected = reference(value)
            packed = bits(expected[0], w) + [expected[1]]
            if (program.run(value) != expected or any(
                    impl.evaluate(bits(value, width)) != packed
                    for impl in (hierarchy, expanded, circuit, compiled))):
                raise ValueError(f"PE<{width}> failed for input {value}")
        name = f"PE<{width}>"
        dataset = generate(name, width, w + 1, ports=program.ports, program=program.spec, samples=1 << width)
        dataset.metadata["description"] = template.document["description"]
        checked = fitness(circuit, dataset)
        if not checked["verified_truth_table"]:
            raise ValueError(f"{name} was not exhaustively verified")
        prefix = OUTPUT / f"pe-{width}"
        write_json(prefix.with_suffix(".block.json"), hierarchy.to_dict())
        write_json(prefix.with_suffix(".circuit.json"), circuit.to_dict())
        write_json(prefix.with_suffix(".template.json"), program.spec)
        write_json(prefix.with_suffix(".vectors.json"), dataset.to_dict())
        prefix.with_suffix(".nand.txt").write_text(netlist(circuit, program, name), encoding="utf-8")
        summary.append({"name": name, "parameters": {"t": width}, "interface": program.ports,
                        "fitness": checked, "hierarchy": hierarchy.summary(),
                        "synthesis": {"method": "hierarchy-expansion-and-simplification", "version": 1},
                        "files": {key: f"pe-{width}.{suffix}" for key, suffix in (
                            ("block", "block.json"), ("circuit", "circuit.json"), ("template", "template.json"),
                            ("vectors", "vectors.json"), ("netlist", "nand.txt"))}})
        print(f"{name}: {len(circuit.gates)} NANDs, depth {circuit.depth}, {len(dataset.rows)} inputs verified")
    write_json(OUTPUT / "verification.json", summary)


if __name__ == "__main__":
    export()
