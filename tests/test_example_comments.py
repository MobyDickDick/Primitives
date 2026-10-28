"""Comment upgrades keep implementations, saved references and user annotations."""
import ast
import copy
import json
from pathlib import Path
import tempfile
import unittest

from primitives.dataset import generate
from primitives.examples import install_arithmetic_comments
from primitives.library import Library, function_id
from primitives.program import template_source
from primitives.synthesis import synthesize
from primitives.templates import Template


ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "examples/templates"
REVISIONS = json.loads((TEMPLATES / "arithmetic-comment-updates.json").read_text(encoding="utf-8"))


def document(name):
    return json.loads((TEMPLATES / f"{name}.abstract.json").read_text(encoding="utf-8"))


def old_document(name):
    result = document(name)
    result["source"] = next(r["previous_source"] for r in REVISIONS if r["template"] == name)
    return result


def dataset(doc):
    program = Template(doc).instantiate({"p": 1, "q": 2})
    circuit = synthesize(program)
    return generate("Division", circuit.inputs, len(circuit.outputs), program=program.spec,
                    ports=program.ports, samples=8), circuit


class ExampleCommentsTests(unittest.TestCase):
    def test_all_sources_only_add_comments_and_keep_identical_nands(self):
        for revision in REVISIONS:
            name = revision["template"]
            current = document(name)
            self.assertEqual(current["source"], (TEMPLATES / f"{name}.prim").read_text(encoding="utf-8"))
            self.assertEqual(ast.dump(ast.parse(template_source(revision["previous_source"]))),
                             ast.dump(ast.parse(template_source(current["source"]))))
            parameters = {"p": 2, "q": 4} if name.startswith("standard-") else {"n": 4}
            self.assertEqual(synthesize(Template(current).instantiate(parameters)),
                             synthesize(Template(old_document(name)).instantiate(parameters)))

    def test_existing_sources_upgrade_without_losing_saved_settings(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".jobs") as directory:
            library = Library(directory)
            original = old_document("standard-div")
            original["name"] = "Meine Division"
            template_id = library.save_template(Template(original))
            ds, circuit = dataset(original)
            saved = library.save_program({"circuit": circuit.to_dict()}, ds)
            library.set_frozen(saved["id"], True)
            previous_id = function_id(ds)
            folder = library.save_folder("Meine Rechner", "Eigene Beschreibung")
            library.move_entry("function", previous_id, folder["id"])
            library.move_entry("template", template_id, folder["id"])
            library.update_function(previous_id, "Meine Rechnung", "Mein Text")
            install_arithmetic_comments(library)
            loaded = library.load_dataset(saved["dataset_id"])
            current_id = function_id(loaded)
            self.assertNotEqual(current_id, previous_id)
            self.assertEqual(loaded.rows, ds.rows)
            self.assertEqual(loaded.metadata["program"]["source"], document("standard-div")["source"])
            template = library.load_template(template_id).to_dict()
            self.assertEqual(template["source"], document("standard-div")["source"])
            self.assertEqual(template["name"], "Meine Division")
            tree = library.tree()
            self.assertEqual(tree["entries"][f"function:{current_id}"], folder["id"])
            self.assertNotIn(f"function:{previous_id}", tree["entries"])
            self.assertEqual(tree["entries"][f"template:{template_id}"], folder["id"])
            program = library.load_program(saved["id"])
            self.assertEqual(program["circuit"], circuit.to_dict())
            self.assertTrue(program["frozen"])
            self.assertEqual(program["dataset_name"], "Meine Rechnung")
            self.assertEqual(program["dataset_metadata"]["description"], "Mein Text")
            self.assertEqual(program["dataset_metadata"]["program"]["source"], template["source"])
            self.assertEqual({d["id"] for d in library.datasets()}, {saved["dataset_id"]})
            snapshot = {p: p.read_bytes() for p in Path(directory).rglob("*.json")}
            install_arithmetic_comments(Library(directory))
            self.assertEqual({p: p.read_bytes() for p in Path(directory).rglob("*.json")}, snapshot)

    def test_custom_sources_and_deleted_examples_stay_untouched(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".jobs") as directory:
            library = Library(directory)
            # User comments and functional edits both make a source their own.
            original = old_document("standard-div")
            for suffix in ("\n# Mein eigener Kommentar\n", "\n", "\nunused = 1\n"):
                custom = copy.deepcopy(original)
                custom["source"] += suffix
                library.save_template(Template(custom))
                ds, _ = dataset(custom)
                library.save_dataset(ds)
            snapshot = {p: p.read_bytes() for folder in ("templates", "datasets")
                        for p in (Path(directory) / folder).glob("*.json")}
            install_arithmetic_comments(library)
            self.assertEqual({p: p.read_bytes() for folder in ("templates", "datasets")
                              for p in (Path(directory) / folder).glob("*.json")}, snapshot)
            # An empty library receives no missing/deleted examples from this refresh.
            empty = Library(Path(directory) / "empty")
            install_arithmetic_comments(empty)
            self.assertEqual(empty.datasets(), [])
            self.assertEqual(empty.templates(), [])


if __name__ == "__main__":
    unittest.main()
