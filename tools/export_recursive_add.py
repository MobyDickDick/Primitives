"""Export the recursive split adder and its verified flat NAND instances.

Run from the repository root: python -m tools.export_recursive_add
The NAND topology is compiled from source before reference vectors are made.
"""
import json
from pathlib import Path

from primitives.dataset import bits, generate, integer
from primitives.library import fitness
from primitives.synthesis import synthesize
from primitives.templates import Template


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "examples/templates/recursive-split-add.prim"
OUTPUT = ROOT / "examples/circuits/recursive-split-add"


def definition():
    return {
        "schema": 1, "kind": "template", "name": "Rekursive Addition mit Inkrementierer",
        "description": "ADD<n>: unabhaengige rekursive Addition beider Haelften, danach bedingte rekursive Inkrementierung der oberen Summe. c=(a+b) modulo 2**n; err ist der Enduebertrag. Direkt nach NAND uebersetzbar.",
        "parameters": ["n"],
        "conditions": ["n >= 1", "n <= 16", "is_power_of_two(n)"],
        "interface": {
            "inputs": [{"name": "a", "bits": "n"}, {"name": "b", "bits": "n"}],
            "outputs": [{"name": "c", "bits": "n"}, {"name": "err", "bits": 1}],
        },
        "source": SOURCE.read_text(encoding="utf-8"),
        "limits": {"steps": 100000, "iterations": 10000, "total_steps": 5000000},
    }


def netlist(circuit, width):
    names = [f"a{i}" for i in range(width)] + [f"b{i}" for i in range(width)]
    lines = [f"# ADD<{width}>: flat NAND netlist; bit 0 is the LSB.",
             "# Inputs: " + ", ".join(names)]
    for number, (left, right) in enumerate(circuit.gates):
        name = f"g{number}"
        lines.append(f"{name} = NAND({names[left]}, {names[right]})")
        names.append(name)
    for number, ref in enumerate(circuit.outputs):
        label = f"c{number}" if number < width else "err"
        lines.append(f"{label} = {names[ref]}")
    return "\n".join(lines) + "\n"


def write_json(path, document):
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def export():
    document = definition()
    template = Template(document)
    write_json(SOURCE.with_suffix(".abstract.json"), template.to_dict())
    OUTPUT.mkdir(parents=True, exist_ok=True)
    summary = []
    for width in (1, 2, 4):
        program = template.instantiate({"n": width})
        circuit = synthesize(program)
        dataset = generate(f"ADD<{width}>", 2 * width, width + 1,
                           ports=program.ports, program=program.spec, samples=1 << (2 * width))
        # Check both executable source and generated wiring against independent arithmetic.
        for a in range(1 << width):
            for b in range(1 << width):
                x = a | (b << width)
                expected = [(a + b) % (1 << width), (a + b) >> width]
                if program.run(x) != expected or integer(circuit.evaluate(bits(x, 2 * width))) != a + b:
                    raise ValueError(f"ADD<{width}> failed for a={a}, b={b}")
        checked = fitness(circuit, dataset)
        if not checked["verified_truth_table"]:
            raise ValueError(f"ADD<{width}> was not exhaustively verified")
        prefix = OUTPUT / f"add-{width}"
        write_json(prefix.with_suffix(".circuit.json"), circuit.to_dict())
        write_json(prefix.with_suffix(".template.json"), program.spec)
        write_json(prefix.with_suffix(".vectors.json"), dataset.to_dict())
        prefix.with_suffix(".nand.txt").write_text(netlist(circuit, width), encoding="utf-8")
        summary.append({"name": f"ADD<{width}>", "parameters": {"n": width},
                        "interface": program.ports, "fitness": checked,
                        "synthesis": {"method": "structural-bitwise", "version": 1},
                        "files": {"circuit": f"add-{width}.circuit.json",
                                  "template": f"add-{width}.template.json",
                                  "vectors": f"add-{width}.vectors.json",
                                  "netlist": f"add-{width}.nand.txt"}})
        print(f"ADD<{width}>: {len(circuit.gates)} NANDs, depth {circuit.depth}, {len(dataset.rows)} input pairs verified")
    write_json(OUTPUT / "verification.json", summary)


if __name__ == "__main__":
    export()
