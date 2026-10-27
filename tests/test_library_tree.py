import json
import tempfile
import unittest

from primitives.dataset import preset
from primitives.examples import install_examples
from primitives.library import Library, function_id
from test_synthesis import arithmetic


class LibraryTreeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=".jobs")
        self.library = Library(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_nested_folders_descriptions_moves_and_persistence(self):
        library = self.library
        dataset = preset("xor")
        library.save_dataset(dataset)
        template = library.save_template(arithmetic("ripple-add"))
        folder = library.save_folder("Meine Bausteine", "Erste Zeile\nZweite Zeile")
        child = library.save_folder("Rechnen", "Unterordner", folder["id"])
        library.move_entry("function", function_id(dataset), child["id"])
        library.move_entry("template", template, child["id"])
        before = library.tree()
        self.assertEqual(Library(library.root).tree(), before)
        library.update_function(function_id(dataset), "Neuer Name", "Neue Beschreibung")
        self.assertEqual(library.tree(), before)
        library.save_folder("Umbenannt", "Neue Ordnerbeschreibung", None, child["id"])
        self.assertEqual(library.tree()["entries"], before["entries"])
        with self.assertRaisesRegex(ValueError, "leere Ordner"):
            library.delete_folder(child["id"])
        library.delete_function(function_id(dataset))
        self.assertNotIn(f"function:{function_id(dataset)}", library.tree()["entries"])

    def test_cycles_missing_destinations_duplicates_and_empty_delete(self):
        library = self.library
        a = library.save_folder("A")
        b = library.save_folder("B", parent=a["id"])
        for parent in (a["id"], b["id"]):
            with self.assertRaisesRegex(ValueError, "sich selbst"):
                library.save_folder("A", parent=parent, key=a["id"])
        with self.assertRaisesRegex(ValueError, "bereits"):
            library.save_folder("a")
        with self.assertRaises(ValueError):
            library.save_folder("C", parent="missing")
        with self.assertRaises(ValueError):
            library.move_entry("function", "../outside", "missing")
        with self.assertRaises(FileNotFoundError):
            library.move_entry("template", "missing", a["id"])
        with self.assertRaises(ValueError):
            library.delete_folder("functions")
        library.delete_folder(b["id"])
        library.delete_folder(a["id"])
        self.assertEqual({f["id"] for f in library.tree()["folders"]}, {"functions", "templates"})

    def test_examples_install_once_preserve_edits_and_do_not_resurrect_deletions(self):
        library = self.library
        install_examples(library)
        self.assertEqual(len(library.templates()), 22)
        self.assertEqual(len(library.datasets()), 59)
        # Three new two-channel MUX instances also share existing truth tables.
        self.assertEqual(len(library.programs()), 54)
        self.assertEqual(len(library.blocks()), 51)
        self.assertTrue(all(p["fitness"]["exact_on_dataset"] for p in library.programs()))
        self.assertEqual(sum(p["fitness"]["verified_truth_table"] for p in library.programs()), 50)
        library.save_folder("Eigene Beispiele", "Mein Text", key="examples")
        dataset = library.datasets()[0]
        library.move_entry("function", dataset["function_id"], "functions")
        library.delete_function(library.datasets()[1]["function_id"])
        before = library.tree()
        install_examples(Library(library.root))
        self.assertEqual(library.tree(), before)
        self.assertEqual(len(library.datasets()), 58)

    def test_recursive_templates_upgrade_existing_library_once_without_reinstalling_arithmetic(self):
        library = self.library
        organization = library._organization()
        organization["folders"].extend([
            {"id": "examples", "parent": None, "name": "Meine Beispiele", "description": "Meine Beschreibung"},
            {"id": "recursion", "parent": "examples", "name": "Rekursion", "description": "Eigene Beschreibung"},
        ])
        library._write_organization(organization)
        (library.root / "example-installations.json").write_text(
            json.dumps({"arithmetic-v1": True, "routing-v1": True, "generative-logic-v1": True, "recursive-gt-v1": True, "recursive-equ-v1": True, "recursive-mul-v1": True, "number-of-ones-v1": True,
                        "recursive-msb-div-v1": True, "recursive-max-index-v1": True}), encoding="utf-8")
        install_examples(library)
        self.assertEqual(len(library.templates()), 2)
        self.assertEqual(len(library.datasets()), 0)
        self.assertEqual(len(library.programs()), 0)
        tree = library.tree()
        self.assertEqual(next(f for f in tree["folders"] if f["id"] == "recursion")["description"],
                         "Eigene Beschreibung")
        self.assertTrue(all(folder == "recursion" for folder in tree["entries"].values()))
        # A removed example must stay removed after the migration has completed.
        template_file = next((library.root / "templates").glob("*.json"))
        template_file.unlink()
        after_delete = library.tree()
        install_examples(Library(library.root))
        self.assertEqual(len(library.templates()), 1)
        self.assertEqual(library.tree(), after_delete)

    def test_mul_upgrade_installs_templates_boxes_and_flat_instances_once(self):
        library = self.library
        (library.root / "example-installations.json").write_text(
            json.dumps({"arithmetic-v1": True, "routing-v1": True, "generative-logic-v1": True, "recursive-gt-v1": True, "recursive-equ-v1": True, "recursive-checked-v1": True, "number-of-ones-v1": True,
                        "recursive-msb-div-v1": True, "recursive-max-index-v1": True}), encoding="utf-8")
        install_examples(library)
        self.assertEqual(len(library.templates()), 1)
        self.assertEqual(len(library.datasets()), 3)
        self.assertEqual(len(library.programs()), 3)
        self.assertEqual(len(library.blocks()), 3)
        self.assertTrue(all(p["fitness"]["verified_truth_table"] for p in library.programs()))
        self.assertEqual({p["dataset_name"] for p in library.programs()}, {"MUL<1>", "MUL<2>", "MUL<4>"})
        self.assertTrue(all(folder == "recursion" for folder in library.tree()["entries"].values()))
        library.delete_function(library.datasets()[0]["function_id"])
        template_file = next((library.root / "templates").glob("*.json"))
        template_file.unlink()
        block_file = next((library.root / "blocks").glob("*.json"))
        block_file.unlink()
        before = library.tree()
        install_examples(Library(library.root))
        self.assertEqual(library.tree(), before)
        self.assertEqual(len(library.datasets()), 2)
        self.assertEqual(len(library.templates()), 0)
        self.assertEqual(len(library.blocks()), 2)


if __name__ == "__main__":
    unittest.main()
