"""Export generative MUX/DEMUX for n=1,2,4 data and w=1,2,4 selector bits.

Run: python -m tools.export_routing
"""
from functools import lru_cache
from pathlib import Path

from primitives.blocks import BlockBundle
from primitives.dataset import bits, generate, integer
from primitives.library import fitness, write_json
from primitives.synthesis import synthesize
from primitives.templates import Template
from tools.export_blocks import inp, instance, out, ports


ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "examples/templates"
OUTPUT = ROOT / "examples/circuits"
KINDS = ("multiplexer", "demultiplexer")
WIDTHS = (1, 2, 4)
SELECTORS = (1, 2, 4)


def label(kind, n, w):
    return f"{'MUX' if kind == 'multiplexer' else 'DEMUX'}<{n},{w}>"


def definition(kind):
    if kind not in KINDS:
        raise ValueError(f"Unknown routing template: {kind}")
    mux = kind == "multiplexer"
    return {
        "schema": 1, "kind": "template", "name": label(kind, "n", "w"),
        "description": (
            "Multiplexer: c=a_b. Wählt aus 2**w Eingangskanälen den Kanal b mit n Datenbits. "
            if mux else
            "Demultiplexer: c_b=a, alle anderen Ausgangskanäle sind 0. Verteilt n Datenbits auf einen von 2**w Kanälen. "
        ) + "n ist die Datenbreite, w die Breite des Auswahlports b. "
            "Kanal j belegt Bits j*n bis (j+1)*n-1 im gepackten Port a (MUX) bzw. c (DEMUX); LSB-first.",
        "parameters": ["n", "w"],
        "conditions": ["n >= 1", "w >= 1", "w <= 7",
                       "n * (2 ** w) + w <= 128" if mux else "n * (2 ** w) <= 128",
                       "n + w <= 128"],
        "interface": ports([("a", "n * (2 ** w)" if mux else "n"), ("b", "w")],
                           [("c", "n" if mux else "n * (2 ** w)")]),
        "source": (TEMPLATES / f"recursive-{kind}.prim").read_text(encoding="utf-8"),
        "limits": {"steps": 100000, "iterations": 10000, "total_steps": 5000000},
    }


@lru_cache(maxsize=None)
def bundle(kind, n, w):
    program = Template(definition(kind)).instantiate({"n": n, "w": w})
    name = label(kind, n, w)
    if w == 1:
        return BlockBundle.from_circuit(name, synthesize(program), program.ports)
    child, stage = bundle(kind, n, w - 1), bundle(kind, n, 1)
    k = n * (2 ** (w - 1))
    selector = [inp("b", i) for i in range(w - 1)]
    if kind == "multiplexer":
        nodes = [instance(half, child, a=[inp("a", offset + i) for i in range(k)], b=selector)
                 for half, offset in (("lower", 0), ("upper", k))]
        nodes.append(instance("select", stage,
                              a=[out(half, "c", i) for half in ("lower", "upper") for i in range(n)],
                              b=[inp("b", w - 1)]))
        result = [out("select", "c", i) for i in range(n)]
    else:
        nodes = [instance("split", stage, a=[inp("a", i) for i in range(n)], b=[inp("b", w - 1)])]
        nodes.extend(instance(half, child, a=[out("split", "c", offset + i) for i in range(n)], b=selector)
                     for half, offset in (("lower", 0), ("upper", n)))
        result = [out(half, "c", i) for half in ("lower", "upper") for i in range(k)]
    return BlockBundle.create({"name": name, "version": 1, "interface": program.ports,
                               "nodes": nodes, "outputs": {"c": result}}, [child, stage])


def reference(kind, n, w, value):
    """Independent integer routing; never used to construct a NAND network."""
    data_bits = n * (2 ** w) if kind == "multiplexer" else n
    a = value % (1 << data_bits)
    b = value >> data_bits
    if kind == "multiplexer":
        return (a >> (n * b)) & ((1 << n) - 1)
    return a << (n * b)


def directed_inputs(kind, n, w):
    """Exercise every channel/data value and every source wire/selector pair."""
    channels = 1 << w
    data_bits = n * channels if kind == "multiplexer" else n
    mask = (1 << data_bits) - 1
    cases = {0, (1 << (data_bits + w)) - 1}
    for selected in range(channels):
        selector = selected << data_bits
        for data in range(1 << n):
            a = data << (n * selected) if kind == "multiplexer" else data
            cases.add(selector | a)
            if kind == "multiplexer":
                cases.add(selector | (mask ^ a))
        if kind == "multiplexer":
            for wire in range(data_bits):
                cases.add(selector | (1 << wire))
                cases.add(selector | (mask ^ (1 << wire)))
    return sorted(cases)


def netlist(circuit, program, name):
    names = [f"{p['name']}[{i}]" for p in program.ports["inputs"] for i in range(p["bits"])]
    lines = [f"# {name}: flat NAND netlist; LSB-first.", "# Inputs: " + ", ".join(names)]
    for i, (left, right) in enumerate(circuit.gates):
        lines.append(f"g{i} = NAND({names[left]}, {names[right]})")
        names.append(f"g{i}")
    lines.extend(f"c[{i}] = {names[ref]}" for i, ref in enumerate(circuit.outputs))
    return "\n".join(lines) + "\n"


def export():
    for kind in KINDS:
        template = Template(definition(kind))
        write_json(TEMPLATES / f"recursive-{kind}.abstract.json", template.to_dict())
        folder = OUTPUT / f"recursive-{kind}"
        folder.mkdir(parents=True, exist_ok=True)
        reports = []
        for n in WIDTHS:
            for w in SELECTORS:
                name = label(kind, n, w)
                program = template.instantiate({"n": n, "w": w})
                hierarchy = bundle(kind, n, w)
                expanded, compiled = hierarchy.expand(), synthesize(program)
                circuit = expanded.simplify()
                inputs, outputs = circuit.inputs, len(circuit.outputs)
                directed = directed_inputs(kind, n, w)
                # Large input spaces stay sampled and retain that status in the library.
                count = (1 << inputs) if inputs <= 12 else 256
                dataset = generate(name, inputs, outputs, ports=program.ports, program=program.spec,
                                   samples=count, edge_inputs=directed[::max(1, len(directed) // 128)][:128])
                dataset.metadata["description"] = template.document["description"]
                cases = set(directed) | {integer(row[:inputs]) for row in dataset.rows}
                for value in sorted(cases):
                    expected = reference(kind, n, w, value)
                    if (program.run(value) != [expected] or any(
                            impl.evaluate(bits(value, inputs)) != bits(expected, outputs)
                            for impl in (hierarchy, expanded, circuit, compiled))):
                        raise ValueError(f"{name} failed for input {value}")
                checked = fitness(circuit, dataset)
                if not checked["exact_on_dataset"]:
                    raise ValueError(f"{name} failed dataset verification")
                prefix = folder / f"{kind}-{n}-{w}"
                write_json(prefix.with_suffix(".template.json"), program.spec)
                write_json(prefix.with_suffix(".block.json"), hierarchy.to_dict())
                write_json(prefix.with_suffix(".circuit.json"), circuit.to_dict())
                write_json(prefix.with_suffix(".vectors.json"), dataset.to_dict())
                prefix.with_suffix(".nand.txt").write_text(netlist(circuit, program, name), encoding="utf-8")
                reports.append({"name": name, "parameters": {"n": n, "w": w}, "channels": 1 << w,
                                "interface": program.ports, "fitness": checked, "hierarchy": hierarchy.summary(),
                                "verification": {"exhaustive": dataset.exhaustive, "dataset_rows": len(dataset.rows),
                                                 "independent_cases": len(cases), "directed_cases": len(directed)},
                                "synthesis": {"method": "hierarchy-expansion-and-simplification", "version": 1},
                                "files": {key: f"{prefix.name}.{suffix}" for key, suffix in (
                                    ("template", "template.json"), ("block", "block.json"),
                                    ("circuit", "circuit.json"), ("vectors", "vectors.json"), ("netlist", "nand.txt"))}})
                print(f"{name}: {len(circuit.gates)} NANDs, {len(cases)} inputs checked, "
                      f"{'exhaustive' if dataset.exhaustive else 'sampled'}", flush=True)
        write_json(folder / "verification.json", reports)


if __name__ == "__main__":
    export()
