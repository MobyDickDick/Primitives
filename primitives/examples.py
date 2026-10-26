"""Install bundled templates and their concrete examples once per library."""
import json
from pathlib import Path

from .blocks import BlockBundle
from .dataset import Dataset, generate
from .library import function_id, write_json
from .templates import Template
from .synthesis import synthesize


def install_examples(library):
    marker = library.root / "example-installations.json"
    installed = json.loads(marker.read_text(encoding="utf-8")) if marker.exists() else {}
    pending_arithmetic = not installed.get("arithmetic-v1")
    pending_recursion = not installed.get("recursive-checked-v1")
    pending_mul = not installed.get("recursive-mul-v1")
    pending_ones = not installed.get("number-of-ones-v1")
    if not pending_arithmetic and not pending_recursion and not pending_mul and not pending_ones:
        return
    with library._lock:
        organization = library._organization()
        folders = [
            {"id": "examples", "parent": None, "name": "Beispiele", "description": "Editierbare Beispiele zum Öffnen, Konkretisieren und Nachbauen."},
            {"id": "arithmetic", "parent": "examples", "name": "Grundrechenarten", "description": "Konventionelle Bit-Algorithmen: feste Stufen, Bitverdrahtung und boolesche Operationen."},
            {"id": "arithmetic-templates", "parent": "arithmetic", "name": "Templates", "description": "Addition, Subtraktion, Multiplikation und Division für parametrierbare unsigned Bitbreiten."},
            {"id": "arithmetic-functions", "parent": "arithmetic", "name": "Funktionen (4 Bit)", "description": "Konkrete Instanzen mit allen 256 Eingabekombinationen und direkt synthetisierten NAND-Netzen."},
            {"id": "recursion", "parent": "examples", "name": "Rekursion", "description": "Rekursive Arithmetik und NumberOfOnes durch Halbierung. MUL und NumberOfOnes für 1, 2 und 4 Bits mit F-Boxen und flachen NAND-Netzen."}]
        existing = {f["id"] for f in organization["folders"]}
        organization["folders"].extend(f for f in folders if f["id"] not in existing)
        # Save folders first; a partially interrupted installation can be retried.
        library._write_organization(organization)
        source = Path(__file__).resolve().parents[1] / "examples" / "templates"
        recursive_checked = {"recursive-split-sub.abstract.json", "recursive-split-add-checked.abstract.json"}
        for path in sorted(source.glob("*.abstract.json")):
            if path.name == "recursive-number-of-ones.abstract.json":
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
            organization["entries"].setdefault(f"template:{key}", "recursion" if path.name.startswith("recursive-") else "arithmetic-templates")
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
                                      (pending_ones, "recursive-number-of-ones", "number-of-ones")):
            if not pending:
                continue
            output = source.parent / "circuits" / folder
            for width in (1, 2, 4):
                prefix = output / f"{stem}-{width}"
                hierarchy = BlockBundle(json.loads(prefix.with_suffix(".block.json").read_text(encoding="utf-8")))
                library.save_block(hierarchy)
                dataset = Dataset.from_dict(json.loads(prefix.with_suffix(".vectors.json").read_text(encoding="utf-8")))
                circuit = json.loads(prefix.with_suffix(".circuit.json").read_text(encoding="utf-8"))
                library.save_program({"circuit": circuit,
                                      "synthesis": {"method": "hierarchy-expansion-and-simplification", "version": 1}}, dataset)
                organization["entries"].setdefault(f"function:{function_id(dataset)}", "recursion")
        library._write_organization(organization)
        installed["arithmetic-v1"] = True
        installed["recursive-checked-v1"] = True
        installed["recursive-mul-v1"] = True
        installed["number-of-ones-v1"] = True
        write_json(marker, installed)
