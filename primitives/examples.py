"""Install bundled templates and their concrete examples once per library."""
import json
from pathlib import Path

from .dataset import generate
from .library import function_id, write_json
from .templates import Template
from .synthesis import synthesize


def install_examples(library):
    marker = library.root / "example-installations.json"
    installed = json.loads(marker.read_text(encoding="utf-8")) if marker.exists() else {}
    if installed.get("arithmetic-v1"):
        return
    with library._lock:
        organization = library._organization()
        folders = [
            {"id": "examples", "parent": None, "name": "Beispiele", "description": "Editierbare Beispiele zum Öffnen, Konkretisieren und Nachbauen."},
            {"id": "arithmetic", "parent": "examples", "name": "Grundrechenarten", "description": "Konventionelle Bit-Algorithmen: feste Stufen, Bitverdrahtung und boolesche Operationen."},
            {"id": "arithmetic-templates", "parent": "arithmetic", "name": "Templates", "description": "Addition, Subtraktion, Multiplikation und Division für parametrierbare unsigned Bitbreiten."},
            {"id": "arithmetic-functions", "parent": "arithmetic", "name": "Funktionen (4 Bit)", "description": "Konkrete Instanzen mit allen 256 Eingabekombinationen und direkt synthetisierten NAND-Netzen."},
            {"id": "recursion", "parent": "examples", "name": "Rekursion", "description": "Rekursiver Addierer als Beispiel für Funktionen und Parameterbedingungen. NAND-Implementierung über die Evolution suchen."}]
        existing = {f["id"] for f in organization["folders"]}
        organization["folders"].extend(f for f in folders if f["id"] not in existing)
        # Save folders first; a partially interrupted installation can be retried.
        library._write_organization(organization)
        source = Path(__file__).resolve().parents[1] / "examples" / "templates"
        for path in sorted(source.glob("*.abstract.json")):
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
        library._write_organization(organization)
        installed["arithmetic-v1"] = True
        write_json(marker, installed)
