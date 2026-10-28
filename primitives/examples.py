"""Install bundled templates and their concrete examples once per library."""
import ast
import json
from pathlib import Path

from .blocks import BlockBundle
from .dataset import Dataset, generate
from .library import function_id, write_json
from .program import template_source
from .templates import Template
from .synthesis import synthesize


GENERATIVE_EXAMPLES = ("parity", "iszero", "reverse", "mux", "min", "max")
ROUTING_EXAMPLES = ("multiplexer", "demultiplexer")


def install_arithmetic_comments(library):
    """Refresh only known bundled sources; retain saved datasets and user edits."""
    marker = library.root / "example-installations.json"
    with library._lock:
        installed = json.loads(marker.read_text(encoding="utf-8")) if marker.exists() else {}
        if installed.get("arithmetic-comments-v1"):
            return
        source = Path(__file__).resolve().parents[1] / "examples/templates"
        revisions = json.loads((source / "arithmetic-comment-updates.json").read_text(encoding="utf-8"))
        updates = {revision["previous_source"]:
                   json.loads((source / f"{revision['template']}.abstract.json").read_text(encoding="utf-8"))["source"]
                   for revision in revisions}
        for previous, current in updates.items():
            if ast.dump(ast.parse(template_source(previous))) != ast.dump(ast.parse(template_source(current))):
                raise ValueError("Die Kommentarmigration darf keine Programmlogik ändern.")
        organization, details = library._organization(), library._function_details()
        changed = []
        for path in sorted((library.root / "datasets").glob("*.json")):
            document = json.loads(path.read_text(encoding="utf-8"))
            program = document.get("metadata", {}).get("program", {})
            if program.get("source") not in updates:
                continue
            previous_id = function_id(Dataset.from_dict(document))
            program["source"] = updates[program["source"]]
            current_id = function_id(Dataset.from_dict(document))
            # Sources participate in function IDs. Transfer folder and editable
            # labels before writing datasets, so an interrupted refresh can retry.
            old, new = f"function:{previous_id}", f"function:{current_id}"
            if old in organization["entries"]:
                organization["entries"].setdefault(new, organization["entries"].pop(old))
            if previous_id in details:
                details.setdefault(current_id, details.pop(previous_id))
            changed.append((path, document))
        library._write_organization(organization)
        if details or (library.root / "function-details.json").exists():
            write_json(library.root / "function-details.json", details)
        for path, document in changed:
            # Keep dataset filenames: circuits, histories and frozen settings
            # still refer to the same data and assignment vectors.
            write_json(path, document)
        for path in sorted((library.root / "templates").glob("*.json")):
            document = json.loads(path.read_text(encoding="utf-8"))
            if document.get("source") in updates:
                document["source"] = updates[document["source"]]
                Template(document)
                # Keep existing template keys and folder assignments too.
                write_json(path, document)
        installed["arithmetic-comments-v1"] = True
        write_json(marker, installed)


def install_standard_arithmetic_examples(library):
    """Add all 1/2/4-bit operand pairs once, preserving existing examples."""
    marker = library.root / "example-installations.json"
    with library._lock:
        installed = json.loads(marker.read_text(encoding="utf-8")) if marker.exists() else {}
        if installed.get("standard-arithmetic-v1"):
            return
        organization = library._organization()
        folders = [
            {"id": "examples", "parent": None, "name": "Beispiele", "description": "Editierbare Beispiele."},
            {"id": "arithmetic", "parent": "examples", "name": "Grundrechenarten", "description": "Konventionelle Bit-Algorithmen."},
            {"id": "standard-arithmetic", "parent": "arithmetic", "name": "Standardlösungen (1, 2, 4 Bit)",
             "description": "Alle neun Kombinationen unabhängig breiter Eingänge pro Grundrechenart; vollständig geprüft mit NAND-Netz und Baustein."},
        ]
        kinds = {"add": "Addition", "sub": "Subtraktion", "mul": "Multiplikation", "div": "Division"}
        folders.extend({"id": f"standard-{kind}", "parent": "standard-arithmetic", "name": name,
                        "description": "Generatives Bit-Template und neun Standardlösungen für a[p], b[q] mit p,q=1,2,4."}
                       for kind, name in kinds.items())
        existing = {f["id"] for f in organization["folders"]}
        organization["folders"].extend(f for f in folders if f["id"] not in existing)
        library._write_organization(organization)
        source = Path(__file__).resolve().parents[1] / "examples"
        for kind in kinds:
            folder = f"standard-{kind}"
            template = Template(json.loads((source / f"templates/{folder}.abstract.json").read_text(encoding="utf-8")))
            key = library.save_template(template)
            organization["entries"].setdefault(f"template:{key}", folder)
            for p in (1, 2, 4):
                for q in (1, 2, 4):
                    prefix = source / f"circuits/{folder}/{kind}-{p}-{q}"
                    library.save_block(BlockBundle(json.loads(prefix.with_suffix(".block.json").read_text(encoding="utf-8"))))
                    dataset = Dataset.from_dict(json.loads(prefix.with_suffix(".vectors.json").read_text(encoding="utf-8")))
                    circuit = json.loads(prefix.with_suffix(".circuit.json").read_text(encoding="utf-8"))
                    library.save_program({"circuit": circuit, "synthesis": {"method": "structural-bitwise", "version": 1}}, dataset)
                    organization["entries"].setdefault(f"function:{function_id(dataset)}", folder)
        library._write_organization(organization)
        installed["standard-arithmetic-v1"] = True
        write_json(marker, installed)


def install_structured_examples(library):
    """Separate migration: previous installations and user organization stay intact."""
    marker = library.root / "example-installations.json"
    with library._lock:
        installed = json.loads(marker.read_text(encoding="utf-8")) if marker.exists() else {}
        if installed.get("structured-logic-v1"):
            return
        organization = library._organization()
        folder = "structured-logic"
        if not any(f["id"] == folder for f in organization["folders"]):
            organization["folders"].append({"id": folder, "parent": "recursion", "name": "Bitcodes & Auswahl",
                                             "description": "Gray-Code, Dekodierung, Präfix-ODER und Sortierung mit sichtbaren FBoxen."})
        source = Path(__file__).resolve().parents[1] / "examples"
        for kind in ("gray", "ungray", "prefix_or", "sort2"):
            template = Template(json.loads((source / f"templates/recursive-{kind}.abstract.json").read_text(encoding="utf-8")))
            key = library.save_template(template)
            organization["entries"].setdefault(f"template:{key}", folder)
            for width in (1, 2, 4):
                prefix = source / f"circuits/recursive-{kind}/{kind}-{width}"
                library.save_block(BlockBundle(json.loads(prefix.with_suffix(".block.json").read_text(encoding="utf-8"))))
                dataset = Dataset.from_dict(json.loads(prefix.with_suffix(".vectors.json").read_text(encoding="utf-8")))
                circuit = json.loads(prefix.with_suffix(".circuit.json").read_text(encoding="utf-8"))
                library.save_program({"circuit": circuit, "synthesis": {"method": "hierarchy-expansion-and-simplification", "version": 1}}, dataset)
                organization["entries"].setdefault(f"function:{function_id(dataset)}", folder)
        library._write_organization(organization)
        installed["structured-logic-v1"] = True
        write_json(marker, installed)


def install_examples(library):
    marker = library.root / "example-installations.json"
    installed = json.loads(marker.read_text(encoding="utf-8")) if marker.exists() else {}
    pending_arithmetic = not installed.get("arithmetic-v1")
    pending_recursion = not installed.get("recursive-checked-v1")
    pending_mul = not installed.get("recursive-mul-v1")
    pending_ones = not installed.get("number-of-ones-v1")
    pending_div = not installed.get("recursive-msb-div-v1")
    pending_max_index = not installed.get("recursive-max-index-v1")
    pending_equ = not installed.get("recursive-equ-v1")
    pending_gt = not installed.get("recursive-gt-v1")
    pending_generative = not installed.get("generative-logic-v1")
    pending_routing = not installed.get("routing-v1")
    if not any((pending_arithmetic, pending_recursion, pending_mul, pending_ones, pending_div, pending_max_index, pending_equ, pending_gt, pending_generative, pending_routing)):
        return
    with library._lock:
        organization = library._organization()
        folders = [
            {"id": "examples", "parent": None, "name": "Beispiele", "description": "Editierbare Beispiele zum Öffnen, Konkretisieren und Nachbauen."},
            {"id": "arithmetic", "parent": "examples", "name": "Grundrechenarten", "description": "Konventionelle Bit-Algorithmen: feste Stufen, Bitverdrahtung und boolesche Operationen."},
            {"id": "arithmetic-templates", "parent": "arithmetic", "name": "Templates", "description": "Addition, Subtraktion, Multiplikation und Division für parametrierbare unsigned Bitbreiten."},
            {"id": "arithmetic-functions", "parent": "arithmetic", "name": "Funktionen (4 Bit)", "description": "Konkrete Instanzen mit allen 256 Eingabekombinationen und direkt synthetisierten NAND-Netzen."},
            {"id": "recursion", "parent": "examples", "name": "Rekursion", "description": "Rekursive Arithmetik, Zählung, Vergleiche, Parität, Nulltest, Bitumkehr, Multiplexer, Minimum und Maximum. Generative Beispiele für 1, 2 und 4 Bits mit F-Boxen und flachen NAND-Netzen."},
            {"id": "routing", "parent": "recursion", "name": "Multiplexer & Demultiplexer", "description": "MUX<n,w> und DEMUX<n,w>: n Datenbits pro Kanal, w Auswahlbits und 2**w Kanäle. Instanzen für n=1,2,4 und w=1,2,4."}]
        existing = {f["id"] for f in organization["folders"]}
        organization["folders"].extend(f for f in folders if f["id"] not in existing)
        # Save folders first; a partially interrupted installation can be retried.
        library._write_organization(organization)
        source = Path(__file__).resolve().parents[1] / "examples" / "templates"
        recursive_checked = {"recursive-split-sub.abstract.json", "recursive-split-add-checked.abstract.json"}
        for path in sorted(source.glob("*.abstract.json")):
            if path.name.startswith("standard-"):
                continue  # Independently sized operands have their own migration.
            if path.stem.removesuffix(".abstract") in {f"recursive-{kind}" for kind in ("gray", "ungray", "prefix_or", "sort2")}:
                continue  # Installed by its own migration after the original examples.
            routing = path.name in {f"recursive-{kind}.abstract.json" for kind in ROUTING_EXAMPLES}
            if routing:
                if not pending_routing:
                    continue
            elif path.name in {f"recursive-{kind}.abstract.json" for kind in GENERATIVE_EXAMPLES}:
                if not pending_generative:
                    continue
            elif path.name == "recursive-gt.abstract.json":
                if not pending_gt:
                    continue
            elif path.name == "recursive-equ.abstract.json":
                if not pending_equ:
                    continue
            elif path.name == "recursive-max-index.abstract.json":
                if not pending_max_index:
                    continue
            elif path.name == "recursive-msb-div.abstract.json":
                if not pending_div:
                    continue
            elif path.name == "recursive-number-of-ones.abstract.json":
                if not pending_ones:
                    continue
            elif path.name == "recursive-split-mul.abstract.json":
                if not pending_mul:
                    continue
            elif path.name in recursive_checked:
                if not pending_recursion:
                    continue
            elif not pending_arithmetic:
                continue
            template = Template(json.loads(path.read_text(encoding="utf-8")))
            key = library.save_template(template)
            organization["entries"].setdefault(f"template:{key}", "routing" if routing else "recursion" if path.name.startswith("recursive-") else "arithmetic-templates")
            if path.name.startswith("recursive-"):
                continue
            program = template.instantiate({"n": 4})
            circuit = synthesize(program)
            dataset = generate(f"{template.document['name']} (4 Bit)", 8,
                               sum(p["bits"] for p in program.ports["outputs"]),
                               ports=program.ports, program=program.spec, samples=256)
            dataset.metadata["description"] = template.document["description"]
            library.save_program({"circuit": circuit.to_dict(), "synthesis": {"method": "structural-bitwise", "version": 1}}, dataset)
            organization["entries"].setdefault(f"function:{function_id(dataset)}", "arithmetic-functions")
        for pending, folder, stem in ((pending_mul, "recursive-split-mul", "mul"),
                                      (pending_ones, "recursive-number-of-ones", "number-of-ones"),
                                      (pending_max_index, "recursive-max-index", "m"),
                                      (pending_equ, "recursive-equ", "equ"),
                                      (pending_gt, "recursive-gt", "gt"),
                                      *((pending_generative, f"recursive-{kind}", kind) for kind in GENERATIVE_EXAMPLES),
                                      *((pending_routing, f"recursive-{kind}", kind) for kind in ROUTING_EXAMPLES)):
            if not pending:
                continue
            output = source.parent / "circuits" / folder
            routing = stem in ROUTING_EXAMPLES
            names = ([f"{stem}-{n}-{w}" for n in (1, 2, 4) for w in (1, 2, 4)] if routing
                     else [f"{stem}-{width}" for width in (1, 2, 4)])
            for name in names:
                prefix = output / name
                hierarchy = BlockBundle(json.loads(prefix.with_suffix(".block.json").read_text(encoding="utf-8")))
                library.save_block(hierarchy)
                dataset = Dataset.from_dict(json.loads(prefix.with_suffix(".vectors.json").read_text(encoding="utf-8")))
                circuit = json.loads(prefix.with_suffix(".circuit.json").read_text(encoding="utf-8"))
                library.save_program({"circuit": circuit,
                                      "synthesis": {"method": "hierarchy-expansion-and-simplification", "version": 1}}, dataset)
                organization["entries"].setdefault(f"function:{function_id(dataset)}", "routing" if routing else "recursion")
        if pending_div:
            output = source.parent / "circuits" / "recursive-msb-div"
            for width in (1, 2, 3, 4):
                prefix = output / f"div-{width}"
                dataset = Dataset.from_dict(json.loads(prefix.with_suffix(".vectors.json").read_text(encoding="utf-8")))
                circuit = json.loads(prefix.with_suffix(".circuit.json").read_text(encoding="utf-8"))
                library.save_program({"circuit": circuit,
                                      "synthesis": {"method": "structural-bitwise", "version": 1}}, dataset)
                organization["entries"].setdefault(f"function:{function_id(dataset)}", "recursion")
        library._write_organization(organization)
        installed["arithmetic-v1"] = True
        installed["recursive-checked-v1"] = True
        installed["recursive-mul-v1"] = True
        installed["number-of-ones-v1"] = True
        installed["recursive-msb-div-v1"] = True
        installed["recursive-max-index-v1"] = True
        installed["recursive-equ-v1"] = True
        installed["recursive-gt-v1"] = True
        installed["generative-logic-v1"] = True
        installed["routing-v1"] = True
        write_json(marker, installed)
