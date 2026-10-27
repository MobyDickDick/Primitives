"""Export six generative templates and verified t=1,2,4 instances.

Run: python -m tools.export_generative
"""
from functools import lru_cache
from pathlib import Path

from primitives.blocks import BlockBundle
from primitives.circuit import Circuit
from primitives.dataset import bits, generate
from primitives.library import fitness
from primitives.templates import Template
from primitives.synthesis import synthesize
from tools.export_blocks import inp, instance, out, ports
from tools.export_gt import bundle as greater_bundle
from tools.export_recursive_add import write_json


ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "examples/templates"
OUTPUT = ROOT / "examples/circuits"
KINDS = ("parity", "iszero", "reverse", "mux", "min", "max")
DESCRIPTIONS = {
    "parity": "Ungerade Parität: c=1 genau bei ungerader Anzahl gesetzter Bits. Rekursive XOR-Verknüpfung beider Hälften.",
    "iszero": "Nulltest: c=1 genau für a=0. Rekursive AND-Verknüpfung der Nulltests beider Hälften.",
    "reverse": "Kehrt die Reihenfolge aller t Bits um. Rekursive Bitumkehr beider Hälften mit anschliessendem Vertauschen; reine Verdrahtung ohne NAND-Gatter.",
    "mux": "Wählt für sel=0 den t-Bit-Wert a, für sel=1 den Wert b. Rekursive Halbierung mit gemeinsamem Auswahlbit.",
    "min": "Vorzeichenloses Minimum zweier t-Bit-Werte. Generative Komposition aus rekursivem GT<t> und MUX<t>.",
    "max": "Vorzeichenloses Maximum zweier t-Bit-Werte. Generative Komposition aus rekursivem GT<t> und MUX<t>.",
}


def definition(kind):
    inputs = [("a", "t")]
    if kind in ("mux", "min", "max"):
        inputs.append(("b", "t"))
    if kind == "mux":
        inputs.append(("sel", 1))
    return {
        "schema": 1, "kind": "template", "name": f"{kind.upper()}<t>",
        "description": DESCRIPTIONS[kind] + " t ist eine positive Zweierpotenz.",
        "parameters": ["t"],
        # MUX needs 2*t+1 inputs, so its largest power-of-two width is 32.
        "conditions": ["t >= 1", f"t <= {32 if kind == 'mux' else 64}", "is_power_of_two(t)"],
        "interface": ports(inputs, [("c", 1 if kind in ("parity", "iszero") else "t")]),
        "source": (TEMPLATES / f"recursive-{kind}.prim").read_text(encoding="utf-8"),
        "limits": {"steps": 100000, "iterations": 10000, "total_steps": 5000000},
    }


@lru_cache(maxsize=None)
def bundle(kind, width):
    program = Template(definition(kind)).instantiate({"t": width})
    name = f"{kind.upper()}<{width}>"
    if kind in ("min", "max"):
        greater, mux = greater_bundle(width), bundle("mux", width)
        a = [inp("a", i) for i in range(width)]
        b = [inp("b", i) for i in range(width)]
        first, second = (a, b) if kind == "min" else (b, a)
        nodes = [instance("greater", greater, a=a, b=b),
                 instance("select", mux, a=first, b=second, sel=[out("greater", "c")])]
        return BlockBundle.create({"name": name, "version": 1, "interface": program.ports,
                                   "nodes": nodes, "outputs": {"c": [out("select", "c", i) for i in range(width)]}},
                                  [greater, mux])
    if width == 1:
        return BlockBundle.from_circuit(name, synthesize(program), program.ports)
    k = width // 2
    child = bundle(kind, k)
    nodes = []
    for half, offset in (("lower", 0), ("upper", k)):
        connections = {p["name"]: ([inp("sel")] if p["name"] == "sel" else
                                   [inp(p["name"], offset + i) for i in range(k)])
                       for p in program.ports["inputs"]}
        nodes.append(instance(half, child, **connections))
    dependencies = [child]
    if kind in ("parity", "iszero"):
        # Explicit XOR / AND NAND implementations combine the two recursive results.
        circuit = (Circuit(2, ((0, 1), (0, 2), (1, 2), (3, 4)), (5,)) if kind == "parity"
                   else Circuit(2, ((0, 1), (2, 2)), (3,)))
        merge = BlockBundle.from_circuit("XOR" if kind == "parity" else "AND", circuit,
                                         ports([("a", 1), ("b", 1)], [("c", 1)]))
        dependencies.append(merge)
        nodes.append(instance("merge", merge, a=[out("lower", "c")], b=[out("upper", "c")]))
        result = [out("merge", "c")]
    else:
        halves = ("upper", "lower") if kind == "reverse" else ("lower", "upper")
        result = [out(half, "c", i) for half in halves for i in range(k)]
    return BlockBundle.create({"name": name, "version": 1, "interface": program.ports,
                               "nodes": nodes, "outputs": {"c": result}}, dependencies)


def reference(kind, width, value):
    """Independent integer oracle; never used to construct circuits."""
    mask = (1 << width) - 1
    a, b, sel = value & mask, (value >> width) & mask, value >> (2 * width)
    if kind == "parity":
        return a.bit_count() % 2
    if kind == "iszero":
        return int(a == 0)
    if kind == "reverse":
        return int(f"{a:0{width}b}"[::-1], 2)
    if kind == "mux":
        return b if sel else a
    return min(a, b) if kind == "min" else max(a, b)


def netlist(circuit, program, name):
    names = [f"{p['name']}{i}" for p in program.ports["inputs"] for i in range(p["bits"])]
    lines = [f"# {name}: flat NAND netlist; bit 0 is the LSB.", "# Inputs: " + ", ".join(names)]
    for number, (left, right) in enumerate(circuit.gates):
        lines.append(f"g{number} = NAND({names[left]}, {names[right]})")
        names.append(f"g{number}")
    for i, ref in enumerate(circuit.outputs):
        lines.append(f"c{i} = {names[ref]}")
    return "\n".join(lines) + "\n"


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
            n = sum(p["bits"] for p in program.ports["inputs"])
            m = sum(p["bits"] for p in program.ports["outputs"])
            for value in range(1 << n):
                expected = reference(kind, width, value)
                if (program.run(value) != [expected] or any(
                        impl.evaluate(bits(value, n)) != bits(expected, m)
                        for impl in (hierarchy, expanded, circuit, compiled))):
                    raise ValueError(f"{kind}<{width}> failed for input {value}")
            name = f"{kind.upper()}<{width}>"
            dataset = generate(name, n, m, ports=program.ports, program=program.spec, samples=1 << n)
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
                            "files": {k: f"{kind}-{width}.{suffix}" for k, suffix in (
                                ("block", "block.json"), ("circuit", "circuit.json"), ("template", "template.json"),
                                ("vectors", "vectors.json"), ("netlist", "nand.txt"))}})
            print(f"{name}: {len(circuit.gates)} NANDs, depth {circuit.depth}, {len(dataset.rows)} inputs verified")
        write_json(folder / "verification.json", summary)


if __name__ == "__main__":
    export()
