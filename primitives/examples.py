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
ZERO_COUNT_EXAMPLES = ("clz", "ctz")
ONEHOT_EXAMPLES = ("decoder", "onehot-encoder")
BARREL_EXAMPLES = ("shl", "shr", "sar")
ROTATION_EXAMPLES = ("rol", "ror")
PREFIX_EXAMPLES = ("prefix_and", "prefix_xor")


def install_multiplier_examples(library):
    """Install GEN-11 once, preserving existing labels, folders and winners."""
    marker = library.root / "example-installations.json"
    with library._lock:
        installed = json.loads(marker.read_text(encoding="utf-8")) if marker.exists() else {}
        if installed.get("multipliers-v1"):
            return
        organization = library._organization()
        organization["entries"].update(library.tree()["entries"])
        folders = [
            {"id": "examples", "parent": None, "name": "Beispiele", "description": "Editierbare Beispiele."},
            {"id": "arithmetic", "parent": "examples", "name": "Grundrechenarten", "description": "Generative Bit-Templates."},
            {"id": "multipliers", "parent": "arithmetic", "name": "Array- & Wallace-Multiplikation",
             "description": "Vollständige unsigned Produkte mit Carry-Save-Reduktion; alle neun Kombinationen p,q=1,2,4 vollständig geprüft."},
        ]
        existing = {f["id"] for f in organization["folders"]}
        organization["folders"].extend(f for f in folders if f["id"] not in existing)
        library._write_organization(organization)
        source = Path(__file__).resolve().parents[1] / "examples"
        for kind in ("array", "wallace"):
            template = Template(json.loads((source / f"templates/{kind}-mul.abstract.json").read_text(encoding="utf-8")))
            key = library.save_template(template)
            organization["entries"].setdefault(f"template:{key}", "multipliers")
            for p in (1, 2, 4):
                for q in (1, 2, 4):
                    prefix = source / f"circuits/multipliers/{kind}-{p}-{q}"
                    library.save_block(BlockBundle(json.loads(prefix.with_suffix(".block.json").read_text(encoding="utf-8"))))
                    dataset = Dataset.from_dict(json.loads(prefix.with_suffix(".vectors.json").read_text(encoding="utf-8")))
                    circuit = json.loads(prefix.with_suffix(".circuit.json").read_text(encoding="utf-8"))
                    library.save_program({"circuit": circuit,
                                          "synthesis": {"method": "structural-carry-save", "version": 1}}, dataset)
                    organization["entries"].setdefault(f"function:{function_id(dataset)}", "multipliers")
        library._write_organization(organization)
        installed["multipliers-v1"] = True
        write_json(marker, installed)


def install_signed_arithmetic_examples(library):
    """Install GEN-10 once, preserving existing labels, folders and winners."""
    marker = library.root / "example-installations.json"
    with library._lock:
        installed = json.loads(marker.read_text(encoding="utf-8")) if marker.exists() else {}
        if installed.get("signed-arithmetic-v1"):
            return
        organization = library._organization()
        organization["entries"].update(library.tree()["entries"])
        folders = [
            {"id": "examples", "parent": None, "name": "Beispiele", "description": "Editierbare Beispiele."},
            {"id": "arithmetic", "parent": "examples", "name": "Grundrechenarten", "description": "Generative Bit-Templates."},
            {"id": "signed-arithmetic", "parent": "arithmetic", "name": "Signed Vergleiche & Grundrechenarten",
             "description": "Zweierkomplement: SCMP, SADD, SSUB, SMUL und SDIV; alle neun Kombinationen p,q=1,2,4 vollständig geprüft."},
        ]
        existing = {f["id"] for f in organization["folders"]}
        organization["folders"].extend(f for f in folders if f["id"] not in existing)
        library._write_organization(organization)
        source = Path(__file__).resolve().parents[1] / "examples"
        for kind in ("cmp", "add", "sub", "mul", "div"):
            template = Template(json.loads((source / f"templates/signed-{kind}.abstract.json").read_text(encoding="utf-8")))
            key = library.save_template(template)
            organization["entries"].setdefault(f"template:{key}", "signed-arithmetic")
            for p in (1, 2, 4):
                for q in (1, 2, 4):
                    prefix = source / f"circuits/signed-arithmetic/s{kind}-{p}-{q}"
                    library.save_block(BlockBundle(json.loads(prefix.with_suffix(".block.json").read_text(encoding="utf-8"))))
                    dataset = Dataset.from_dict(json.loads(prefix.with_suffix(".vectors.json").read_text(encoding="utf-8")))
                    circuit = json.loads(prefix.with_suffix(".circuit.json").read_text(encoding="utf-8"))
                    library.save_program({"circuit": circuit,
                                          "synthesis": {"method": "structural-bitwise-signed", "version": 1}}, dataset)
                    organization["entries"].setdefault(f"function:{function_id(dataset)}", "signed-arithmetic")
        library._write_organization(organization)
        installed["signed-arithmetic-v1"] = True
        write_json(marker, installed)


def install_signed_examples(library):
    """Install GEN-09 once, retaining user organization and better solutions."""
    marker = library.root / "example-installations.json"
    with library._lock:
        installed = json.loads(marker.read_text(encoding="utf-8")) if marker.exists() else {}
        if installed.get("signed-v1"):
            return
        organization = library._organization()
        # Existing entries may still use an implicit default folder.
        organization["entries"].update(library.tree()["entries"])
        folders = [
            {"id": "examples", "parent": None, "name": "Beispiele", "description": "Editierbare Beispiele."},
            {"id": "arithmetic", "parent": "examples", "name": "Grundrechenarten", "description": "Generative Bit-Templates."},
            {"id": "signed", "parent": "arithmetic", "name": "Vorzeichen, NEG & ABS",
             "description": "Zweierkomplement: Vorzeichenbit, Negation und Absolutwert mit Overflow; t=1,2,4 vollständig geprüft."},
        ]
        existing = {f["id"] for f in organization["folders"]}
        organization["folders"].extend(f for f in folders if f["id"] not in existing)
        library._write_organization(organization)
        source = Path(__file__).resolve().parents[1] / "examples"
        for kind in ("sign", "neg", "abs"):
            template = Template(json.loads((source / f"templates/signed-{kind}.abstract.json").read_text(encoding="utf-8")))
            key = library.save_template(template)
            organization["entries"].setdefault(f"template:{key}", "signed")
            for width in (1, 2, 4):
                prefix = source / f"circuits/signed/{kind}-{width}"
                library.save_block(BlockBundle(json.loads(prefix.with_suffix(".block.json").read_text(encoding="utf-8"))))
                dataset = Dataset.from_dict(json.loads(prefix.with_suffix(".vectors.json").read_text(encoding="utf-8")))
                circuit = json.loads(prefix.with_suffix(".circuit.json").read_text(encoding="utf-8"))
                library.save_program({"circuit": circuit,
                                      "synthesis": {"method": "hierarchy-expansion-and-simplification", "version": 1}}, dataset)
                organization["entries"].setdefault(f"function:{function_id(dataset)}", "signed")
        library._write_organization(organization)
        installed["signed-v1"] = True
        write_json(marker, installed)


def install_saturating_examples(library):
    """Install GEN-08 once, retaining user organization and better solutions."""
    marker = library.root / "example-installations.json"
    with library._lock:
        installed = json.loads(marker.read_text(encoding="utf-8")) if marker.exists() else {}
        if installed.get("saturating-v1"):
            return
        organization = library._organization()
        folders = [
            {"id": "examples", "parent": None, "name": "Beispiele", "description": "Editierbare Beispiele."},
            {"id": "arithmetic", "parent": "examples", "name": "Grundrechenarten", "description": "Generative Bit-Templates."},
            {"id": "saturating", "parent": "arithmetic", "name": "Sättigungsarithmetik",
             "description": "Unsigned SAT_ADD mit overflow und SAT_SUB mit underflow; alle neun Kombinationen p,q=1,2,4 vollständig geprüft."},
        ]
        existing = {f["id"] for f in organization["folders"]}
        organization["folders"].extend(f for f in folders if f["id"] not in existing)
        library._write_organization(organization)
        source = Path(__file__).resolve().parents[1] / "examples"
        for kind in ("add", "sub"):
            template = Template(json.loads((source / f"templates/sat-{kind}.abstract.json").read_text(encoding="utf-8")))
            key = library.save_template(template)
            organization["entries"].setdefault(f"template:{key}", "saturating")
            for p in (1, 2, 4):
                for q in (1, 2, 4):
                    prefix = source / f"circuits/saturating/sat-{kind}-{p}-{q}"
                    library.save_block(BlockBundle(json.loads(prefix.with_suffix(".block.json").read_text(encoding="utf-8"))))
                    dataset = Dataset.from_dict(json.loads(prefix.with_suffix(".vectors.json").read_text(encoding="utf-8")))
                    circuit = json.loads(prefix.with_suffix(".circuit.json").read_text(encoding="utf-8"))
                    library.save_program({"circuit": circuit,
                                          "synthesis": {"method": "hierarchy-expansion-and-simplification", "version": 1}}, dataset)
                    organization["entries"].setdefault(f"function:{function_id(dataset)}", "saturating")
        library._write_organization(organization)
        installed["saturating-v1"] = True
        write_json(marker, installed)


def install_parallel_add_examples(library):
    """Install GEN-07 once, retaining user organization and better solutions."""
    marker = library.root / "example-installations.json"
    with library._lock:
        installed = json.loads(marker.read_text(encoding="utf-8")) if marker.exists() else {}
        if installed.get("parallel-add-v1"):
            return
        organization = library._organization()
        folders = [
            {"id": "examples", "parent": None, "name": "Beispiele", "description": "Editierbare Beispiele."},
            {"id": "arithmetic", "parent": "examples", "name": "Grundrechenarten", "description": "Generative Bit-Templates."},
            {"id": "parallel-add", "parent": "arithmetic", "name": "Parallelpräfix-Addition",
             "description": "Generate/Propagate-Netz mit vollständiger Summe und Carry; alle neun Kombinationen p,q=1,2,4 vollständig geprüft."},
        ]
        existing = {f["id"] for f in organization["folders"]}
        organization["folders"].extend(f for f in folders if f["id"] not in existing)
        library._write_organization(organization)
        source = Path(__file__).resolve().parents[1] / "examples"
        template = Template(json.loads((source / "templates/parallel-prefix-add.abstract.json").read_text(encoding="utf-8")))
        key = library.save_template(template)
        organization["entries"].setdefault(f"template:{key}", "parallel-add")
        for p in (1, 2, 4):
            for q in (1, 2, 4):
                prefix = source / f"circuits/parallel-prefix-add/cla-{p}-{q}"
                library.save_block(BlockBundle(json.loads(prefix.with_suffix(".block.json").read_text(encoding="utf-8"))))
                dataset = Dataset.from_dict(json.loads(prefix.with_suffix(".vectors.json").read_text(encoding="utf-8")))
                circuit = json.loads(prefix.with_suffix(".circuit.json").read_text(encoding="utf-8"))
                library.save_program({"circuit": circuit,
                                      "synthesis": {"method": "hierarchy-expansion-and-simplification", "version": 1}}, dataset)
                organization["entries"].setdefault(f"function:{function_id(dataset)}", "parallel-add")
        library._write_organization(organization)
        installed["parallel-add-v1"] = True
        write_json(marker, installed)


def install_prefix_examples(library):
    """Install GEN-06 once, retaining user organization and better solutions."""
    marker = library.root / "example-installations.json"
    with library._lock:
        installed = json.loads(marker.read_text(encoding="utf-8")) if marker.exists() else {}
        if installed.get("prefixes-v1"):
            return
        organization = library._organization()
        folders = [
            {"id": "examples", "parent": None, "name": "Beispiele", "description": "Editierbare Beispiele."},
            {"id": "recursion", "parent": "examples", "name": "Rekursion", "description": "Generative Bit-Templates."},
            {"id": "prefixes", "parent": "recursion", "name": "Präfix-AND & Präfix-XOR",
             "description": "Inklusive Präfixe ab Bit 0; t=1,2,4 vollständig geprüft."},
        ]
        existing = {f["id"] for f in organization["folders"]}
        organization["folders"].extend(f for f in folders if f["id"] not in existing)
        library._write_organization(organization)
        source = Path(__file__).resolve().parents[1] / "examples"
        for kind in PREFIX_EXAMPLES:
            template = Template(json.loads((source / f"templates/recursive-{kind}.abstract.json").read_text(encoding="utf-8")))
            key = library.save_template(template)
            organization["entries"].setdefault(f"template:{key}", "prefixes")
            for width in (1, 2, 4):
                prefix = source / f"circuits/recursive-{kind}/{kind}-{width}"
                library.save_block(BlockBundle(json.loads(prefix.with_suffix(".block.json").read_text(encoding="utf-8"))))
                dataset = Dataset.from_dict(json.loads(prefix.with_suffix(".vectors.json").read_text(encoding="utf-8")))
                circuit = json.loads(prefix.with_suffix(".circuit.json").read_text(encoding="utf-8"))
                library.save_program({"circuit": circuit,
                                      "synthesis": {"method": "hierarchy-expansion-and-simplification", "version": 1}}, dataset)
                organization["entries"].setdefault(f"function:{function_id(dataset)}", "prefixes")
        library._write_organization(organization)
        installed["prefixes-v1"] = True
        write_json(marker, installed)


def install_rotation_examples(library):
    """Install GEN-05 once, retaining user organization and better solutions."""
    marker = library.root / "example-installations.json"
    with library._lock:
        installed = json.loads(marker.read_text(encoding="utf-8")) if marker.exists() else {}
        if installed.get("rotations-v1"):
            return
        organization = library._organization()
        folders = [
            {"id": "examples", "parent": None, "name": "Beispiele", "description": "Editierbare Beispiele."},
            {"id": "recursion", "parent": "examples", "name": "Rekursion", "description": "Generative Bit-Templates."},
            {"id": "rotations", "parent": "recursion", "name": "Rotationen",
             "description": "ROL und ROR modulo t mit festen MUX-Stufen; alle neun Kombinationen t,s_bits=1,2,4 vollständig geprüft."},
        ]
        existing = {f["id"] for f in organization["folders"]}
        organization["folders"].extend(f for f in folders if f["id"] not in existing)
        library._write_organization(organization)
        source = Path(__file__).resolve().parents[1] / "examples"
        for kind in ROTATION_EXAMPLES:
            template = Template(json.loads((source / f"templates/rotate-{kind}.abstract.json").read_text(encoding="utf-8")))
            key = library.save_template(template)
            organization["entries"].setdefault(f"template:{key}", "rotations")
            for t in (1, 2, 4):
                for s_bits in (1, 2, 4):
                    prefix = source / f"circuits/rotate-{kind}/{kind}-{t}-{s_bits}"
                    library.save_block(BlockBundle(json.loads(prefix.with_suffix(".block.json").read_text(encoding="utf-8"))))
                    dataset = Dataset.from_dict(json.loads(prefix.with_suffix(".vectors.json").read_text(encoding="utf-8")))
                    circuit = json.loads(prefix.with_suffix(".circuit.json").read_text(encoding="utf-8"))
                    library.save_program({"circuit": circuit,
                                          "synthesis": {"method": "hierarchy-expansion-and-simplification", "version": 1}}, dataset)
                    organization["entries"].setdefault(f"function:{function_id(dataset)}", "rotations")
        library._write_organization(organization)
        installed["rotations-v1"] = True
        write_json(marker, installed)


def install_barrel_shifter_examples(library):
    """Install GEN-04 once, retaining user organization and better solutions."""
    marker = library.root / "example-installations.json"
    with library._lock:
        installed = json.loads(marker.read_text(encoding="utf-8")) if marker.exists() else {}
        if installed.get("barrel-shifter-v1"):
            return
        organization = library._organization()
        folders = [
            {"id": "examples", "parent": None, "name": "Beispiele", "description": "Editierbare Beispiele."},
            {"id": "recursion", "parent": "examples", "name": "Rekursion", "description": "Generative Bit-Templates."},
            {"id": "barrel-shifter", "parent": "recursion", "name": "Barrel-Shifter",
             "description": "SHL, SHR und SAR mit festen MUX-Stufen; alle neun Kombinationen t,s_bits=1,2,4 vollständig geprüft."},
        ]
        existing = {f["id"] for f in organization["folders"]}
        organization["folders"].extend(f for f in folders if f["id"] not in existing)
        library._write_organization(organization)
        source = Path(__file__).resolve().parents[1] / "examples"
        for kind in BARREL_EXAMPLES:
            template = Template(json.loads((source / f"templates/barrel-{kind}.abstract.json").read_text(encoding="utf-8")))
            key = library.save_template(template)
            organization["entries"].setdefault(f"template:{key}", "barrel-shifter")
            for t in (1, 2, 4):
                for s_bits in (1, 2, 4):
                    prefix = source / f"circuits/barrel-{kind}/{kind}-{t}-{s_bits}"
                    library.save_block(BlockBundle(json.loads(prefix.with_suffix(".block.json").read_text(encoding="utf-8"))))
                    dataset = Dataset.from_dict(json.loads(prefix.with_suffix(".vectors.json").read_text(encoding="utf-8")))
                    circuit = json.loads(prefix.with_suffix(".circuit.json").read_text(encoding="utf-8"))
                    library.save_program({"circuit": circuit,
                                          "synthesis": {"method": "hierarchy-expansion-and-simplification", "version": 1}}, dataset)
                    organization["entries"].setdefault(f"function:{function_id(dataset)}", "barrel-shifter")
        library._write_organization(organization)
        installed["barrel-shifter-v1"] = True
        write_json(marker, installed)


def install_onehot_examples(library):
    """Install GEN-03 once, preserving user organization and better solutions."""
    marker = library.root / "example-installations.json"
    with library._lock:
        installed = json.loads(marker.read_text(encoding="utf-8")) if marker.exists() else {}
        if installed.get("onehot-v1"):
            return
        organization = library._organization()
        folders = [
            {"id": "examples", "parent": None, "name": "Beispiele", "description": "Editierbare Beispiele."},
            {"id": "recursion", "parent": "examples", "name": "Rekursion", "description": "Rekursive Bit-Templates."},
            {"id": "onehot", "parent": "recursion", "name": "Decoder & One-Hot",
             "description": "Decoder mit enable und One-Hot-Encoder mit valid/multiple; w=1,2,4 vollständig geprüft."},
        ]
        existing = {f["id"] for f in organization["folders"]}
        organization["folders"].extend(f for f in folders if f["id"] not in existing)
        library._write_organization(organization)
        source = Path(__file__).resolve().parents[1] / "examples"
        for kind in ONEHOT_EXAMPLES:
            template = Template(json.loads((source / f"templates/recursive-{kind}.abstract.json").read_text(encoding="utf-8")))
            key = library.save_template(template)
            organization["entries"].setdefault(f"template:{key}", "onehot")
            for w in (1, 2, 4):
                prefix = source / f"circuits/recursive-{kind}/{kind}-{w}"
                library.save_block(BlockBundle(json.loads(prefix.with_suffix(".block.json").read_text(encoding="utf-8"))))
                dataset = Dataset.from_dict(json.loads(prefix.with_suffix(".vectors.json").read_text(encoding="utf-8")))
                circuit = json.loads(prefix.with_suffix(".circuit.json").read_text(encoding="utf-8"))
                library.save_program({"circuit": circuit,
                                      "synthesis": {"method": "hierarchy-expansion-and-simplification", "version": 1}}, dataset)
                organization["entries"].setdefault(f"function:{function_id(dataset)}", "onehot")
        library._write_organization(organization)
        installed["onehot-v1"] = True
        write_json(marker, installed)


def install_priority_encoder_examples(library):
    """Install GEN-02 once, retaining existing folders, labels and better nets."""
    marker = library.root / "example-installations.json"
    with library._lock:
        installed = json.loads(marker.read_text(encoding="utf-8")) if marker.exists() else {}
        if installed.get("priority-encoder-v1"):
            return
        organization = library._organization()
        folders = [
            {"id": "examples", "parent": None, "name": "Beispiele", "description": "Editierbare Beispiele."},
            {"id": "recursion", "parent": "examples", "name": "Rekursion", "description": "Rekursive Bit-Templates."},
            {"id": "priority-encoder", "parent": "recursion", "name": "Prioritätsencoder",
             "description": "Niedrigster gesetzter Bitindex mit valid; vollständige 1-, 2- und 4-Bit-Beispiele."},
        ]
        existing = {f["id"] for f in organization["folders"]}
        organization["folders"].extend(f for f in folders if f["id"] not in existing)
        library._write_organization(organization)
        source = Path(__file__).resolve().parents[1] / "examples"
        template = Template(json.loads((source / "templates/recursive-priority-encoder.abstract.json").read_text(encoding="utf-8")))
        key = library.save_template(template)
        organization["entries"].setdefault(f"template:{key}", "priority-encoder")
        for width in (1, 2, 4):
            prefix = source / f"circuits/recursive-priority-encoder/pe-{width}"
            library.save_block(BlockBundle(json.loads(prefix.with_suffix(".block.json").read_text(encoding="utf-8"))))
            dataset = Dataset.from_dict(json.loads(prefix.with_suffix(".vectors.json").read_text(encoding="utf-8")))
            circuit = json.loads(prefix.with_suffix(".circuit.json").read_text(encoding="utf-8"))
            library.save_program({"circuit": circuit,
                                  "synthesis": {"method": "hierarchy-expansion-and-simplification", "version": 1}}, dataset)
            organization["entries"].setdefault(f"function:{function_id(dataset)}", "priority-encoder")
        library._write_organization(organization)
        installed["priority-encoder-v1"] = True
        write_json(marker, installed)


def install_zero_count_examples(library):
    """Install GEN-01 once without changing existing labels or organization."""
    marker = library.root / "example-installations.json"
    with library._lock:
        installed = json.loads(marker.read_text(encoding="utf-8")) if marker.exists() else {}
        if installed.get("zero-counts-v1"):
            return
        organization = library._organization()
        folders = [
            {"id": "examples", "parent": None, "name": "Beispiele", "description": "Editierbare Beispiele."},
            {"id": "recursion", "parent": "examples", "name": "Rekursion", "description": "Rekursive Bit-Templates."},
            {"id": "zero-counts", "parent": "recursion", "name": "Nullbits zählen (CLZ & CTZ)",
             "description": "Führende und nachlaufende Nullbits; vollständige 1-, 2- und 4-Bit-Beispiele."},
        ]
        existing = {f["id"] for f in organization["folders"]}
        organization["folders"].extend(f for f in folders if f["id"] not in existing)
        library._write_organization(organization)
        source = Path(__file__).resolve().parents[1] / "examples"
        for kind in ZERO_COUNT_EXAMPLES:
            template = Template(json.loads((source / f"templates/recursive-{kind}.abstract.json").read_text(encoding="utf-8")))
            key = library.save_template(template)
            organization["entries"].setdefault(f"template:{key}", "zero-counts")
            for width in (1, 2, 4):
                prefix = source / f"circuits/recursive-{kind}/{kind}-{width}"
                library.save_block(BlockBundle(json.loads(prefix.with_suffix(".block.json").read_text(encoding="utf-8"))))
                dataset = Dataset.from_dict(json.loads(prefix.with_suffix(".vectors.json").read_text(encoding="utf-8")))
                circuit = json.loads(prefix.with_suffix(".circuit.json").read_text(encoding="utf-8"))
                library.save_program({"circuit": circuit,
                                      "synthesis": {"method": "hierarchy-expansion-and-simplification", "version": 1}}, dataset)
                organization["entries"].setdefault(f"function:{function_id(dataset)}", "zero-counts")
        library._write_organization(organization)
        installed["zero-counts-v1"] = True
        write_json(marker, installed)


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
            if path.name in {"array-mul.abstract.json", "wallace-mul.abstract.json"}:
                continue  # GEN-11 has its own migration for existing libraries.
            if path.name in {f"signed-{kind}.abstract.json" for kind in ("cmp", "add", "sub", "mul", "div")}:
                continue  # GEN-10 has its own migration for existing libraries.
            if path.name in {"signed-sign.abstract.json", "signed-neg.abstract.json", "signed-abs.abstract.json"}:
                continue  # GEN-09 has its own migration for existing libraries.
            if path.name in {"sat-add.abstract.json", "sat-sub.abstract.json"}:
                continue  # GEN-08 has its own migration for existing libraries.
            if path.name == "parallel-prefix-add.abstract.json":
                continue  # GEN-07 has its own migration for existing libraries.
            if path.name in {f"recursive-{kind}.abstract.json" for kind in PREFIX_EXAMPLES}:
                continue  # GEN-06 has its own migration for existing libraries.
            if path.name in {f"rotate-{kind}.abstract.json" for kind in ROTATION_EXAMPLES}:
                continue  # GEN-05 has its own migration for existing libraries.
            if path.name in {f"barrel-{kind}.abstract.json" for kind in BARREL_EXAMPLES}:
                continue  # GEN-04 has its own migration for existing libraries.
            if path.name in {f"recursive-{kind}.abstract.json" for kind in ONEHOT_EXAMPLES}:
                continue  # GEN-03 has its own migration for existing libraries.
            if path.name == "recursive-priority-encoder.abstract.json":
                continue  # GEN-02 has its own migration for existing libraries.
            if path.name in {f"recursive-{kind}.abstract.json" for kind in ZERO_COUNT_EXAMPLES}:
                continue  # GEN-01 has its own migration for existing libraries.
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
