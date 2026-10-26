"""Export recursive MUL as executable templates, F-box packages and flat NANDs.

Run: python -m tools.export_recursive_mul
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
SOURCE = ROOT / "examples/templates/recursive-split-mul.prim"
OUTPUT = ROOT / "examples/circuits/recursive-split-mul"


def definition():
    return {
        "schema": 1, "kind": "template", "name": "Rekursive Multiplikation mit Fehlerbit",
        "description": "MUL<w>: vier volle rekursive Teilprodukte mit ADD und INC. Bei a*b >= 2**w: c=0, err=1; sonst c=a*b, err=0.",
        "parameters": ["w"],
        "conditions": ["w >= 1", "w <= 8", "is_power_of_two(w)"],
        "interface": ports([("a", "w"), ("b", "w")], [("c", "w"), ("err", 1)]),
        "source": SOURCE.read_text(encoding="utf-8"),
        "limits": {"steps": 100000, "iterations": 10000, "total_steps": 5000000},
    }


def helper(width, name, inputs, output_width, expression):
    document = definition()
    document["name"] = f"{name}<{width}>"
    document["interface"] = ports(inputs, [("value", output_width)])
    document["source"] = document["source"].rsplit("\nresult = bits(", 1)[0] + f"\nreturn {expression}\n"
    return Template(document).instantiate({"w": width})


def leaf(width, name, inputs, output_width, expression):
    program = helper(width, name, inputs, output_width, expression)
    return BlockBundle.from_circuit(f"{name}<{width}>", synthesize(program), program.ports)


@lru_cache(maxsize=None)
def raw_bundle(width):
    if type(width) is not int or width < 1 or width > 16 or width & (width - 1):
        raise ValueError("MUL braucht eine positive Zweierpotenz bis 16 als Breite.")
    if width == 1:
        return leaf(1, "MUL_raw", [("a", 1), ("b", 1)], 2, "MUL_raw<w>(a, b)")
    k = width // 2
    child = raw_bundle(k)
    adder = leaf(width, "ADD", [("a", width), ("b", width)], width + 1, "ADD<w>(a, b)")
    low_adder = leaf(width, "ADD_shifted", [("a", width), ("b", k)], width + 1,
                     "ADD<w>(a, pack([0] * (w // 2) + bits(b, w // 2)))")
    high_adder = leaf(width, "ADD_extended", [("a", width), ("b", k + 1)], width + 1,
                      "ADD<w>(a, pack(bits(b, w // 2 + 1) + [0] * (w // 2 - 1)))")
    inc = leaf(width, "INC", [("a", width), ("enable", 1)], width + 1, "INC<w>(a, enable)")
    refs = lambda node, start, stop: [out(node, "value", i) for i in range(start, stop)]
    nodes = []
    for name, a_start, b_start in (("p00", 0, 0), ("p01", 0, k), ("p10", k, 0), ("p11", k, k)):
        nodes.append(instance(name, child,
                              a=[inp("a", i) for i in range(a_start, a_start + k)],
                              b=[inp("b", i) for i in range(b_start, b_start + k)]))
    nodes.extend([
        instance("cross", adder, a=refs("p01", 0, width), b=refs("p10", 0, width)),
        instance("low", low_adder, a=refs("p00", 0, width), b=refs("cross", 0, k)),
        instance("high", high_adder, a=refs("p11", 0, width), b=refs("cross", k, width + 1)),
        instance("adjusted", inc, a=refs("high", 0, width), enable=refs("low", width, width + 1)),
    ])
    return BlockBundle.create({"name": f"MUL_raw<{width}>", "version": 1,
                               "interface": ports([("a", width), ("b", width)], [("value", 2 * width)]),
                               "nodes": nodes,
                               "outputs": {"value": refs("low", 0, width) + refs("adjusted", 0, width)}},
                              [child, adder, low_adder, high_adder, inc])


def bundle(width):
    raw = raw_bundle(width)
    check = leaf(width, "CHECK", [("product", 2 * width)], width + 1, "CHECK<w>(product)")
    return BlockBundle.create({"name": f"MUL<{width}>", "version": 1,
                               "interface": ports([("a", width), ("b", width)], [("c", width), ("err", 1)]),
                               "nodes": [instance("product", raw,
                                                  a=[inp("a", i) for i in range(width)],
                                                  b=[inp("b", i) for i in range(width)]),
                                         instance("checked", check,
                                                  product=[out("product", "value", i) for i in range(2 * width)])],
                               "outputs": {"c": [out("checked", "value", i) for i in range(width)],
                                           "err": [out("checked", "value", width)]}}, [raw, check])


def netlist(circuit, width):
    names = [f"a{i}" for i in range(width)] + [f"b{i}" for i in range(width)]
    lines = [f"# MUL<{width}>: flat NAND netlist; bit 0 is the LSB.", "# Inputs: " + ", ".join(names)]
    for number, (left, right) in enumerate(circuit.gates):
        lines.append(f"g{number} = NAND({names[left]}, {names[right]})")
        names.append(f"g{number}")
    for number, ref in enumerate(circuit.outputs):
        lines.append(f"{'c' + str(number) if number < width else 'err'} = {names[ref]}")
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
                value = a * b
                expected = value if value < (1 << width) else 1 << width
                x = a | b << width
                input_bits = bits(x, 2 * width)
                if (program.run(x) != [expected & ((1 << width) - 1), expected >> width]
                        or any(integer(c.evaluate(input_bits)) != expected for c in (expanded, circuit, compiled))
                        or integer(hierarchy.evaluate(input_bits)) != expected):
                    raise ValueError(f"MUL<{width}> failed for {a}, {b}")
        dataset = generate(f"MUL<{width}>", 2 * width, width + 1,
                           ports=program.ports, program=program.spec, samples=1 << (2 * width))
        checked = fitness(circuit, dataset)
        if not checked["verified_truth_table"]:
            raise ValueError(f"MUL<{width}> was not exhaustively verified")
        prefix = OUTPUT / f"mul-{width}"
        write_json(prefix.with_suffix(".block.json"), hierarchy.to_dict())
        write_json(prefix.with_suffix(".circuit.json"), circuit.to_dict())
        write_json(prefix.with_suffix(".template.json"), program.spec)
        write_json(prefix.with_suffix(".vectors.json"), dataset.to_dict())
        prefix.with_suffix(".nand.txt").write_text(netlist(circuit, width), encoding="utf-8")
        summary.append({"name": f"MUL<{width}>", "parameters": {"w": width},
                        "interface": program.ports, "fitness": checked,
                        "hierarchy": hierarchy.summary(),
                        "synthesis": {"method": "hierarchy-expansion-and-simplification", "version": 1},
                        "files": {kind: f"mul-{width}.{suffix}" for kind, suffix in (
                            ("block", "block.json"), ("circuit", "circuit.json"), ("template", "template.json"),
                            ("vectors", "vectors.json"), ("netlist", "nand.txt"))}})
        print(f"MUL<{width}>: {len(expanded.gates)} hierarchical / {len(circuit.gates)} flat NANDs, "
              f"{len(dataset.rows)} input pairs verified")
    write_json(OUTPUT / "verification.json", summary)


if __name__ == "__main__":
    export()
