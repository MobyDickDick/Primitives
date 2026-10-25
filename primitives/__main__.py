import argparse
import importlib.util
import json
from pathlib import Path
import sys
from .circuit import parse_expression
from .dataset import Dataset, PRESETS, generate, preset
from .operations import OPERATIONS, generate_operation
from .evolution import SearchConfig
from .library import Library, write_json
from .runner import ROOT, search
from .server import serve


def main():
    parser = argparse.ArgumentParser(description="Primitives – evolutionäre NAND-Spielwiese")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    commands = parser.add_subparsers(dest="command", required=True)
    web = commands.add_parser("serve", help="Lokale Browseroberfläche starten")
    web.add_argument("--port", type=int, default=8765)
    gen = commands.add_parser("generate", help="Zuordnungsvektoren erzeugen")
    template = gen.add_mutually_exclusive_group()
    template.add_argument("--preset", choices=PRESETS)
    template.add_argument("--operation", choices=OPERATIONS)
    gen.add_argument("--name", default="eigener-ausdruck")
    gen.add_argument("--inputs", type=int, default=2)
    gen.add_argument("--outputs", type=int, default=1)
    gen.add_argument("--expression", default="x0 ^ x1")
    gen.add_argument("--a-bits", type=int)
    gen.add_argument("--b-bits", type=int)
    gen.add_argument("--result-bits", type=int)
    gen.add_argument("--signed", action="store_true")
    gen.add_argument("--overflow", choices=("wrap", "error"), default="wrap")
    gen.add_argument("--flag", action="store_true", help="Carry/Borrow bzw. Überlauf als zusätzlichen Ausgang erzeugen")
    gen.add_argument("--interface", type=Path, help="JSON mit benannten inputs/outputs; Summen müssen --inputs/--outputs entsprechen")
    gen.add_argument("--expressions", type=Path, help="JSON-Zuordnung Ergebnisport -> Ausdruck")
    gen.add_argument("--reference-circuit", type=Path, help="NAND-JSON bitweise auf benannte Ports anwenden")
    gen.add_argument("--samples", type=int)
    gen.add_argument("--seed", type=int, default=1)
    gen.add_argument("--out", type=Path, required=True)
    oracle = commands.add_parser("oracle", help="Vektoren aus einem eigenen vertrauenswürdigen Python-Programm")
    oracle.add_argument("file", type=Path, help="Python-Datei mit oracle(x) -> int")
    oracle.add_argument("--inputs", type=int, required=True)
    oracle.add_argument("--outputs", type=int, required=True)
    oracle.add_argument("--samples", type=int, default=256)
    oracle.add_argument("--seed", type=int, default=1)
    oracle.add_argument("--out", type=Path, required=True)
    evolve = commands.add_parser("evolve", help="Programm evolutionär suchen und speichern")
    source = evolve.add_mutually_exclusive_group(required=True)
    source.add_argument("--preset", choices=PRESETS)
    source.add_argument("--dataset", type=Path)
    evolve.add_argument("--backend", choices=("tiny", "python"), default="tiny")
    evolve.add_argument("--gates", type=int, default=12)
    evolve.add_argument("--population", type=int, default=24)
    evolve.add_argument("--generations", type=int, default=200)
    evolve.add_argument("--seed", type=int, default=1)
    commands.add_parser("library", help="Gespeicherte Programme auflisten")
    evaluate = commands.add_parser("eval", help="Klammerprogramm auswerten")
    evaluate.add_argument("expression")
    evaluate.add_argument("bits", help="Eingangsbits in Reihenfolge 1…N, z.B. 101")
    args = parser.parse_args()
    try:
        library = Library(args.data_dir)
        if args.command == "serve":
            serve(args.port, args.data_dir)
        elif args.command == "generate":
            if (args.operation or args.preset) and (args.interface or args.expressions or args.reference_circuit):
                raise ValueError("Benannte eigene Referenzen nicht mit --operation/--preset kombinieren.")
            if not args.operation and (args.a_bits is not None or args.b_bits is not None or args.result_bits is not None or args.signed or args.flag or args.overflow != "wrap"):
                raise ValueError("Breitenparameter und --signed/--flag/--overflow benötigen --operation; eigene Ports über --interface definieren.")
            if args.operation:
                params = {"a_bits": args.a_bits, "b_bits": args.b_bits, "result_bits": args.result_bits,
                          "signed": args.signed, "overflow": args.overflow, "flag": args.flag}
                dataset = generate_operation({"definition": args.operation, "parameters": params}, args.samples, args.seed,
                                             None if args.name == "eigener-ausdruck" else args.name)
            elif args.preset:
                dataset = preset(args.preset, args.samples, args.seed)
            else:
                load = lambda p: json.loads(p.read_text(encoding="utf-8")) if p else None
                dataset = generate(args.name, args.inputs, args.outputs, load(args.expressions) if args.expressions else args.expression,
                                   args.samples, args.seed, ports=load(args.interface), reference_circuit=load(args.reference_circuit))
            write_json(args.out, dataset.to_dict())
            print(f"{len(dataset.rows)} Vektoren gespeichert: {args.out.resolve()}")
        elif args.command == "evolve":
            dataset = preset(args.preset) if args.preset else Dataset.from_dict(json.loads(args.dataset.read_text(encoding="utf-8")))
            config = SearchConfig(args.gates, args.population, args.generations, args.seed, args.backend)
            print(json.dumps(search(dataset, config, library), ensure_ascii=False, indent=2))
        elif args.command == "oracle":
            spec = importlib.util.spec_from_file_location("primitives_user_oracle", args.file.resolve())
            if spec is None or spec.loader is None:
                raise ValueError("Die Python-Datei kann nicht geladen werden.")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            if not callable(getattr(module, "oracle", None)):
                raise ValueError("Die Datei muss eine Funktion oracle(x) enthalten.")
            dataset = generate(args.file.stem, args.inputs, args.outputs, "Python oracle(x)", args.samples, args.seed, oracle=module.oracle)
            dataset.metadata["oracle_file"] = str(args.file.resolve())
            write_json(args.out, dataset.to_dict())
            print(f"{len(dataset.rows)} Vektoren gespeichert: {args.out.resolve()}")
        elif args.command == "library":
            print(json.dumps(library.programs(), ensure_ascii=False, indent=2))
        elif args.command == "eval":
            circuit = parse_expression(args.expression, len(args.bits))
            print(circuit.evaluate([int(b) for b in args.bits]))
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

