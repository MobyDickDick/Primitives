"""Export recursive GreaterThan, nested F-boxes and verified flat NANDs.

Run: python -m tools.export_gt
"""
from functools import lru_cache
from pathlib import Path

from primitives.blocks import BlockBundle
from primitives.dataset import bits, generate, integer
from primitives.library import fitness
from primitives.synthesis import synthesize
from primitives.templates import Template
from tools.export_blocks import inp, instance, out, ports
from tools.export_equ import bundle as equality_bundle
from tools.export_recursive_add import write_json


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "examples/templates/recursive-gt.prim"
OUTPUT = ROOT / "examples/circuits/recursive-gt"


def definition():
    return {
        "schema": 1, "kind": "template", "name": "GT<t>",
        "description": "GreaterThan: vergleicht zwei vorzeichenlose t-Bit-Werte durch rekursive Halbierung. t=2**w mit ganzzahligem w>=0; c ist genau dann 1, wenn a>b. Basisfall: AND(a,NOT(b)). Upper<t>/Lower<t> liefern je t//2 Bits; Equal verwendet die EQU-Rekursion. GreaterThan<t> ist ein Alias für GT<t>.",
        "parameters": ["t"],
        "conditions": ["t >= 1", "t <= 64", "is_power_of_two(t)"],
        "interface": ports([("a", "t"), ("b", "t")], [("c", 1)]),
        "source": SOURCE.read_text(encoding="utf-8"),
        "limits": {"steps": 100000, "iterations": 10000, "total_steps": 5000000},
    }


@lru_cache(maxsize=None)
def bundle(width):
    program = Template(definition()).instantiate({"t": width})
    if width == 1:
        return BlockBundle.from_circuit("GT<1>", synthesize(program), program.ports)
    k = width // 2
    child, equality = bundle(k), equality_bundle(k)
    upper = {p: [inp(p, k + i) for i in range(k)] for p in ("a", "b")}
    lower = {p: [inp(p, i) for i in range(k)] for p in ("a", "b")}
    # hi OR (eq AND lo) = NAND(NOT(hi), NAND(eq,lo)).
    nodes = [instance("upper", child, **upper),
             instance("equal", equality, **upper),
             instance("lower", child, **lower),
             {"id": "not_upper", "type": "nand", "inputs": [out("upper", "c")] * 2},
             {"id": "not_lower_equal", "type": "nand", "inputs": [out("equal", "c"), out("lower", "c")]},
             {"id": "greater", "type": "nand", "inputs": [out("not_upper", "out"), out("not_lower_equal", "out")]}]
    return BlockBundle.create({"name": f"GT<{width}>", "version": 1,
                               "interface": program.ports, "nodes": nodes,
                               "outputs": {"c": [out("greater", "out")]}}, [child, equality])


def netlist(circuit, width):
    names = [f"a{i}" for i in range(width)] + [f"b{i}" for i in range(width)]
    lines = [f"# GT<{width}> (GreaterThan): flat NAND netlist; bit 0 is the LSB.",
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
        program = template.instantiate({"t": width})
        hierarchy = bundle(width)
        expanded = hierarchy.expand()
        circuit = expanded.simplify()
        compiled = synthesize(program)
        for a in range(1 << width):
            for b in range(1 << width):
                expected = int(a > b)
                inputs = bits(a | b << width, 2 * width)
                if (program.run(a | b << width) != [expected]
                        or any(integer(c.evaluate(inputs)) != expected
                               for c in (hierarchy, expanded, circuit, compiled))):
                    raise ValueError(f"GT<{width}> failed for a={a}, b={b}")
        dataset = generate(f"GT<{width}>", 2 * width, 1, ports=program.ports,
                           program=program.spec, samples=1 << (2 * width))
        dataset.metadata["description"] = template.document["description"]
        checked = fitness(circuit, dataset)
        if not checked["verified_truth_table"]:
            raise ValueError(f"GT<{width}> was not exhaustively verified")
        prefix = OUTPUT / f"gt-{width}"
        write_json(prefix.with_suffix(".block.json"), hierarchy.to_dict())
        write_json(prefix.with_suffix(".circuit.json"), circuit.to_dict())
        write_json(prefix.with_suffix(".template.json"), program.spec)
        write_json(prefix.with_suffix(".vectors.json"), dataset.to_dict())
        prefix.with_suffix(".nand.txt").write_text(netlist(circuit, width), encoding="utf-8")
        summary.append({"name": f"GT<{width}>", "parameters": {"t": width},
                        "interface": program.ports, "fitness": checked,
                        "hierarchy": hierarchy.summary(),
                        "synthesis": {"method": "hierarchy-expansion-and-simplification", "version": 1},
                        "files": {kind: f"gt-{width}.{suffix}" for kind, suffix in (
                            ("block", "block.json"), ("circuit", "circuit.json"), ("template", "template.json"),
                            ("vectors", "vectors.json"), ("netlist", "nand.txt"))}})
        print(f"GT<{width}>: {len(expanded.gates)} hierarchical / {len(circuit.gates)} flat NANDs, "
              f"depth {circuit.depth}, {len(dataset.rows)} input pairs verified")
    write_json(OUTPUT / "verification.json", summary)


if __name__ == "__main__":
    export()
