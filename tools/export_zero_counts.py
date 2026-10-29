"""Export GEN-01: recursive CLZ/CTZ, F-boxes and verified NAND nets.

Run: python -m tools.export_zero_counts
"""
from functools import lru_cache
from pathlib import Path

from primitives.blocks import BlockBundle
from primitives.dataset import bits, generate
from primitives.library import fitness, write_json
from primitives.synthesis import synthesize
from primitives.templates import Template
from tools.export_blocks import inp, instance, out, ports
from tools.export_generative import bundle as logic_bundle, netlist


ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "examples/templates"
OUTPUT = ROOT / "examples/circuits"
KINDS = ("clz", "ctz")


def definition(kind):
    if kind not in KINDS:
        raise ValueError("Expected clz or ctz")
    direction = "Führende Nullbits ab Bit t-1" if kind == "clz" else "Nachlaufende Nullbits ab Bit 0"
    return {
        "schema": 1, "kind": "template", "name": f"{kind.upper()}<t>",
        "description": direction + " durch rekursive Halbierung zählen. Für a=0 ist c=t; sonst 0<=c<t. "
                       "t ist eine positive Zweierpotenz bis 128; c hat LOG2(t)+1 Bits. "
                       "NAND-Übersetzung und F-Boxen unterliegen zusätzlich der 512-Gattergrenze.",
        "parameters": ["t"],
        "conditions": ["t >= 1", "t <= 128", "is_power_of_two(t)"],
        "interface": ports([("a", "t")], [("c", "LOG2(t)+1")]),
        "source": (TEMPLATES / f"recursive-{kind}.prim").read_text(encoding="utf-8"),
        "limits": {"steps": 100000, "iterations": 10000, "total_steps": 5000000},
    }


def merge_program(k):
    document = definition("clz")
    r = k.bit_length()
    document["name"] = f"CountMerge<{k}>"
    document["interface"] = ports([("first", r), ("second", r), ("z", 1)], [("c", r + 1)])
    document["source"] = document["source"].rsplit("\nreturn ", 1)[0] + f"\nreturn CountMerge<{k}>(first, second, z)\n"
    return Template(document).instantiate({"t": 1})


@lru_cache(maxsize=None)
def bundle(kind, width):
    program = Template(definition(kind)).instantiate({"t": width})
    name = f"{kind.upper()}<{width}>"
    if width == 1:
        return BlockBundle.from_circuit(name, synthesize(program), program.ports)
    k, r = width // 2, width.bit_length() - 1
    child, zero = bundle(kind, k), logic_bundle("iszero", k)
    merge = merge_program(k)
    select = BlockBundle.from_circuit(f"CountMerge<{k}>", synthesize(merge), merge.ports)
    first, second = (k, 0) if kind == "clz" else (0, k)
    first_bits = [inp("a", first + i) for i in range(k)]
    nodes = [instance("first", child, a=first_bits),
             instance("second", child, a=[inp("a", second + i) for i in range(k)]),
             instance("zero", zero, a=first_bits),
             instance("merge", select,
                      first=[out("first", "c", i) for i in range(r)],
                      second=[out("second", "c", i) for i in range(r)],
                      z=[out("zero", "c")])]
    return BlockBundle.create({"name": name, "version": 1, "interface": program.ports,
                               "nodes": nodes,
                               "outputs": {"c": [out("merge", "c", i) for i in range(r + 1)]}},
                              [child, zero, select])


def reference(kind, width, value):
    """Independent integer oracle; never used to construct circuits."""
    if kind == "clz":
        return width - value.bit_length()
    return (value & -value).bit_length() - 1 if value else width


def export():
    for kind in KINDS:
        template = Template(definition(kind))
        write_json(TEMPLATES / f"recursive-{kind}.abstract.json", template.to_dict())
        folder = OUTPUT / f"recursive-{kind}"
        folder.mkdir(parents=True, exist_ok=True)
        summary = []
        for width in (1, 2, 4):
            program = template.instantiate({"t": width})
            hierarchy = bundle(kind, width)
            expanded = hierarchy.expand()
            circuit, compiled = expanded.simplify(), synthesize(program)
            m = width.bit_length()
            for value in range(1 << width):
                expected = reference(kind, width, value)
                if (program.run(value) != [expected] or any(
                        impl.evaluate(bits(value, width)) != bits(expected, m)
                        for impl in (hierarchy, expanded, circuit, compiled))):
                    raise ValueError(f"{kind}<{width}> failed for input {value}")
            name = f"{kind.upper()}<{width}>"
            dataset = generate(name, width, m, ports=program.ports, program=program.spec, samples=1 << width)
            dataset.metadata["description"] = template.document["description"]
            checked = fitness(circuit, dataset)
            if not checked["verified_truth_table"]:
                raise ValueError(f"{name} was not exhaustively verified")
            prefix = folder / f"{kind}-{width}"
            write_json(prefix.with_suffix(".block.json"), hierarchy.to_dict())
            write_json(prefix.with_suffix(".circuit.json"), circuit.to_dict())
            write_json(prefix.with_suffix(".template.json"), program.spec)
            write_json(prefix.with_suffix(".vectors.json"), dataset.to_dict())
            prefix.with_suffix(".nand.txt").write_text(netlist(circuit, program, name), encoding="utf-8")
            summary.append({"name": name, "parameters": {"t": width}, "interface": program.ports,
                            "fitness": checked, "hierarchy": hierarchy.summary(),
                            "synthesis": {"method": "hierarchy-expansion-and-simplification", "version": 1},
                            "files": {key: f"{kind}-{width}.{suffix}" for key, suffix in (
                                ("block", "block.json"), ("circuit", "circuit.json"), ("template", "template.json"),
                                ("vectors", "vectors.json"), ("netlist", "nand.txt"))}})
            print(f"{name}: {len(circuit.gates)} NANDs, depth {circuit.depth}, {len(dataset.rows)} inputs verified")
        write_json(folder / "verification.json", summary)


if __name__ == "__main__":
    export()
