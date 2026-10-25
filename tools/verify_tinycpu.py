"""Compare reference vectors with an explicit local TinyCPU checkout, without modifying it."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True

from primitives.dataset import integer
from primitives.operations import generate_operation
from primitives.ports import decode


def verify(source):
    sys.path.insert(0, str(source / "src"))
    from tiny_cpu_assembler import Instruction, Program
    from tiny_cpu_vm import TinyCPU

    checked, overflows = 0, 0
    for name in ("ADD", "SUB", "MUL", "DIV", "AND", "OR", "XOR", "NOT"):
        ds = generate_operation({"definition": name, "parameters": {
            "a_bits": 16, "b_bits": 16, "result_bits": 16, "signed": True,
            "flag": name in {"ADD", "SUB", "MUL"}}}, samples=256, seed=7)
        for row in ds.rows:
            a, *rest = [decode(integer(row[:ds.inputs]), p) for p in ds.metadata["interface"]["inputs"]]
            outputs = {p["name"]: decode(integer(row[ds.inputs:]), p) for p in ds.metadata["interface"]["outputs"]}
            for mode in (("CONST", "ADDRESS", "ADDRESS_REGISTER", "ADDRESS_REGISTER_PLUS_OFFSET") if rest else (None,)):
                b = rest[0] if rest else 0
                instruction = Instruction(f"{name}_{mode}" if mode else name,
                                          b if mode == "CONST" else 7 if mode == "ADDRESS" else 0)
                cpu = TinyCPU(Program((instruction,), {}, {}), accumulator=a, accumulator_valid=True,
                              address_register=7, address_register_valid=True, memory={7: (b, True)})
                cpu.step()
                context = (name, mode, a, b, outputs)
                if outputs.get("overflow"):
                    assert cpu.errors["OVF"] and not cpu.accumulator_valid and cpu.accumulator == 0, context
                    overflows += 1
                else:
                    assert cpu.accumulator == outputs["c"], context
                    assert cpu.accumulator_valid == bool(outputs.get("valid", 1)), context
                    assert cpu.errors["DIV0"] == bool(outputs.get("div0", 0)), context
                    assert not cpu.errors["OVF"], context
                checked += 1
    return checked, overflows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="TinyCPU checkout root")
    args = parser.parse_args()
    checked, overflows = verify(args.source.resolve())
    print(f"{checked} VM-Vergleiche erfolgreich; {overflows} Überlauffälle mit dokumentiert abweichender Ergebnispolitik.")


if __name__ == "__main__":
    main()
