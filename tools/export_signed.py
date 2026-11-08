"""Export and independently verify GEN-09: python -m tools.export_signed."""
from functools import lru_cache

from primitives.blocks import BlockBundle
from primitives.dataset import Dataset, bits
from primitives.library import fitness
from primitives.synthesis import synthesize
from primitives.templates import Template
from tools.export_blocks import inp, instance, out, ports
from tools.export_generative import netlist
from tools.export_parallel_add import ROOT, TEMPLATES, WIDTHS, write_json


KINDS = ("sign", "neg", "abs")
OUTPUT = ROOT / "examples/circuits/signed"


def definition(kind):
    semantics = {
        "sign": "negative=1 genau für negative Werte, auch bei null 0. 1<=t<=128.",
        "neg": "c=-signed(a) modulo 2**t; overflow=1 genau beim kleinsten negativen Wert. 1<=t<=127.",
        "abs": "c=abs(signed(a)) modulo 2**t; overflow=1 genau beim kleinsten negativen Wert. 1<=t<=127.",
    }[kind]
    return {
        "schema": 1, "kind": "template", "name": f"{kind.upper()}<t>",
        "description": "Zweierkomplement, LSB-first. " + semantics +
            " NEG/ABS behalten beim Overflow das Eingangsbitmuster; c ist signed. "
            "NAND-Netze/F-Boxen maximal 512 Gatter.",
        "parameters": ["t"], "conditions": ["t >= 1", f"t <= {128 if kind == 'sign' else 127}"],
        "interface": ports([("a", "t")], [("negative", 1)] if kind == "sign" else [("c", "t"), ("overflow", 1)]),
        "source": (TEMPLATES / f"signed-{kind}.prim").read_text(encoding="utf-8"),
        "limits": {"steps": 100000, "iterations": 10000, "total_steps": 5000000},
    }


def component(kind, width, name, interface, call):
    document = definition(kind)
    document.update(name=name, interface=interface)
    document["source"] = document["source"].split("# Ergebnisports", 1)[0] + call + "\n"
    return Template(document).instantiate({"t": width})


@lru_cache(maxsize=None)
def bundle(kind, width):
    program = Template(definition(kind)).instantiate({"t": width})
    name = f"{kind.upper()}<{width}>"
    if kind == "sign":
        return BlockBundle.from_circuit(name, synthesize(program), program.ports)
    flip = "1" if kind == "neg" else f"bits(a, {width})[{width - 1}]"
    arithmetic = component(kind, width, f"{kind.upper()}_value<{width}>",
                           ports([("a", width)], [("c", width)]),
                           f"return FlipAddOne<{width}>(a, {flip})")
    status = component(kind, width, f"MinNegative<{width}>",
                       ports([("a", width)], [("overflow", 1)]),
                       f"return MinNegative<{width}>(a)")
    value = BlockBundle.from_circuit(f"{kind.upper()}_value<{width}>", synthesize(arithmetic), arithmetic.ports)
    overflow = BlockBundle.from_circuit(f"MinNegative<{width}>", synthesize(status), status.ports)
    inputs = [inp("a", i) for i in range(width)]
    return BlockBundle.create({"name": name, "version": 1, "interface": program.ports,
        "nodes": [instance("arithmetic", value, a=inputs), instance("overflow", overflow, a=inputs)],
        "outputs": {"c": [out("arithmetic", "c", i) for i in range(width)],
                    "overflow": [out("overflow", "overflow")]}}, [value, overflow])


def reference(kind, value, width):
    """Independent integer oracle; values crossing the port remain raw bit words."""
    signed = value if value < 1 << (width - 1) else value - (1 << width)
    if kind == "sign":
        return [int(signed < 0)]
    result = -signed if kind == "neg" else abs(signed)
    return [result % (1 << width), int(result >= 1 << (width - 1))]


def export():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    reports = []
    for kind in KINDS:
        template = Template(definition(kind))
        write_json(TEMPLATES / f"signed-{kind}.abstract.json", template.to_dict())
        for width in WIDTHS:
            name = f"{kind.upper()}<{width}>"
            program = template.instantiate({"t": width})
            hierarchy = bundle(kind, width)
            expanded = hierarchy.expand()
            circuit, compiled = expanded.simplify(), synthesize(program)
            rows = []
            for value in range(1 << width):
                expected = reference(kind, value, width)
                inputs = bits(value, width)
                outputs = expected if kind == "sign" else bits(expected[0], width) + [expected[1]]
                if program.run(value) != expected or any(
                        impl.evaluate(inputs) != outputs for impl in (hierarchy, expanded, circuit, compiled)):
                    raise ValueError(f"{name} failed for a={value}")
                rows.append(inputs + outputs)
            dataset = Dataset(name, width, 1 if kind == "sign" else width + 1, rows,
                {"program": program.spec, "interface": program.ports, "description": template.document["description"]})
            checked = fitness(circuit, dataset)
            if not checked["verified_truth_table"]:
                raise ValueError("Export requires a fully verified truth table")
            prefix = OUTPUT / f"{kind}-{width}"
            for suffix, document in (("block", hierarchy.to_dict()), ("circuit", circuit.to_dict()),
                                     ("template", program.spec), ("vectors", dataset.to_dict())):
                write_json(prefix.with_suffix(f".{suffix}.json"), document)
            prefix.with_suffix(".nand.txt").write_text(netlist(circuit, program, name), encoding="utf-8", newline="\n")
            reports.append({"name": name, "kind": kind, "parameters": {"t": width},
                "interface": program.ports, "fitness": checked, "hierarchy": hierarchy.summary(),
                "synthesis": {"method": "hierarchy-expansion-and-simplification", "version": 1}})
            print(f"{name}: {len(circuit.gates)} NANDs, depth {circuit.depth}, {len(rows)} inputs verified", flush=True)
    write_json(OUTPUT / "verification.json", reports)


if __name__ == "__main__":
    export()
