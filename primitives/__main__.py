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
from .blocks import BlockBundle


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
    gen.add_argument("--expression")
    formulas = gen.add_mutually_exclusive_group()
    formulas.add_argument("--formula", help="Eigene Formel, z.B. c=mod(a+b,2^4), e=div(a+b,2^4); ^ bedeutet Potenz")
    formulas.add_argument("--formula-file", type=Path, help="UTF-8-Datei mit eigener Formel")
    formulas.add_argument("--program-file", type=Path, help="UTF-8-Programm: Zuweisungen, return, if/else, while, for … in range(…)")
    gen.add_argument("--program-steps", type=int)
    gen.add_argument("--program-iterations", type=int)
    gen.add_argument("--program-total-steps", type=int)
    gen.add_argument("--a-bits", type=int)
    gen.add_argument("--b-bits", type=int)
    gen.add_argument("--result-bits", type=int)
    gen.add_argument("--signed", action="store_true")
    gen.add_argument("--overflow", choices=("wrap", "error"), default="wrap")
    gen.add_argument("--flag", action="store_true", help="Carry/Borrow bzw. Überlauf als zusätzlichen Ausgang erzeugen")
    gen.add_argument("--shift", type=int, help="Feste Schiebeweite 0–32 für SHL/SHR/SAR; sonst Eingang b")
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
    evolve.add_argument("--population", type=int, default=24,
                        help="Elternpopulation (2–256); zugleich maximale Nachkommen je Runde")
    evolve.add_argument("--generations", type=int, default=200)
    evolve.add_argument("--restarts", type=int, default=1, help="Unabhängige Starts (1–32), teilen das Kandidatenbudget")
    evolve.add_argument("--islands", type=int, default=1, help="Inseln (1–16), teilen die Elternpopulation; mindestens 2 Eltern je Insel")
    evolve.add_argument("--migration-interval", type=int, default=10, help="Elitenaustausch im Ring nach jeweils so vielen Generationen")
    evolve.add_argument("--seed", type=int, default=1)
    evolve.add_argument("--neutral", action="store_true",
                        help="Nur Ausgangsfehler bewerten, danach funktionserhaltend vereinfachen")
    commands.add_parser("library", help="Gespeicherte Programme auflisten")
    evaluate = commands.add_parser("eval", help="Klammerprogramm auswerten")
    evaluate.add_argument("expression")
    evaluate.add_argument("bits", help="Eingangsbits in Reihenfolge 1…N, z.B. 101")
    blocks = commands.add_parser("blocks", help="Versionierte Unterprogramm-Bausteine")
    block_commands = blocks.add_subparsers(dest="block_command", required=True)
    block_commands.add_parser("list")
    for verb in ("import", "compose", "expand", "eval", "vectors"):
        command = block_commands.add_parser(verb)
        command.add_argument("file", type=Path, help="Portables Bausteinpaket; bei compose eine neue Definition")
        if verb in ("expand", "vectors"):
            command.add_argument("--out", type=Path, required=True)
        if verb == "compose":
            command.add_argument("--dependency", action="append", default=[], help="Feste Kennung in der lokalen Bibliothek")
            command.add_argument("--out", type=Path)
        if verb == "eval":
            command.add_argument("bits", help="LSB-first-Eingabebits")
        if verb == "vectors":
            command.add_argument("--samples", type=int, default=256)
            command.add_argument("--seed", type=int, default=1)
    block_from = block_commands.add_parser("from-program")
    block_from.add_argument("program_id")
    block_from.add_argument("--name")
    block_from.add_argument("--version", type=int, default=1)
    block_from.add_argument("--interface", type=Path)
    block_from.add_argument("--out", type=Path)
    args = parser.parse_args()
    try:
        library = Library(args.data_dir)
        if args.command == "serve":
            serve(args.port, args.data_dir)
        elif args.command == "generate":
            if not args.program_file and any(v is not None for v in (args.program_steps, args.program_iterations, args.program_total_steps)):
                raise ValueError("Programmbudgets benötigen --program-file.")
            if (args.operation or args.preset) and (args.interface or args.expressions or args.reference_circuit or args.formula is not None or args.formula_file or args.program_file):
                raise ValueError("Benannte eigene Referenzen nicht mit --operation/--preset kombinieren.")
            if not args.operation and (args.a_bits is not None or args.b_bits is not None or args.result_bits is not None or args.signed or args.flag or args.overflow != "wrap" or args.shift is not None):
                raise ValueError("Breitenparameter und --signed/--flag/--overflow benötigen --operation; eigene Ports über --interface definieren.")
            if args.operation:
                params = {"a_bits": args.a_bits, "b_bits": args.b_bits, "result_bits": args.result_bits,
                          "signed": args.signed, "overflow": args.overflow, "flag": args.flag, "shift": args.shift}
                dataset = generate_operation({"definition": args.operation, "parameters": params}, args.samples, args.seed,
                                             None if args.name == "eigener-ausdruck" else args.name)
            elif args.preset:
                dataset = preset(args.preset, args.samples, args.seed)
            else:
                load = lambda p: json.loads(p.read_text(encoding="utf-8")) if p else None
                formula = args.formula_file.read_text(encoding="utf-8") if args.formula_file else args.formula
                program = None
                if args.program_file:
                    if args.expressions or args.reference_circuit or args.expression is not None:
                        raise ValueError("Programm nicht mit anderen Referenzen kombinieren.")
                    program = {"version": 1, "source": args.program_file.read_text(encoding="utf-8"),
                               "limits": {k: v for k, v in {"steps": args.program_steps, "iterations": args.program_iterations,
                                          "total_steps": args.program_total_steps}.items() if v is not None}}
                if formula is not None and (args.expressions or args.reference_circuit):
                    raise ValueError("Formel nicht mit --expressions oder --reference-circuit kombinieren.")
                expression = args.expression if args.expression is not None else "x0 ^ x1"
                dataset = generate(args.name, args.inputs, args.outputs, None if program else load(args.expressions) if args.expressions else expression,
                                   args.samples, args.seed, ports=load(args.interface), reference_circuit=load(args.reference_circuit), formula=formula, program=program)
            write_json(args.out, dataset.to_dict())
            print(f"{len(dataset.rows)} Vektoren gespeichert: {args.out.resolve()}")
        elif args.command == "evolve":
            dataset = preset(args.preset) if args.preset else Dataset.from_dict(json.loads(args.dataset.read_text(encoding="utf-8")))
            config = SearchConfig(args.gates, args.population, args.generations, args.seed, args.backend,
                                  restarts=args.restarts, islands=args.islands, migration_interval=args.migration_interval,
                                  neutral=args.neutral)
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
        elif args.command == "blocks":
            verb = args.block_command
            if verb == "list":
                print(json.dumps(library.blocks(), ensure_ascii=False, indent=2))
            else:
                if verb == "from-program":
                    ports = json.loads(args.interface.read_text(encoding="utf-8")) if args.interface else None
                    bundle = library.block_from_program(args.program_id, args.name, ports, args.version)
                else:
                    document = json.loads(args.file.read_text(encoding="utf-8"))
                    bundle = (BlockBundle.create(document, [library.load_block(key) for key in args.dependency])
                              if verb == "compose" else BlockBundle(document))
                if verb in ("from-program", "import", "compose"):
                    summary = library.save_block(bundle)
                    if getattr(args, "out", None): write_json(args.out, bundle.to_dict())
                    print(json.dumps(summary, ensure_ascii=False, indent=2))
                elif verb == "expand":
                    write_json(args.out, {"circuit": bundle.expand().to_dict(), "hierarchy": bundle.to_dict()})
                elif verb == "vectors":
                    write_json(args.out, bundle.dataset(args.samples, args.seed).to_dict())
                else:
                    print(bundle.evaluate([int(b) for b in args.bits]))
        elif args.command == "eval":
            circuit = parse_expression(args.expression, len(args.bits))
            print(circuit.evaluate([int(b) for b in args.bits]))
    except KeyboardInterrupt:
        print("Abgebrochen; kein neuer Datensatz gespeichert.", file=sys.stderr)
        return 130
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

