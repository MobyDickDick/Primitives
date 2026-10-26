"""Export checked split arithmetic and exhaustively verified small NAND instances.

Run: python -m tools.export_recursive_arithmetic
"""
from pathlib import Path

from primitives.dataset import bits, generate, integer
from primitives.library import fitness
from primitives.synthesis import synthesize
from primitives.templates import Template
from tools.export_recursive_add import write_json


ROOT = Path(__file__).resolve().parents[1]
VARIANTS = {
    "sub": ("recursive-split-sub", "Rekursive Subtraktion mit Borrow",
            "SUB<n>: rekursive Halbierung und bedingtes Dekrementieren. Bei a<b: c=0, err=1; sonst c=a-b, err=0."),
    "add-checked": ("recursive-split-add-checked", "Rekursive Addition mit Fehlerbit",
                    "ADD_checked<n>: rekursive Addition; bei a+b >= 2**n: c=0, err=1; sonst c=a+b, err=0."),
}


def definition(operation):
    stem, name, description = VARIANTS[operation]
    return {
        "schema": 1, "kind": "template", "name": name, "description": description,
        "parameters": ["n"],
        "conditions": ["n >= 1", "n <= 16", "is_power_of_two(n)"],
        "interface": {
            "inputs": [{"name": "a", "bits": "n"}, {"name": "b", "bits": "n"}],
            "outputs": [{"name": "c", "bits": "n"}, {"name": "err", "bits": 1}],
        },
        "source": (ROOT / "examples/templates" / f"{stem}.prim").read_text(encoding="utf-8"),
        "limits": {"steps": 100000, "iterations": 10000, "total_steps": 5000000},
    }


def netlist(circuit, width, operation):
    name = "SUB" if operation == "sub" else "ADD_checked"
    names = [f"a{i}" for i in range(width)] + [f"b{i}" for i in range(width)]
    lines = [f"# {name}<{width}>: flat NAND netlist; bit 0 is the LSB.",
             "# Inputs: " + ", ".join(names)]
    for number, (left, right) in enumerate(circuit.gates):
        name = f"g{number}"
        lines.append(f"{name} = NAND({names[left]}, {names[right]})")
        names.append(name)
    for number, ref in enumerate(circuit.outputs):
        label = f"c{number}" if number < width else "err"
        lines.append(f"{label} = {names[ref]}")
    return "\n".join(lines) + "\n"


def export():
    for operation, (stem, _, _) in VARIANTS.items():
        document = definition(operation)
        template = Template(document)
        write_json(ROOT / "examples/templates" / f"{stem}.abstract.json", template.to_dict())
        output = ROOT / "examples/circuits" / stem
        output.mkdir(parents=True, exist_ok=True)
        summary = []
        for width in (1, 2, 4):
            program = template.instantiate({"n": width})
            circuit = synthesize(program)
            for a in range(1 << width):
                for b in range(1 << width):
                    value = a - b if operation == "sub" else a + b
                    expected = value if 0 <= value < (1 << width) else 1 << width
                    x = a | (b << width)
                    if (program.run(x) != [expected & ((1 << width) - 1), expected >> width]
                            or integer(circuit.evaluate(bits(x, 2 * width))) != expected):
                        raise ValueError(f"{operation}<{width}> failed for {a}, {b}")
            dataset = generate(f"{operation}<{width}>", 2 * width, width + 1,
                               ports=program.ports, program=program.spec, samples=1 << (2 * width))
            checked = fitness(circuit, dataset)
            if not checked["verified_truth_table"]:
                raise ValueError(f"{operation}<{width}> was not exhaustively verified")
            prefix = output / f"{operation}-{width}"
            write_json(prefix.with_suffix(".circuit.json"), circuit.to_dict())
            write_json(prefix.with_suffix(".template.json"), program.spec)
            write_json(prefix.with_suffix(".vectors.json"), dataset.to_dict())
            prefix.with_suffix(".nand.txt").write_text(netlist(circuit, width, operation), encoding="utf-8")
            summary.append({"name": f"{operation}<{width}>", "parameters": {"n": width},
                            "interface": program.ports, "fitness": checked,
                            "synthesis": {"method": "structural-bitwise", "version": 1}})
            print(f"{operation}<{width}>: {len(circuit.gates)} NANDs, depth {circuit.depth}, {len(dataset.rows)} input pairs verified")
        write_json(output / "verification.json", summary)


if __name__ == "__main__":
    export()
