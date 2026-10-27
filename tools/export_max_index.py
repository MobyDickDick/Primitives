"""Export m<t>, recursive F-boxes and exhaustively verified NAND instances.

Run: python -m tools.export_max_index
"""
from functools import lru_cache
from pathlib import Path

from primitives.blocks import BlockBundle
from primitives.dataset import bits, generate, integer
from primitives.library import fitness
from primitives.synthesis import synthesize
from primitives.templates import Template
from tools.export_blocks import inp, instance, out, ports
from tools.export_recursive_add import write_json


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "examples/templates/recursive-max-index.prim"
OUTPUT = ROOT / "examples/circuits/recursive-max-index"


def definition():
    return {
        "schema": 1, "kind": "template", "name": "m<t>",
        "description": "Maximaler Index eines gesetzten Bits durch rekursive Halbierung. t=2**w Eingangsbits, t Indexbits c und err. a=0 liefert [0,1], sonst [floor(log2(a)),0]. Der Offset der oberen Hälfte ist t//2; die Auswahl wird als NAND-Multiplexer verdrahtet.",
        "parameters": ["t"],
        "conditions": ["t >= 1", "t <= 16", "is_power_of_two(t)"],
        "interface": ports([("a", "t")], [("c", "t"), ("err", 1)]),
        "source": SOURCE.read_text(encoding="utf-8"),
        "limits": {"steps": 100000, "iterations": 10000, "total_steps": 5000000},
    }


@lru_cache(maxsize=None)
def bundle(width):
    program = Template(definition()).instantiate({"t": width})
    if width == 1:
        return BlockBundle.from_circuit("m<1>", synthesize(program), program.ports)
    k = width // 2
    w = width.bit_length() - 1
    child = bundle(k)
    nodes = [instance("lower", child, a=[inp("a", i) for i in range(k)]),
             instance("upper", child, a=[inp("a", k + i) for i in range(k)])]

    def nand(name, left, right):
        nodes.append({"id": name, "type": "nand", "inputs": [left, right]})
        return out(name, "out")

    lo_zero, hi_zero = out("lower", "err"), out("upper", "err")
    select = nand("select", hi_zero, hi_zero)
    index = []
    for i in range(w - 1):
        upper = nand(f"upper{i}", select, out("upper", "c", i))
        lower = nand(f"lower{i}", hi_zero, out("lower", "c", i))
        index.append(nand(f"index{i}", upper, lower))
    index.append(select)
    # The last child index bit is always zero, including the t=1 base case.
    index.extend([out("lower", "c", k - 1)] * (width - w))
    nonzero = nand("nonzero", lo_zero, hi_zero)
    error = nand("error", nonzero, nonzero)
    return BlockBundle.create({"name": f"m<{width}>", "version": 1,
                               "interface": program.ports, "nodes": nodes,
                               "outputs": {"c": index, "err": [error]}}, [child])


def netlist(circuit, width):
    names = [f"a{i}" for i in range(width)]
    lines = [f"# m<{width}>: flat NAND netlist; bit 0 is the LSB.",
             "# Outputs: c0..c" + str(width - 1) + ", err; a=0 -> [0,1].",
             "# Inputs: " + ", ".join(names)]
    for number, (left, right) in enumerate(circuit.gates):
        lines.append(f"g{number} = NAND({names[left]}, {names[right]})")
        names.append(f"g{number}")
    for number, ref in enumerate(circuit.outputs):
        label = f"c{number}" if number < width else "err"
        lines.append(f"{label} = {names[ref]}")
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
            expected = [max(0, a.bit_length() - 1), int(a == 0)]
            packed = expected[0] | expected[1] << width
            if (program.run(a) != expected
                    or any(integer(c.evaluate(bits(a, width))) != packed
                           for c in (hierarchy, expanded, circuit, compiled))):
                raise ValueError(f"m<{width}> failed for a={a}")
        dataset = generate(f"m<{width}>", width, width + 1, ports=program.ports,
                           program=program.spec, samples=1 << width)
        dataset.metadata["description"] = template.document["description"]
        checked = fitness(circuit, dataset)
        if not checked["verified_truth_table"]:
            raise ValueError(f"m<{width}> was not exhaustively verified")
        prefix = OUTPUT / f"m-{width}"
        write_json(prefix.with_suffix(".block.json"), hierarchy.to_dict())
        write_json(prefix.with_suffix(".circuit.json"), circuit.to_dict())
        write_json(prefix.with_suffix(".template.json"), program.spec)
        write_json(prefix.with_suffix(".vectors.json"), dataset.to_dict())
        prefix.with_suffix(".nand.txt").write_text(netlist(circuit, width), encoding="utf-8")
        summary.append({"name": f"m<{width}>", "parameters": {"t": width},
                        "interface": program.ports, "fitness": checked,
                        "hierarchy": hierarchy.summary(),
                        "synthesis": {"method": "hierarchy-expansion-and-simplification", "version": 1},
                        "files": {kind: f"m-{width}.{suffix}" for kind, suffix in (
                            ("block", "block.json"), ("circuit", "circuit.json"),
                            ("template", "template.json"), ("vectors", "vectors.json"),
                            ("netlist", "nand.txt"))}})
        print(f"m<{width}>: {len(expanded.gates)} hierarchical / {len(circuit.gates)} flat NANDs, "
              f"depth {circuit.depth}, {len(dataset.rows)} inputs verified")
    write_json(OUTPUT / "verification.json", summary)


if __name__ == "__main__":
    export()
