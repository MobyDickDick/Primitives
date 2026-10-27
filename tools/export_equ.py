"""Export recursive equality, nested F-boxes and verified flat NANDs.

Run: python -m tools.export_equ
"""
from functools import lru_cache
from pathlib import Path

from primitives.blocks import BlockBundle
from primitives.circuit import Circuit
from primitives.dataset import bits, generate, integer
from primitives.library import fitness
from primitives.synthesis import synthesize
from primitives.templates import Template
from tools.export_blocks import inp, instance, out, ports
from tools.export_recursive_add import write_json


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "examples/templates/recursive-equ.prim"
OUTPUT = ROOT / "examples/circuits/recursive-equ"


def definition():
    return {
        "schema": 1, "kind": "template", "name": "EQU<w>",
        "description": "Vergleicht zwei w-Bit-Werte durch rekursive Halbierung. w ist eine positive Zweierpotenz; c ist genau dann 1, wenn a und b gleich sind. Basisfall: NOT(XOR(a,b)). Upper<w>/Lower<w> liefern je w//2 Bits.",
        "parameters": ["w"],
        "conditions": ["w >= 1", "w <= 64", "is_power_of_two(w)"],
        "interface": ports([("a", "w"), ("b", "w")], [("c", 1)]),
        "source": SOURCE.read_text(encoding="utf-8"),
        "limits": {"steps": 100000, "iterations": 10000, "total_steps": 5000000},
    }


@lru_cache(maxsize=None)
def bundle(width):
    program = Template(definition()).instantiate({"w": width})
    if width == 1:
        return BlockBundle.from_circuit("EQU<1>", synthesize(program), program.ports)
    k = width // 2
    child = bundle(k)
    conjunction = BlockBundle.from_circuit("AND", Circuit(2, ((0, 1), (2, 2)), (3,)),
                                          ports([("a", 1), ("b", 1)], [("value", 1)]))
    # Upper/Lower only select wires; both halves are compared in parallel.
    nodes = [instance("upper", child, **{p: [inp(p, k + i) for i in range(k)] for p in ("a", "b")}),
             instance("lower", child, **{p: [inp(p, i) for i in range(k)] for p in ("a", "b")}),
             instance("equal", conjunction, a=[out("upper", "c")], b=[out("lower", "c")])]
    return BlockBundle.create({"name": f"EQU<{width}>", "version": 1,
                               "interface": program.ports, "nodes": nodes,
                               "outputs": {"c": [out("equal", "value")]}}, [child, conjunction])


def netlist(circuit, width):
    names = [f"a{i}" for i in range(width)] + [f"b{i}" for i in range(width)]
    lines = [f"# EQU<{width}>: flat NAND netlist; bit 0 is the LSB.",
             "# Inputs: " + ", ".join(names)]
    for number, (left, right) in enumerate(circuit.gates):
        lines.append(f"g{number} = NAND({names[left]}, {names[right]})")
        names.append(f"g{number}")
    lines.append(f"c = {names[circuit.outputs[0]]}")
    return "\n".join(lines) + "\n"


def export():
    template = Template(definition())
    write_json(SOURCE.with_suffix(".abstract.json"), template.to_dict())
    OUTPUT.mkdir(parents=True, exist_ok=True)
    summary = []
    for width in (1, 2, 4):
        program = template.instantiate({"w": width})
        hierarchy = bundle(width)
        expanded = hierarchy.expand()
        circuit = expanded.simplify()
        compiled = synthesize(program)
        for a in range(1 << width):
            for b in range(1 << width):
                expected = int(a == b)
                inputs = bits(a | b << width, 2 * width)
                if (program.run(a | b << width) != [expected]
                        or any(integer(c.evaluate(inputs)) != expected
                               for c in (hierarchy, expanded, circuit, compiled))):
                    raise ValueError(f"EQU<{width}> failed for a={a}, b={b}")
        dataset = generate(f"EQU<{width}>", 2 * width, 1, ports=program.ports,
                           program=program.spec, samples=1 << (2 * width))
        dataset.metadata["description"] = template.document["description"]
        checked = fitness(circuit, dataset)
        if not checked["verified_truth_table"]:
            raise ValueError(f"EQU<{width}> was not exhaustively verified")
        prefix = OUTPUT / f"equ-{width}"
        write_json(prefix.with_suffix(".block.json"), hierarchy.to_dict())
        write_json(prefix.with_suffix(".circuit.json"), circuit.to_dict())
        write_json(prefix.with_suffix(".template.json"), program.spec)
        write_json(prefix.with_suffix(".vectors.json"), dataset.to_dict())
        prefix.with_suffix(".nand.txt").write_text(netlist(circuit, width), encoding="utf-8")
        summary.append({"name": f"EQU<{width}>", "parameters": {"w": width},
                        "interface": program.ports, "fitness": checked,
                        "hierarchy": hierarchy.summary(),
                        "synthesis": {"method": "hierarchy-expansion-and-simplification", "version": 1},
                        "files": {kind: f"equ-{width}.{suffix}" for kind, suffix in (
                            ("block", "block.json"), ("circuit", "circuit.json"), ("template", "template.json"),
                            ("vectors", "vectors.json"), ("netlist", "nand.txt"))}})
        print(f"EQU<{width}>: {len(expanded.gates)} hierarchical / {len(circuit.gates)} flat NANDs, "
              f"depth {circuit.depth}, {len(dataset.rows)} input pairs verified")
    write_json(OUTPUT / "verification.json", summary)


if __name__ == "__main__":
    export()
