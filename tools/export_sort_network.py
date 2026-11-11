"""Export and independently verify GEN-12: python -m tools.export_sort_network."""
from functools import lru_cache

from primitives.blocks import BlockBundle
from primitives.dataset import Dataset, bits
from primitives.library import fitness
from primitives.synthesis import synthesize
from primitives.templates import Template
from tools.export_blocks import inp, instance, out, ports
from tools.export_generative import netlist
from tools.export_parallel_add import ROOT, TEMPLATES, write_json
from tools.export_structured import bundle as structured_bundle


CASES = ((1, 1), (1, 2), (1, 4), (2, 1), (2, 2))
OUTPUT = ROOT / "examples/circuits/sort-network"


def definition():
    return {
        "schema": 1, "kind": "template", "name": "SORT_NET<k,n>",
        "description": "Aufsteigendes bitonisches Sortiernetz aus SORT2: 2**k unsigned "
            "Kanäle zu je n Bits. Kanal i belegt a[i*n:(i+1)*n], LSB-first; "
            "c hat dieselbe Belegung und erhält das Eingabemultiset einschliesslich Duplikaten. "
            "k=0 ist die Identität; n ist eine Zweierpotenz bis 64, n*2**k<=128. "
            "Feste Vergleichsstufen ohne datenabhängige Verdrahtung. NAND-Netze/F-Boxen "
            "maximal 512 Gatter; grössere Eingaberäume nur als Stichprobe prüfen.",
        "parameters": ["k", "n"],
        "conditions": ["k >= 0", "k <= 7", "n >= 1", "n <= 64",
                       "is_power_of_two(n)", "n * 2**k <= 128"],
        "interface": ports([("a", "n*2**k")], [("c", "n*2**k")]),
        "source": (TEMPLATES / "sort-network.prim").read_text(encoding="utf-8"),
        "limits": {"steps": 100000, "iterations": 10000, "total_steps": 5000000},
    }


@lru_cache(maxsize=None)
def bundle(k, n):
    program = Template(definition()).instantiate({"k": k, "n": n})
    channels = 2**k
    wires = [[inp("a", channel*n+bit) for bit in range(n)] for channel in range(channels)]
    nodes = []
    sorter = structured_bundle("sort2", n) if k else None
    # Build the same fixed bitonic topology with visible SORT2 sub-boxes.
    size = 2
    while size <= channels:
        distance = size // 2
        while distance:
            for i in range(channels):
                j = i ^ distance
                if i < j:
                    name = f"s{size}_d{distance}_c{i}"
                    nodes.append(instance(name, sorter, a=wires[i], b=wires[j]))
                    lo = [out(name, "lo", bit) for bit in range(n)]
                    hi = [out(name, "hi", bit) for bit in range(n)]
                    wires[i], wires[j] = (lo, hi) if i & size == 0 else (hi, lo)
            distance //= 2
        size *= 2
    return BlockBundle.create({"name": f"SORT_NET<{k},{n}>", "version": 1,
        "interface": program.ports, "nodes": nodes,
        "outputs": {"c": [ref for channel in wires for ref in channel]}}, [sorter] if sorter else [])


def reference(value, k, n):
    """Integer sorting, independent of the comparator network and its schedule."""
    values = sorted((value >> (i*n)) & ((1 << n)-1) for i in range(2**k))
    return sum(item << (i*n) for i, item in enumerate(values))


def export():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    template = Template(definition())
    write_json(TEMPLATES / "sort-network.abstract.json", template.to_dict())
    reports = []
    for k, n in CASES:
        name = f"SORT_NET<{k},{n}>"
        program = template.instantiate({"k": k, "n": n})
        hierarchy = bundle(k, n)
        expanded, compiled = hierarchy.expand(), synthesize(program)
        circuit = expanded.simplify()
        width = n*2**k
        rows = []
        for value in range(1 << width):
            wanted = reference(value, k, n)
            inputs, outputs = bits(value, width), bits(wanted, width)
            if program.run(value) != [wanted] or any(impl.evaluate(inputs) != outputs
                    for impl in (hierarchy, expanded, circuit, compiled)):
                raise ValueError(f"{name} failed for {value}")
            rows.append(inputs + outputs)
        dataset = Dataset(name, width, width, rows, {"program": program.spec,
            "interface": program.ports, "description": template.document["description"]})
        checked = fitness(circuit, dataset)
        if not checked["verified_truth_table"]:
            raise ValueError("Export requires a fully verified truth table")
        prefix = OUTPUT / f"sort-{k}-{n}"
        for suffix, document in (("block", hierarchy.to_dict()), ("circuit", circuit.to_dict()),
                                 ("template", program.spec), ("vectors", dataset.to_dict())):
            write_json(prefix.with_suffix(f".{suffix}.json"), document)
        prefix.with_suffix(".nand.txt").write_text(netlist(circuit, program, name), encoding="utf-8", newline="\n")
        reports.append({"name": name, "parameters": {"k": k, "n": n},
            "channels": 2**k, "comparators": 2**k*k*(k+1)//4,
            "stages": k*(k+1)//2, "fitness": checked, "hierarchy": hierarchy.summary(),
            "synthesis": {"method": "structural-bitonic-sort", "version": 1}})
        print(f"{name}: {len(circuit.gates)} NANDs, depth {circuit.depth}, {len(rows)} inputs verified", flush=True)
    write_json(OUTPUT / "verification.json", reports)


if __name__ == "__main__":
    export()
