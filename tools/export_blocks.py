"""Build portable nested adder examples from explicit NAND implementations."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from primitives.blocks import BlockBundle
from primitives.circuit import Circuit
from primitives.library import write_json


def inp(name, bit=0):
    return {"input": name, "bit": bit}


def out(node, port, bit=0):
    return {"node": node, "port": port, "bit": bit}


def ports(inputs, outputs):
    return {"inputs": [{"name": n, "bits": b} for n, b in inputs],
            "outputs": [{"name": n, "bits": b} for n, b in outputs]}


def instance(name, block, **inputs):
    return {"id": name, "type": "instance", "definition": block.root, "inputs": inputs}


def examples():
    logic_ports = ports([("a", 1), ("b", 1)], [("value", 1)])
    xor = BlockBundle.from_circuit("XOR", Circuit(2, ((0, 1), (0, 2), (1, 2), (3, 4)), (5,)), logic_ports)
    and_block = BlockBundle.from_circuit("AND", Circuit(2, ((0, 1), (2, 2)), (3,)), logic_ports)
    or_block = BlockBundle.from_circuit("OR", Circuit(2, ((0, 0), (1, 1), (2, 3)), (4,)), logic_ports)
    half = BlockBundle.create({"name": "Halbaddierer", "version": 1,
        "interface": ports([("a", 1), ("b", 1)], [("sum", 1), ("carry", 1)]),
        "nodes": [instance("sum", xor, a=[inp("a")], b=[inp("b")]),
                  instance("carry", and_block, a=[inp("a")], b=[inp("b")])],
        "outputs": {"sum": [out("sum", "value")], "carry": [out("carry", "value")]}}, [xor, and_block])
    full = BlockBundle.create({"name": "Volladdierer", "version": 1,
        "interface": ports([("a", 1), ("b", 1), ("carryIn", 1)], [("sum", 1), ("carry", 1)]),
        "nodes": [instance("first", half, a=[inp("a")], b=[inp("b")]),
                  instance("second", half, a=[out("first", "sum")], b=[inp("carryIn")]),
                  instance("merge", or_block, a=[out("first", "carry")], b=[out("second", "carry")])],
        "outputs": {"sum": [out("second", "sum")], "carry": [out("merge", "value")]}}, [half, or_block])
    ripple = BlockBundle.create({"name": "ADD2 mit verschachtelten Volladdierern", "version": 1,
        "interface": ports([("a", 2), ("b", 2), ("carryIn", 1)], [("sum", 2), ("carryOut", 1)]),
        "nodes": [instance("high", full, a=[inp("a", 1)], b=[inp("b", 1)], carryIn=[out("low", "carry")]),
                  instance("low", full, a=[inp("a", 0)], b=[inp("b", 0)], carryIn=[inp("carryIn")])],
        "outputs": {"sum": [out("low", "sum"), out("high", "sum")], "carryOut": [out("high", "carry")]}}, [full])
    return {"half-adder": half, "full-adder": full, "ripple-adder-2": ripple}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "examples" / "blocks")
    args = parser.parse_args()
    for name, bundle in examples().items():
        write_json(args.out / (name + ".json"), bundle.to_dict())
    print(f"3 verschachtelte Beispielbausteine nach {args.out.resolve()} exportiert.")


if __name__ == "__main__":
    main()
