"""Export MSB-aligned recursive division and verified flat NAND networks.

Run: python -m tools.export_recursive_div
"""
from pathlib import Path

from primitives.dataset import bits, generate, integer
from primitives.library import fitness
from primitives.synthesis import synthesize
from primitives.templates import Template
from tools.export_recursive_add import write_json


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "examples/templates/recursive-msb-div.prim"
OUTPUT = ROOT / "examples/circuits/recursive-msb-div"


def definition():
    return {
        "schema": 1, "kind": "template", "name": "Rekursive Division mit MSB-Ausrichtung",
        "description": "DIV<w>: Divisor am höchsten Dividend-Bit ausrichten, gegebenenfalls eine Stelle zurück, subtrahieren und rekursiv fortsetzen. Bei b=0: c=0, err=1; sonst c=a//b, err=0. Feste azyklische NAND-Struktur.",
        "parameters": ["w"], "conditions": ["w >= 1", "w <= 8"],
        "interface": {
            "inputs": [{"name": "a", "bits": "w"}, {"name": "b", "bits": "w"}],
            "outputs": [{"name": "c", "bits": "w"}, {"name": "err", "bits": 1}],
        },
        "source": SOURCE.read_text(encoding="utf-8"),
        "limits": {"steps": 100000, "iterations": 10000, "total_steps": 5000000},
    }


def netlist(circuit, width):
    names = [f"a{i}" for i in range(width)] + [f"b{i}" for i in range(width)]
    lines = [f"# DIV<{width}>: MSB-aligned flat NAND netlist; bit 0 is the LSB.",
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
    reports = []
    for width in (1, 2, 3, 4):
        program = template.instantiate({"w": width})
        circuit = synthesize(program)
        for a in range(1 << width):
            for b in range(1 << width):
                expected = [a // b, 0] if b else [0, 1]
                encoded = expected[0] | expected[1] << width
                inputs = a | b << width
                if (program.run(inputs) != expected
                        or integer(circuit.evaluate(bits(inputs, 2 * width))) != encoded):
                    raise ValueError(f"DIV<{width}> failed for {a}, {b}")
        dataset = generate(f"DIV<{width}> MSB", 2 * width, width + 1,
                           ports=program.ports, program=program.spec, samples=1 << (2 * width))
        dataset.metadata["description"] = template.document["description"]
        checked = fitness(circuit, dataset)
        if not checked["verified_truth_table"]:
            raise ValueError(f"DIV<{width}> was not exhaustively verified")
        prefix = OUTPUT / f"div-{width}"
        write_json(prefix.with_suffix(".circuit.json"), circuit.to_dict())
        write_json(prefix.with_suffix(".template.json"), program.spec)
        write_json(prefix.with_suffix(".vectors.json"), dataset.to_dict())
        prefix.with_suffix(".nand.txt").write_text(netlist(circuit, width), encoding="utf-8")
        reports.append({"name": f"DIV<{width}>", "parameters": {"w": width},
                        "fitness": checked, "synthesis": {"method": "structural-bitwise", "version": 1}})
        print(f"DIV<{width}>: {len(circuit.gates)} NANDs, depth {circuit.depth}, {len(dataset.rows)} input pairs verified")
    write_json(OUTPUT / "verification.json", reports)


if __name__ == "__main__":
    export()
