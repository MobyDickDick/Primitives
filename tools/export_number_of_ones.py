"""Export recursive population counts, nested F-boxes and verified flat NANDs.

Run: python -m tools.export_number_of_ones
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
SOURCE = ROOT / "examples/templates/recursive-number-of-ones.prim"
OUTPUT = ROOT / "examples/circuits/recursive-number-of-ones"


def definition():
    return {
        "schema": 1, "kind": "template", "name": "NumberOfOnes<w>",
        "description": "Zählt rekursiv die Einsen in w Bits. w ist eine positive Zweierpotenz; c hat LOG2(w)+1 Bits. Vollständige Addition der beiden Teilzählungen einschliesslich Übertrag.",
        "parameters": ["w"],
        "conditions": ["w >= 1", "w <= 32", "is_power_of_two(w)"],
        "interface": ports([("a", "w")], [("c", "LOG2(w)+1")]),
        "source": SOURCE.read_text(encoding="utf-8"),
        "limits": {"steps": 100000, "iterations": 10000, "total_steps": 5000000},
    }


def adder_program(width):
    document = definition()
    document["name"] = f"ADD_count<{width}>"
    document["interface"] = ports([("a", width), ("b", width)], [("value", width + 1)])
    document["source"] = document["source"].rsplit("\nreturn NumberOfOnes", 1)[0] + f"\nreturn ADD_count<{width}>(a, b)\n"
    return Template(document).instantiate({"w": 1})


@lru_cache(maxsize=None)
def bundle(width):
    program = Template(definition()).instantiate({"w": width})
    if width == 1:
        return BlockBundle.from_circuit("NumberOfOnes<1>", synthesize(program), program.ports)
    k = width // 2
    r = width.bit_length() - 1
    child = bundle(k)
    adder = adder_program(r)
    add = BlockBundle.from_circuit(f"ADD_count<{r}>", synthesize(adder), adder.ports)
    # LOWER/HIGHER are bit wiring and need no gates.
    nodes = [instance("lower", child, a=[inp("a", i) for i in range(k)]),
             instance("higher", child, a=[inp("a", k + i) for i in range(k)]),
             instance("sum", add,
                      a=[out("lower", "c", i) for i in range(r)],
                      b=[out("higher", "c", i) for i in range(r)])]
    return BlockBundle.create({"name": f"NumberOfOnes<{width}>", "version": 1,
                               "interface": program.ports, "nodes": nodes,
                               "outputs": {"c": [out("sum", "value", i) for i in range(r + 1)]}},
                              [child, add])


def netlist(circuit, width):
    names = [f"a{i}" for i in range(width)]
    lines = [f"# NumberOfOnes<{width}>: flat NAND netlist; bit 0 is the LSB.",
             "# Inputs: " + ", ".join(names)]
    for number, (left, right) in enumerate(circuit.gates):
        lines.append(f"g{number} = NAND({names[left]}, {names[right]})")
        names.append(f"g{number}")
    for number, ref in enumerate(circuit.outputs):
        lines.append(f"c{number} = {names[ref]}")
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
            expected = a.bit_count()
            inputs = bits(a, width)
            if (program.run(a) != [expected]
                    or any(integer(c.evaluate(inputs)) != expected
                           for c in (hierarchy, expanded, circuit, compiled))):
                raise ValueError(f"NumberOfOnes<{width}> failed for a={a}")
        dataset = generate(f"NumberOfOnes<{width}>", width, width.bit_length(),
                           ports=program.ports, program=program.spec, samples=1 << width)
        dataset.metadata["description"] = template.document["description"]
        checked = fitness(circuit, dataset)
        if not checked["verified_truth_table"]:
            raise ValueError(f"NumberOfOnes<{width}> was not exhaustively verified")
        prefix = OUTPUT / f"number-of-ones-{width}"
        write_json(prefix.with_suffix(".block.json"), hierarchy.to_dict())
        write_json(prefix.with_suffix(".circuit.json"), circuit.to_dict())
        write_json(prefix.with_suffix(".template.json"), program.spec)
        write_json(prefix.with_suffix(".vectors.json"), dataset.to_dict())
        prefix.with_suffix(".nand.txt").write_text(netlist(circuit, width), encoding="utf-8")
        summary.append({"name": f"NumberOfOnes<{width}>", "parameters": {"w": width},
                        "interface": program.ports, "fitness": checked,
                        "hierarchy": hierarchy.summary(),
                        "synthesis": {"method": "hierarchy-expansion-and-simplification", "version": 1},
                        "files": {kind: f"number-of-ones-{width}.{suffix}" for kind, suffix in (
                            ("block", "block.json"), ("circuit", "circuit.json"), ("template", "template.json"),
                            ("vectors", "vectors.json"), ("netlist", "nand.txt"))}})
        print(f"NumberOfOnes<{width}>: {len(expanded.gates)} hierarchical / {len(circuit.gates)} flat NANDs, "
              f"depth {circuit.depth}, {len(dataset.rows)} inputs verified")
    write_json(OUTPUT / "verification.json", summary)


if __name__ == "__main__":
    export()
