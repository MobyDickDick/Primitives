"""Export conventional arithmetic for independently sized unsigned operands.

Run: python -m tools.export_standard_arithmetic
"""
from itertools import product
from pathlib import Path

from primitives.blocks import BlockBundle
from primitives.dataset import bits, generate
from primitives.library import fitness
from primitives.synthesis import synthesize
from primitives.templates import Template
from tools.export_templates import ADD, MUL, SUB
from tools.export_recursive_add import write_json


ROOT = Path(__file__).resolve().parents[1]
WIDTHS = (1, 2, 4)
KINDS = ("add", "sub", "mul", "div")
NAMES = {"add": "Standardaddition", "sub": "Standardsubtraktion",
         "mul": "Standardmultiplikation", "div": "Standarddivision"}
DESCRIPTIONS = {
    "add": "Ripple-Carry-Addition: vollständige Summe mit max(p,q)+1 Bits.",
    "sub": "Ripple-Borrow-Subtraktion: c=(a-b) modulo 2**max(p,q), borrow=1 genau bei a<b.",
    "mul": "Schiebe-Addier-Multiplikation aus AND-Teilprodukten: vollständiges Produkt mit p+q Bits.",
    "div": "Restoring-Division mit p festen Stufen: c=a//b, rest=a%b. Bei b=0: c=rest=valid=0, div0=1; sonst valid=1, div0=0.",
}

DIV = '''x = bits(a, p)
y = bits(b, q)
quotient = [0] * p
remainder = [0] * (q + 1)
for i in range(p - 1, -1, -1):
    remainder = [x[i]] + remainder[:q]
    difference = bits(subtract<q+1>(pack(remainder), b), q + 2)
    take = 1 ^ difference[q + 1]
    for j in range(q + 1):
        remainder[j] = (difference[j] & take) | (remainder[j] & (1 ^ take))
    quotient[i] = take
valid = 0
for i in range(q):
    valid = valid | y[i]
for i in range(p):
    quotient[i] = quotient[i] & valid
for i in range(q):
    remainder[i] = remainder[i] & valid
return pack(quotient), pack(remainder[:q]), valid, 1 ^ valid
'''


def definition(kind):
    # bits(a,w) and bits(b,w) zero-extend narrower inputs; this is wiring.
    width = "w = p if p >= q else q\n"
    sources = {
        "add": ADD + "\n" + width + "return add<w>(a, b)\n",
        "sub": SUB + "\n" + width + "difference = bits(subtract<w>(a, b), w + 1)\nreturn pack(difference[:w]), difference[w]\n",
        "mul": MUL + "\n" + width + "return pack(bits(multiply<w>(a, b), p + q))\n",
        "div": SUB + "\n" + DIV,
    }
    outputs = {
        "add": [("c", "max(p,q)+1")],
        "sub": [("c", "max(p,q)"), ("borrow", 1)],
        "mul": [("c", "p+q")],
        "div": [("c", "p"), ("rest", "q"), ("valid", 1), ("div0", 1)],
    }
    conditions = ["p >= 1", "q >= 1", "p <= 16", "q <= 16"]
    return {
        "schema": 1, "kind": "template", "name": f"{NAMES[kind]}<p,q>",
        "description": DESCRIPTIONS[kind] + " Vorzeichenlose Eingänge: a[p], b[q]; unabhängig wählbare Bitbreiten.",
        "parameters": ["p", "q"], "conditions": conditions,
        "interface": {"inputs": [{"name": "a", "bits": "p"}, {"name": "b", "bits": "q"}],
                      "outputs": [{"name": name, "bits": n} for name, n in outputs[kind]]},
        "source": sources[kind],
        "limits": {"steps": 100000, "iterations": 10000, "total_steps": 5000000},
    }


def reference(kind, a, b, p, q):
    """Integer oracle independent of bit-level construction."""
    if kind == "add":
        return [a + b]
    if kind == "sub":
        return [(a - b) % (1 << max(p, q)), int(a < b)]
    if kind == "mul":
        return [a * b]
    return [a // b, a % b, 1, 0] if b else [0, 0, 0, 1]


def netlist(circuit, ports, name):
    names = [f"{port['name']}{i}" for port in ports["inputs"] for i in range(port["bits"])]
    lines = [f"# {name}: flat NAND netlist; bit 0 is the LSB.", "# Inputs: " + ", ".join(names)]
    for i, (a, b) in enumerate(circuit.gates):
        lines.append(f"g{i} = NAND({names[a]}, {names[b]})")
        names.append(f"g{i}")
    for port in ports["outputs"]:
        for i in range(port["bits"]):
            lines.append(f"{port['name']}{i} = {names[circuit.outputs[port['offset'] + i]]}")
    return "\n".join(lines) + "\n"


def export():
    for kind in KINDS:
        template = Template(definition(kind))
        stem = ROOT / f"examples/templates/standard-{kind}"
        write_json(stem.with_suffix(".abstract.json"), template.to_dict())
        stem.with_suffix(".prim").write_text(template.document["source"], encoding="utf-8")
        folder = ROOT / f"examples/circuits/standard-{kind}"
        folder.mkdir(parents=True, exist_ok=True)
        reports = []
        for p, q in product(WIDTHS, repeat=2):
            program = template.instantiate({"p": p, "q": q})
            circuit = synthesize(program)
            name = f"{NAMES[kind]} ({p}/{q} Bit)"
            block = BlockBundle.from_circuit(name, circuit, program.ports)
            for a, b in product(range(1 << p), range(1 << q)):
                value = a | b << p
                expected = reference(kind, a, b, p, q)
                encoded = [digit for port, number in zip(program.ports["outputs"], expected)
                           for digit in bits(number, port["bits"])]
                if program.run(value) != expected or any(
                        impl.evaluate(bits(value, p + q)) != encoded for impl in (circuit, block)):
                    raise ValueError(f"{name} failed for {a}, {b}")
            dataset = generate(name, p + q, len(circuit.outputs), ports=program.ports,
                               program=program.spec, samples=1 << (p + q))
            dataset.metadata["description"] = template.document["description"]
            checked = fitness(circuit, dataset)
            if not checked["verified_truth_table"]:
                raise ValueError(f"{name} was not exhaustively verified")
            prefix = folder / f"{kind}-{p}-{q}"
            for suffix, document in (("circuit", circuit.to_dict()), ("block", block.to_dict()),
                                     ("template", program.spec), ("vectors", dataset.to_dict())):
                write_json(prefix.with_suffix(f".{suffix}.json"), document)
            prefix.with_suffix(".nand.txt").write_text(netlist(circuit, program.ports, name), encoding="utf-8")
            reports.append({"name": name, "parameters": program.parameters, "interface": program.ports,
                            "fitness": checked, "synthesis": {"method": "structural-bitwise", "version": 1}})
            print(f"{name}: {len(circuit.gates)} NANDs, {len(dataset.rows)} inputs verified")
        write_json(folder / "verification.json", reports)


if __name__ == "__main__":
    export()
