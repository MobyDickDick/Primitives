import json
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from primitives.server import make_server
from primitives.runner import ROOT
from primitives.blocks import BlockBundle
from primitives.circuit import Circuit
from primitives.dataset import preset
from primitives.library import Library, function_id


class ServerTests(unittest.TestCase):
    def setUp(self):
        (ROOT / ".jobs").mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT / ".jobs")
        self.server = make_server(0, self.tmp.name, background=False)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.server.executor.shutdown()
        self.thread.join(timeout=5)
        self.tmp.cleanup()

    def request(self, path, obj=None, headers=None):
        req = Request(self.base + path, data=json.dumps(obj).encode() if obj is not None else None,
                      headers={"Content-Type": "application/json", **(headers or {})})
        with urlopen(req, timeout=10) as response:
            return json.load(response)

    def test_end_to_end_api(self):
        with urlopen(self.base) as response:
            self.assertIn(b"PRIMITIVES", response.read())
        self.assertIn("xor", self.request("/api/catalog")["presets"])
        d = self.request("/api/datasets", {"name": "xor", "inputs": 2, "outputs": 1, "expression": "x0 ^ x1"})
        job = self.request("/api/search", {"dataset_id": d["id"], "config": {"backend": "python", "gates": 8, "generations": 300}})
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            state = self.request("/api/jobs/" + job["job_id"])
            if state["status"] in ("done", "failed"):
                break
            time.sleep(0.03)
        self.assertEqual(state["status"], "done", state)
        self.assertTrue(state["result"]["fitness"]["verified_truth_table"])
        saved = self.request("/api/programs/" + state["result"]["id"])
        self.assertEqual(saved["search"]["selection"], "tournament")
        self.assertEqual(saved["search"]["tournament_size"], 3)
        self.assertEqual(saved["search"]["parent_population"], 24)
        self.assertLessEqual(saved["search"]["evaluations"], saved["search"]["evaluation_budget"])
        ancestry = saved["search"]["ancestry"]
        self.assertEqual(ancestry, state["result"]["search"]["ancestry"])
        self.assertIn(ancestry["root"], [node["id"] for node in ancestry["nodes"]])
        self.assertEqual(ancestry["transformations"][-1]["circuit"], saved["circuit"])
        evaluated = self.request("/api/evaluate", {"circuit": saved["circuit"], "bits": [1, 0]})
        self.assertEqual(evaluated["outputs"], [1])
        retest = self.request("/api/search", {"dataset_id": d["id"], "config": {
            "backend": "python", "gates": 1, "population": 2, "generations": 2}})
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            state = self.request("/api/jobs/" + retest["job_id"])
            if state["status"] in ("done", "failed"):
                break
            time.sleep(0.03)
        self.assertEqual(state["status"], "done", state)
        self.assertEqual(state["result"]["id"], saved["id"])
        self.assertFalse(state["result"]["comparison"]["accepted"])
        self.assertEqual(state["result"]["search"]["ancestry"], ancestry)
        self.assertGreater(state["result"]["comparison"]["candidate_fitness"]["errors"], 0)
        self.assertEqual([p["id"] for p in self.request("/api/catalog")["programs"]], [saved["id"]])

    def test_template_specialization_generation_debug_and_roundtrip(self):
        from test_templates import template
        spec = template(2)
        abstract = {"schema": 1, "kind": "template", "name": "Abstrakte Addition", "parameters": ["n"],
                    **{k: spec[k] for k in ("source", "limits", "interface", "conditions")}}
        saved_template = self.request("/api/templates", abstract)
        self.assertEqual(self.request("/api/catalog")["datasets"], [])
        self.assertEqual(self.request("/api/catalog")["templates"][0]["parameters"], ["n"])
        portable = self.request("/api/templates/" + saved_template["id"])
        self.assertEqual(portable["parameters"], ["n"])
        self.assertEqual(self.request("/api/templates", portable)["id"], saved_template["id"])
        concrete = self.request("/api/templates/specialize", {"template_id": saved_template["id"], "parameters": {"n": 8}})
        self.assertEqual(concrete["inputs"], 16)
        with self.assertRaises(HTTPError) as caught:
            self.request("/api/templates/specialize", {"template_id": saved_template["id"], "parameters": {"n": 6}})
        self.assertEqual(caught.exception.code, 400)
        caught.exception.close()
        specialized = self.request("/api/templates/specialize", {"program": spec})
        self.assertEqual((specialized["inputs"], specialized["outputs"]), (4, 3))
        self.assertEqual(specialized["interface"]["outputs"][0]["bits"], 3)
        request = {**specialized, "name": "Rekursiver Addierer", "samples": 16}
        job = self.request("/api/datasets/generate", request)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            state = self.request("/api/jobs/" + job["job_id"])
            if state["status"] in ("done", "failed"):
                break
            time.sleep(.02)
        self.assertEqual(state["status"], "done", state)
        saved = state["result"]
        loaded = self.request("/api/datasets/" + saved["id"])
        self.assertEqual(loaded["metadata"]["program"]["interface"], spec["interface"])
        self.assertEqual(self.request("/api/datasets", loaded)["dataset"], loaded)
        debug = self.request("/api/source-debug/start", {
            "program": spec, "interface": specialized["interface"], "x": 15})
        final = self.request(f'/api/source-debug/{debug["id"]}/continue', {})
        self.assertEqual(final["status"], "done", final)
        self.assertEqual(final["result"], ["6"])

    def test_manual_circuit_edits_recheck_vectors_and_drop_search_claims(self):
        ds = self.request("/api/datasets", {"name": "nand", "inputs": 2, "outputs": 1,
                                             "expression": "1-(x0 & x1)"})
        original = {"inputs": 2, "gates": [[0, 1]], "outputs": [2]}
        edited = {"inputs": 2, "gates": [[0, 0]], "outputs": [2]}
        checked = self.request("/api/circuits/check", {"circuit": original, "dataset_id": ds["id"]})
        self.assertTrue(checked["fitness"]["verified_truth_table"])
        changed = self.request("/api/circuits/check", {"circuit": edited, "dataset_id": ds["id"],
                                                     "search": {"ancestry": "stale"}, "fitness": checked["fitness"]})
        self.assertEqual(changed["fitness"]["errors"], 1)
        self.assertTrue(changed["manual_edit"])
        self.assertNotIn("search", changed)
        self.assertNotIn("id", changed)
        self.assertNotIn("hierarchy", changed)
        self.assertEqual(self.request("/api/catalog")["programs"], [])
        standalone = self.request("/api/circuits/check", {"circuit": edited})
        self.assertNotIn("fitness", standalone)
        for bad in ({"inputs": 2, "gates": [[2, 0]], "outputs": [2]},
                    {"inputs": 2, "gates": [], "outputs": [2]},
                    {"inputs": 1, "gates": [], "outputs": [0]}):
            with self.assertRaises(HTTPError) as caught:
                self.request("/api/circuits/check", {"circuit": bad, "dataset_id": ds["id"]})
            self.assertEqual(caught.exception.code, 400)
            caught.exception.close()

    def test_search_restarts_islands_and_saved_diversity(self):
        config = {"backend": "python", "gates": 1, "population": 6, "generations": 4,
                  "restarts": 2, "islands": 3, "migration_interval": 1}
        job = self.request("/api/search", {"dataset": preset("xor").to_dict(), "config": config})
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            state = self.request("/api/jobs/" + job["job_id"])
            if state["status"] in ("done", "failed"):
                break
            time.sleep(.02)
        self.assertEqual(state["status"], "done", state)
        saved = self.request("/api/programs/" + state["result"]["id"])
        self.assertEqual(saved["search"]["evaluations"], 25)
        self.assertEqual(saved["search"]["restarts_completed"], 2)
        self.assertEqual(saved["search"]["tournament_size"], 2)
        self.assertEqual(saved["search"]["runs"][0]["island_populations"], [2, 2, 2])
        self.assertEqual(saved["search"]["diversity"]["size"], 6)
        for change in ({"islands": 4}, {"restarts": 32}, {"migration_interval": 0}):
            with self.subTest(change=change), self.assertRaises(HTTPError) as error:
                self.request("/api/search", {"dataset": preset("xor").to_dict(), "config": {**config, **change}})
            self.assertEqual(error.exception.code, 400)
            error.exception.close()

    def test_function_names_descriptions_and_portable_documents(self):
        obj = {"name": "Meine Addition", "description": "Zwei Bits addieren.",
               "operation": {"definition": "ADD", "parameters": {"a_bits": 1, "b_bits": 1, "result_bits": 2}}}
        saved = self.request("/api/datasets", obj)
        entry = self.request("/api/catalog")["datasets"][0]
        self.assertEqual(entry["function_name"], obj["name"])
        self.assertEqual(entry["description"], obj["description"])
        key = entry["function_id"]
        result = self.request(f"/api/functions/{key}/details", {"name": "Addition mit Übertrag", "description": "Ergebnis: 0 bis 2.\nZwei Ausgangsbits."})
        self.assertEqual(result["dataset_ids"], [saved["id"]])
        document = self.request("/api/datasets/" + saved["id"])
        self.assertEqual(document["name"], result["name"])
        self.assertEqual(document["metadata"]["description"], result["description"])
        self.assertEqual(document["rows"], saved["dataset"]["rows"])
        # Saving the loaded reference from the editor can update its labels again.
        resaved = self.request("/api/datasets", {**obj, "name": "Neu aus dem Editor", "description": ""})
        self.assertEqual(resaved["dataset"]["name"], "Neu aus dem Editor")
        for item in self.request("/api/catalog")["datasets"]:
            self.assertEqual(item["function_name"], "Neu aus dem Editor")
            self.assertEqual(item["description"], "")
        for invalid in ({"name": " "}, {"name": "ok", "description": 2}, {"name": "ok", "description": "x" * 4001}):
            with self.assertRaises(HTTPError) as caught:
                self.request(f"/api/functions/{key}/details", invalid)
            self.assertEqual(caught.exception.code, 400)
            caught.exception.close()
        with urlopen(self.base + "/#hilfe") as response:
            page = response.read().decode()
        self.assertIn('id="page-help"', page)
        self.assertIn('id="page-functions"', page)
        self.assertIn('id="dataset-description"', page)

    def test_neutral_search_simplifies_and_exports_separate_phases(self):
        redundant = Circuit(2, ((0, 1), (2, 2), (3, 3)), (4,))
        Library(self.tmp.name).save_program({"circuit": redundant.to_dict()}, preset("nand"))
        job = self.request("/api/search", {"dataset": preset("nand").to_dict(), "config": {
            "backend": "python", "gates": 3, "neutral": True, "repair_cases": 4}})
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            state = self.request("/api/jobs/" + job["job_id"])
            if state["status"] in ("done", "failed"):
                break
            time.sleep(.02)
        self.assertEqual(state["status"], "done", state)
        saved = self.request("/api/programs/" + state["result"]["id"])
        self.assertTrue(saved["search"]["neutral"])
        self.assertEqual(saved["search"]["objective"], "errors_only")
        self.assertEqual(saved["search"]["evaluations"], 1)
        self.assertEqual(saved["search"]["phases"][0]["result"]["gates"], 3)
        self.assertEqual(saved["search"]["phases"][1]["removed_gates"], 2)
        ancestry = saved["search"]["ancestry"]
        self.assertEqual(ancestry["nodes"][0]["operator"], "incumbent")
        self.assertEqual([t["operation"] for t in ancestry["transformations"]], ["compact", "simplification"])
        self.assertEqual(saved["fitness"]["gates"], 1)
        self.assertTrue(saved["fitness"]["verified_truth_table"])
        with urlopen(self.base) as response:
            self.assertIn('id="neutral"', response.read().decode())
        with self.assertRaises(HTTPError) as caught:
            self.request("/api/search", {"dataset": preset("nand").to_dict(), "config": {"neutral": "true"}})
        self.assertEqual(caught.exception.code, 400)
        caught.exception.close()

    def test_source_debug_step_continue_stop_reset_and_isolation(self):
        from test_program_debug import PORTS, SUM
        obj = {"interface": PORTS, "program": {"version": 1, "source": SUM}, "x": 5}
        first = self.request("/api/source-debug/start", obj)
        second = self.request("/api/source-debug/start", {**obj, "x": 0})
        key = first["id"]
        self.assertEqual(first["variables"], {"n": "5"})
        self.assertEqual(first["steps"], 0)
        step = self.request(f"/api/source-debug/{key}/step", {})
        self.assertEqual(step["variables"]["s"], "0")
        stopped = self.request(f"/api/source-debug/{key}/stop", {})
        self.assertEqual(stopped["status"], "stopped")
        self.assertEqual(stopped["pc"], step["pc"])
        reset = self.request(f"/api/source-debug/{key}/reset", {})
        self.assertEqual(reset, first)
        done = self.request(f"/api/source-debug/{key}/continue", {})
        self.assertEqual(done["status"], "done")
        self.assertEqual(done["result"], ["10"])
        self.assertEqual(done["outputs"], {"c": 10})
        other = self.request(f'/api/source-debug/{second["id"]}/continue', {})
        self.assertEqual(other["result"], ["0"])
        self.assertEqual(self.request("/api/catalog")["datasets"], [])
        self.assertEqual(self.request(f"/api/source-debug/{key}/close", {})["status"], "closed")
        with self.assertRaises(HTTPError) as caught:
            self.request(f"/api/source-debug/{key}/step", {})
        caught.exception.close()

    def test_source_debug_limits_compile_errors_and_session_cap(self):
        from test_program_debug import PORTS
        obj = {"interface": PORTS, "x": 3, "program": {"version": 1,
               "source": 'label("loop")\ngoto("loop")\nreturn 0', "limits": {"steps": 1000}}}
        first = self.request("/api/source-debug/start", obj)
        key = first["id"]
        state = self.request(f"/api/source-debug/{key}/continue", {})
        self.assertEqual(state["instructions"], 100)
        self.assertEqual(state["status"], "paused")
        self.assertEqual(self.request(f"/api/source-debug/{key}/stop", {})["status"], "stopped")
        for _ in range(10):
            state = self.request(f"/api/source-debug/{key}/continue", {})
            if state["status"] == "failed": break
        self.assertEqual(state["status"], "failed")
        self.assertIn("Anweisungsbudget", state["error"])
        with self.assertRaises(HTTPError) as caught:
            self.request("/api/source-debug/start", {**obj, "program": {"version": 1, "source": 'goto("missing")\nreturn 0'}})
        caught.exception.close()
        for _ in range(32):
            latest = self.request("/api/source-debug/start", {**obj, "program": {"version": 1, "source": "return n"}})
        with self.assertRaises(HTTPError) as caught:
            self.request(f"/api/source-debug/{key}/reset", {})
        caught.exception.close()
        self.assertEqual(self.request(f'/api/source-debug/{latest["id"]}/continue', {})["result"], ["3"])

    def test_contradiction_and_origin_rejected(self):
        for obj, headers in (({"name": "bad", "inputs": 1, "outputs": 1, "rows": [[0, 0], [0, 1]]}, {}),
                             ({}, {"Origin": "https://foreign.invalid"})):
            with self.assertRaises(HTTPError) as caught:
                self.request("/api/datasets", obj, headers)
            self.assertEqual(caught.exception.code, 400)
            caught.exception.close()

    def wait_job(self, key):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            job = self.request("/api/jobs/" + key)
            if job["status"] in ("done", "failed", "cancelled"):
                return job
            time.sleep(0.01)
        self.fail(f"Auftrag {key} nicht beendet.")

    def test_source_program_generation_import_and_restart(self):
        ports = {"inputs": [{"name": "n", "bits": 4}], "outputs": [{"name": "c", "bits": 8}]}
        program = {"version": 1, "source": "s = 0\nfor i in range(n):\n    s += i\nreturn s"}
        obj = {"name": "Summe for", "inputs": 4, "outputs": 8, "interface": ports, "program": program}
        key = self.request("/api/datasets/generate", obj)["job_id"]
        job = self.wait_job(key)
        self.assertEqual(job["status"], "done", job)
        self.assertEqual(job["kind"], "dataset")
        saved = job["result"]; ds = saved["dataset"]
        self.assertTrue(ds["exhaustive"])
        self.assertEqual(ds["metadata"]["program"]["source"], program["source"])
        for row in ds["rows"]:
            n = sum(b << i for i, b in enumerate(row[:4]))
            self.assertEqual(sum(b << i for i, b in enumerate(row[4:])), n * (n - 1) // 2)
        self.assertEqual(self.request("/api/datasets", ds), saved)
        self.assertEqual(self.request("/api/datasets", obj), saved)
        self.server.shutdown(); self.server.server_close(); self.server.executor.shutdown()
        self.thread.join(timeout=5)
        self.server = make_server(0, self.tmp.name, background=False)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        self.assertEqual(self.request("/api/datasets/" + saved["id"]), ds)
        self.assertEqual(len(self.request("/api/catalog")["datasets"]), 1)
        # A simple source program feeds the existing combinatorial evolution unchanged.
        xor = self.request("/api/datasets", {"name": "program xor", "inputs": 2, "outputs": 1,
            "interface": {"inputs": [{"name": "a", "bits": 1}, {"name": "b", "bits": 1}],
                          "outputs": [{"name": "c", "bits": 1}]}, "program": {"version": 1, "source": "c = a ^ b\nreturn c"}})
        job = self.wait_job(self.request("/api/search", {"dataset_id": xor["id"], "config": {
            "backend": "python", "gates": 8, "generations": 300}})["job_id"])
        self.assertEqual(job["status"], "done", job)
        self.assertTrue(job["result"]["fitness"]["verified_truth_table"])
        self.assertEqual(job["result"]["dataset_metadata"], xor["dataset"]["metadata"])

    def test_bit_array_program_generation_and_roundtrip(self):
        source = "# Bitreihenfolge umkehren\na = bits(n, 4)  # LSB-first\nreturn pack(a[::-1])"
        obj = {"name": "Bitumkehr", "inputs": 4, "outputs": 4,
               "interface": {"inputs": [{"name": "n", "bits": 4}], "outputs": [{"name": "c", "bits": 4}]},
               "program": {"version": 1, "source": source}}
        job = self.wait_job(self.request("/api/datasets/generate", obj)["job_id"])
        self.assertEqual(job["status"], "done", job)
        saved = job["result"]
        ds = saved["dataset"]
        self.assertEqual(ds["metadata"]["program"]["source"], source)
        self.assertEqual(len(ds["rows"]), 16)
        self.assertTrue(all(row[4:] == row[:4][::-1] for row in ds["rows"]))
        self.assertEqual(self.request("/api/datasets", ds), saved)
        self.assertEqual(self.request("/api/datasets/" + saved["id"]), ds)

    def test_delete_function_stops_background_and_persists(self):
        library = Library(self.tmp.name)
        dataset = preset("and")
        saved = library.save_program({"circuit": Circuit(2, (), (0,)).to_dict()}, dataset)
        sample_id = library.save_dataset(preset("and", samples=2, seed=8))
        other_id = library.save_dataset(preset("or"))
        optimizer = self.server.optimizer
        optimizer.enabled = True
        optimizer._next_due = 0
        optimizer.tick()
        worker = optimizer._process
        self.assertIsNotNone(worker)
        path = f"/api/functions/{function_id(dataset)}/delete"
        # The deletion endpoint applies the same origin checks as other mutations.
        with self.assertRaises(HTTPError) as caught:
            self.request(path, {}, {"Origin": "https://foreign.invalid"})
        self.assertEqual(caught.exception.code, 400)
        caught.exception.close()
        deleted = self.request(path, {})
        self.assertEqual(set(deleted["dataset_ids"]), {saved["dataset_id"], sample_id})
        self.assertEqual(deleted["program_ids"], [saved["id"]])
        self.assertIsNotNone(worker.poll())
        self.assertIsNone(optimizer._process)
        optimizer._next_due = 0
        optimizer.tick()
        self.assertIsNone(optimizer._process)
        catalog = self.request("/api/catalog")
        self.assertEqual([d["id"] for d in catalog["datasets"]], [other_id])
        self.assertEqual(catalog["programs"], [])
        self.assertEqual([d["id"] for d in Library(self.tmp.name).datasets()], [other_id])
        for endpoint in ("/api/datasets/" + saved["dataset_id"], "/api/programs/" + saved["id"]):
            with self.assertRaises(HTTPError) as caught: self.request(endpoint)
            self.assertEqual(caught.exception.code, 404)
            caught.exception.close()

    def test_delete_function_rejects_active_job_then_allows_after_cancel(self):
        saved = self.request("/api/datasets", preset("and").to_dict())
        path = f"/api/functions/{function_id(preset('and'))}/delete"
        # Hold the worker until the active-job rejection has been checked.
        entered, release = threading.Event(), threading.Event()
        def waiting_search(*args, **kwargs):
            entered.set()
            release.wait(5)
            from primitives.evolution import check_cancelled
            check_cancelled(kwargs["cancel_event"])
        with patch("primitives.server.search", side_effect=waiting_search):
            key = self.request("/api/search", {"dataset_id": saved["id"], "config": {"backend": "python"}})["job_id"]
            try:
                self.assertTrue(entered.wait(5))
                with self.assertRaises(HTTPError) as caught: self.request(path, {})
                self.assertEqual(caught.exception.code, 400)
                self.assertIn("laufenden Auftrag", caught.exception.read().decode())
                caught.exception.close()
                self.assertEqual(len(self.request("/api/catalog")["datasets"]), 1)
                self.request(f"/api/jobs/{key}/cancel", {})
            finally:
                release.set()
            self.assertEqual(self.wait_job(key)["status"], "cancelled")
        self.request(path, {})
        self.assertEqual(self.request("/api/catalog")["datasets"], [])

    def test_source_program_cancel_errors_and_no_partial_datasets(self):
        ports = {"inputs": [{"name": "n", "bits": 16}], "outputs": [{"name": "c", "bits": 8}]}
        obj = {"name": "Cancel source", "inputs": 16, "outputs": 8, "samples": 65536, "interface": ports,
               "program": {"version": 1, "source": "s = 0\nfor i in range(1000):\n    s += 1\nreturn 0",
                           "limits": {"steps": 100000, "iterations": 100000, "total_steps": 5000000}}}
        key = self.request("/api/datasets/generate", obj)["job_id"]
        self.assertIn(self.request("/api/jobs/" + key)["status"], ("queued", "running"))
        self.assertEqual(self.request(f"/api/jobs/{key}/cancel", {})["status"], "cancelling")
        self.assertEqual(self.wait_job(key)["status"], "cancelled")
        self.assertEqual(self.request("/api/catalog")["datasets"], [])
        sources = ["while True:\n    c = 0\nreturn c", "if n:\n    return 1", "return 1 // 0", "import os\nreturn 0",
                   "if n < 3:\n    return n\nwhile True:\n    c = 0\nreturn c"]
        for source in sources:
            with self.subTest(source=source):
                obj["program"] = {"version": 1, "source": source, "limits": {"steps": 100}}
                job = self.wait_job(self.request("/api/datasets/generate", obj)["job_id"])
                self.assertEqual(job["status"], "failed", job)
                self.assertIn("Zeile", job["error"])
                self.assertEqual(self.request("/api/catalog")["datasets"], [])
        obj["program"] = {"version": 1, "source": "return 0"}
        with self.assertRaises(HTTPError) as caught:
            self.request("/api/datasets", {**obj, "expression": "n"})
        self.assertEqual(caught.exception.code, 400); caught.exception.close()
        job = self.wait_job(self.request("/api/datasets/generate", obj)["job_id"])
        self.assertEqual(job["status"], "done", job)
        self.assertEqual(len(self.request("/api/catalog")["datasets"]), 1)

    def test_nested_blocks_roundtrip_evaluate_compose_and_restart(self):
        bundle = json.loads((ROOT / "examples" / "blocks" / "ripple-adder-2.json").read_text(encoding="utf-8"))
        saved = self.request("/api/blocks", bundle)
        self.assertEqual(saved["summary"]["definitions"], 6)
        key = saved["summary"]["id"]
        self.assertEqual(self.request("/api/blocks/" + key), bundle)
        self.assertEqual(self.request("/api/blocks/evaluate", {"block_id": key, "bits": [1, 1, 1, 1, 1]})["outputs"], [1, 1, 1])
        expanded = self.request("/api/blocks/expand", {"block_id": key})
        self.assertEqual(expanded["hierarchy"], bundle)
        ds = self.request("/api/datasets", {"block": bundle, "samples": 32})["dataset"]
        self.assertTrue(ds["exhaustive"])
        self.assertEqual(ds["metadata"]["hierarchy"], bundle)
        self.assertEqual(self.request("/api/datasets", ds)["dataset"], ds)
        wrapped = BlockBundle(bundle).wrap("HTTP nested wrapper")
        created = self.request("/api/blocks", {"definition": wrapped.definition, "dependencies": [key]})
        self.assertEqual(created["block"], wrapped.to_dict())
        invalid = wrapped.definition
        invalid["nodes"][0]["inputs"]["a"] = [{"input": "a", "bit": 9}]
        for obj in ({"definition": invalid, "dependencies": [key]},
                    {"definition": wrapped.definition, "dependencies": []}):
            with self.assertRaises(HTTPError) as caught: self.request("/api/blocks", obj)
            self.assertEqual(caught.exception.code, 400)
            caught.exception.close()
        self.server.shutdown(); self.server.server_close(); self.server.executor.shutdown()
        self.thread.join(timeout=5)
        self.server = make_server(0, self.tmp.name, background=False)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        catalog = self.request("/api/catalog")
        self.assertEqual({b["id"] for b in catalog["blocks"]}, {key, wrapped.root})
        self.assertEqual(self.request("/api/blocks/" + wrapped.root), wrapped.to_dict())

    def test_width_variants_named_ports_import_and_search(self):
        catalog = self.request("/api/catalog")
        self.assertIn("ADD", catalog["operations"])
        self.assertEqual(catalog["programs"], [])
        variant = self.request("/api/operations/variant", {"definition": "SUB", "parameters": {
            "a_bits": 2, "b_bits": 3, "result_bits": 3, "flag": True}})
        self.assertEqual(variant["expression"]["c"], "a-b")
        self.assertEqual(variant["interface"]["outputs"][1]["name"], "borrow")
        obj = {"operation": {"definition": "ADD", "parameters": {
            "a_bits": 2, "b_bits": 3, "result_bits": 4, "flag": True}}, "samples": 32}
        saved = self.request("/api/datasets", obj)
        ds = saved["dataset"]
        self.assertEqual((ds["inputs"], ds["outputs"], len(ds["rows"])), (5, 5, 32))
        self.assertEqual([p["offset"] for p in ds["metadata"]["interface"]["inputs"]], [0, 2])
        self.assertEqual(self.request("/api/datasets/" + saved["id"]), ds)
        self.assertEqual(self.request("/api/datasets", ds)["dataset"], ds)
        named = self.request("/api/datasets", {"name": "named XOR", "inputs": 2, "outputs": 1,
            "interface": {"inputs": [{"name": "left", "bits": 1}, {"name": "right", "bits": 1}],
                          "outputs": [{"name": "result", "bits": 1}]}, "expression": {"result": "left ^ right"}})
        job = self.request("/api/search", {"dataset_id": named["id"], "config": {
            "backend": "python", "gates": 8, "generations": 300}})
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            state = self.request("/api/jobs/" + job["job_id"])
            if state["status"] in ("done", "failed"): break
            time.sleep(0.03)
        self.assertEqual(state["status"], "done", state)
        self.assertTrue(state["result"]["fitness"]["verified_truth_table"])
        self.assertEqual(state["result"]["dataset_metadata"], named["dataset"]["metadata"])
        for invalid in ({"operation": {"definition": "ADD", "parameters": {"a_bits": 32, "b_bits": 2}}},
                        {**obj, "operation": {"definition": "ADD", "parameters": {"a_bits": 2, "b_bits": 2,
                            "result_bits": 2, "overflow": "error"}}}):
            with self.assertRaises(HTTPError) as caught: self.request("/api/datasets", invalid)
            self.assertEqual(caught.exception.code, 400)
            caught.exception.close()

    def test_block_debug_views_and_separate_persistent_instance_layouts(self):
        from primitives.library import Library
        bundle = BlockBundle(json.loads((ROOT / "examples/blocks/ripple-adder-2.json").read_text(encoding="utf-8")))
        key = self.request("/api/blocks", bundle.to_dict())["summary"]["id"]
        root = self.request("/api/blocks/view", {"block_id": key})
        instances = [n for n in root["circuit"]["view_nodes"] if n["kind"] == "instance"]
        self.assertEqual([n["id"] for n in instances], ["low", "high"])
        for path in ([], ["low"], ["high"], ["low", "first", "sum"]):
            request = {"block_id": key, "path": path}
            view = self.request("/api/blocks/view", request)
            c = view["circuit"]
            nodes = c.get("view_nodes")
            count = len(nodes) if nodes else c["inputs"] + len(c["gates"]) + len(c["outputs"])
            positions = [{"x": 40 + 288 * i, "y": 100 + 10 * len(path)} for i in range(count)]
            if nodes:
                node = next(n for n in nodes if n["sources"])
                wire = f'{node["sources"][0]}:{node["ref"]}:0:{node["sourceBits"][0]}'
            else:
                wire = f'{c["gates"][0][0]}:{c["inputs"]}:0'
            wires = {wire: [{"x": 236, "y": 100}, {"x": 300, "y": 100}]}
            saved = self.request("/api/blocks/layout/save", {**request, "positions": positions, "wires": wires})
            self.assertEqual(saved, {"positions": positions, "wires": wires})
            self.assertEqual(self.request("/api/blocks/layout/load", request), saved)
            reloaded = Library(self.tmp.name).load_layout_data(Circuit.from_dict(c), identity={"block": key, "path": path})
            self.assertEqual(reloaded, saved)
            with self.assertRaises(HTTPError) as caught:
                self.request("/api/blocks/layout/save", {**request, "positions": positions, "wires": {"bogus": []}})
            self.assertEqual(caught.exception.code, 400); caught.exception.close()
        high = self.request("/api/blocks/layout/load", {"block_id": key, "path": ["high"]})
        low_request = {"block_id": key, "path": ["low"]}
        low = self.request("/api/blocks/layout/load", low_request)
        low["positions"][0]["x"] = 999
        self.request("/api/blocks/layout/save", {**low_request, **low})
        self.assertEqual(self.request("/api/blocks/layout/load", {"block_id": key, "path": ["high"]}), high)
        for path in (["absent"], "low", ["low"] * 33):
            with self.assertRaises(HTTPError) as caught:
                self.request("/api/blocks/view", {"block_id": key, "path": path})
            self.assertEqual(caught.exception.code, 400); caught.exception.close()
        with urlopen(self.base + "/block-debug.js") as response:
            self.assertIn(b"BlockDebug", response.read())

    def test_cpu_operations_catalog_roundtrip_and_rejection(self):
        operations = self.request("/api/catalog")["operations"]
        self.assertTrue({"DIV", "IsZero", "IsNegative", "SHL", "SHR", "SAR", "MUX", "INC", "DEC", "LT"} <= operations.keys())
        for name, parameters, inputs, outputs in (
                ("DIV", {"signed": True}, 6, 5), ("MUX", {}, 5, 2),
                ("SAR", {"signed": True, "shift": 32}, 3, 3), ("IsZero", {}, 3, 1)):
            spec = {"definition": name, "parameters": parameters}
            preview = self.request("/api/operations/variant", spec)
            saved = self.request("/api/datasets", {"operation": spec})
            ds = saved["dataset"]
            self.assertEqual((ds["inputs"], ds["outputs"]), (inputs, outputs))
            self.assertEqual(ds["metadata"]["interface"], preview["interface"])
            self.assertEqual(self.request("/api/datasets/" + saved["id"]), ds)
            self.assertEqual(self.request("/api/datasets", ds)["dataset"], ds)
            self.assertTrue(ds["exhaustive"])
        for name, params in (("SHL", {"shift": -1}), ("ADD", {"shift": 2}),
                             ("DIV", {"result_bits": 31}), ("EQ", {"result_bits": 2})):
            with self.assertRaises(HTTPError) as caught:
                self.request("/api/datasets", {"operation": {"definition": name, "parameters": params}})
            self.assertEqual(caught.exception.code, 400)
            caught.exception.close()

    def test_defined_functions_survive_server_restart_without_search(self):
        expected = {"ADD(1,1,2)", "ADD(4,4,5)", "ADD(8,8,9)", "ADD(1,1,16)"}
        for a, b, c in ((1, 1, 2), (4, 4, 5), (8, 8, 9), (1, 1, 16)):
            saved = self.request("/api/datasets", {"operation": {"definition": "ADD", "parameters": {
                "a_bits": a, "b_bits": b, "result_bits": c}}})
            self.assertEqual(saved["dataset"]["name"], f"ADD({a},{b},{c})")
        self.server.shutdown()
        self.server.server_close()
        self.server.executor.shutdown()
        self.thread.join(timeout=5)
        self.server = make_server(0, self.tmp.name, background=False)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        catalog = self.request("/api/catalog")
        self.assertEqual(catalog["programs"], [])
        self.assertEqual({d["function_name"] for d in catalog["datasets"]}, expected)
        self.assertEqual(len({d["function_id"] for d in catalog["datasets"]}), 4)
        for entry in catalog["datasets"]:
            ds = self.request("/api/datasets/" + entry["id"])
            self.assertEqual(ds["metadata"]["operation"], entry["metadata"]["operation"])

    def test_own_arithmetic_formula_with_two_outputs(self):
        source = "c = mod(a+b,2^4), e = div(a+b,2^4)"
        parsed = self.request("/api/formulas/parse", {"formula": source})
        self.assertEqual(set(parsed["expression"]), {"c", "e"})
        converted = self.request("/api/formulas/convert", {"expression": {"c": "a^b"}})
        self.assertIn("xor(a, b)", converted["formula"])
        obj = {"name": "User formula", "inputs": 8, "outputs": 5, "formula": source,
            "interface": {"inputs": [{"name": "a", "bits": 4}, {"name": "b", "bits": 4}],
                          "outputs": [{"name": "c", "bits": 4}, {"name": "e", "bits": 1}]}}
        saved = self.request("/api/datasets", obj)
        self.assertTrue(saved["dataset"]["exhaustive"])
        self.assertEqual(saved["dataset"]["metadata"]["formula"]["source"], source)
        for row in saved["dataset"]["rows"]:
            integer = lambda bs: sum(b << i for i, b in enumerate(bs))
            total = integer(row[:4]) + integer(row[4:8])
            self.assertEqual(integer(row[8:12]), total % 16)
            self.assertEqual(row[-1], total // 16)
        self.assertEqual(self.request("/api/datasets/" + saved["id"]), saved["dataset"])
        self.assertEqual(self.request("/api/datasets", saved["dataset"])["dataset"], saved["dataset"])
        for formula in ("c=a; c=b", "c=div(a,0); e=0", "c=a+b; e=c"):
            with self.assertRaises(HTTPError) as caught: self.request("/api/datasets", {**obj, "formula": formula})
            self.assertEqual(caught.exception.code, 400)
            caught.exception.close()

    def test_infix_parse_api(self):
        for expression in ("(1) ⊼ ((2) ⊼ (3))", "(1,(2,3))"):
            parsed = self.request("/api/parse", {"expression": expression, "inputs": 3})
            self.assertEqual(parsed["expressions"], ["(1) ⊼ ((2) ⊼ (3))"])
            self.assertEqual(self.request("/api/evaluate", {"circuit": parsed["circuit"], "bits": [1, 1, 1]})["outputs"], [1])

    def test_layout_is_saved_per_circuit_and_survives_reload(self):
        from primitives.circuit import Circuit
        from primitives.library import Library
        circuit = {"inputs": 2, "gates": [[0, 1]], "outputs": [2]}
        positions = [{"x": 40, "y": 100}, {"x": 40, "y": 240}, {"x": 330, "y": 170}, {"x": 620, "y": 170}]
        self.assertIsNone(self.request("/api/layout/load", {"circuit": circuit})["positions"])
        self.assertEqual(self.request("/api/layout/save", {"circuit": circuit, "positions": positions})["positions"], positions)
        self.assertEqual(self.request("/api/layout/load", {"circuit": circuit})["positions"], positions)
        self.assertEqual(Library(self.tmp.name).load_layout(Circuit.from_dict(circuit)), positions)
        other = {**circuit, "gates": [[0, 0]]}
        self.assertIsNone(self.request("/api/layout/load", {"circuit": other})["positions"])
        for invalid in ([], [{"x": True, "y": 100}] * 4, [{"x": float("nan"), "y": 100}] * 4,
                        [{"x": -1, "y": 100}] * 4):
            with self.assertRaises(HTTPError) as caught:
                self.request("/api/layout/save", {"circuit": circuit, "positions": invalid})
            self.assertEqual(caught.exception.code, 400)
            caught.exception.close()
        with urlopen(self.base + "/graph.js") as response:
            self.assertIn(b"CircuitGraph", response.read())
        with urlopen(self.base + "/viewport.js") as response:
            self.assertEqual(response.headers.get_content_type(), "text/javascript")
            self.assertIn(b"CircuitViewport", response.read())

    def test_manual_wire_layout_restart_legacy_and_validation(self):
        from primitives.circuit import Circuit
        from primitives.library import Library, digest, write_json
        circuit = {"inputs": 1, "gates": [[0, 0]], "outputs": [1]}
        positions = [{"x": 40, "y": 150}, {"x": 330, "y": 150}, {"x": 620, "y": 150}]
        points = [{"x": 236, "y": 150}, {"x": 260, "y": 150}, {"x": 260, "y": 132}, {"x": 330, "y": 132}]
        wires = {"0:1:0": points, "0:1:1": [{"x": p["x"], "y": p["y"] + 36} for p in points]}
        body = {"circuit": circuit, "positions": positions, "wires": wires}
        saved = self.request("/api/layout/save", body)
        self.assertEqual(saved, {"positions": positions, "wires": wires})
        self.assertEqual(self.request("/api/layout/load", {"circuit": circuit}), saved)
        self.assertEqual(Library(self.tmp.name).load_layout_data(Circuit.from_dict(circuit)), saved)
        # Restart the actual HTTP server against the same directory.
        self.server.shutdown()
        self.server.server_close()
        self.server.executor.shutdown()
        self.thread.join(timeout=5)
        self.server = make_server(0, self.tmp.name, background=False)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        self.assertEqual(self.request("/api/layout/load", {"circuit": circuit}), saved)
        for invalid in ([], {"0:1:2": points}, {"1:1:0": points}, {"0:1:0": []},
                        {"0:1:0": points * 33}, {"0:1:0": [{"x": True, "y": 5}, {"x": 1, "y": 5}]},
                        {"0:1:0": [{"x": float("inf"), "y": 5}, {"x": 1, "y": 5}]},
                        {"0:1:0": [{"x": -1, "y": 5}, {"x": 1, "y": 5}]},
                        {"0:1:0": [{"x": 1, "y": 5}, {"x": 2, "y": 6}]}):
            with self.subTest(invalid=invalid):
                with self.assertRaises(HTTPError) as caught:
                    self.request("/api/layout/save", {**body, "wires": invalid})
                self.assertEqual(caught.exception.code, 400)
                caught.exception.close()
                self.assertEqual(self.request("/api/layout/load", {"circuit": circuit}), saved)
        # A positions-only file from schema 1 must remain loadable.
        write_json(Library(self.tmp.name).root / "layouts" / f"{digest(circuit)}.json",
                   {"schema": 1, "positions": positions})
        self.assertEqual(self.request("/api/layout/load", {"circuit": circuit}), {"positions": positions, "wires": {}})
        self.assertEqual(self.request("/api/layout/save", {"circuit": circuit, "positions": positions})["wires"], {})

    def test_cancel_search_and_restart(self):
        from primitives.runner import tiny_interpreter
        backends = ["python"]
        try:
            tiny_interpreter()
            backends.append("tiny")
        except ValueError:
            pass
        dataset = self.request("/api/datasets", {"name": "xor", "inputs": 2, "outputs": 1, "expression": "x0 ^ x1"})
        for backend in backends:
            with self.subTest(backend=backend):
                job = self.request("/api/search", {"dataset_id": dataset["id"], "config": {
                    "backend": backend, "gates": 1, "population": 25, "generations": 20000}})
                path = "/api/jobs/" + job["job_id"]
                deadline = time.monotonic() + 3
                while self.request(path)["status"] == "queued" and time.monotonic() < deadline:
                    time.sleep(0.01)
                # Give TinyLanguage time to start its subprocess before cancellation.
                time.sleep(0.15)
                self.assertEqual(self.request(path + "/cancel", {})["status"], "cancelling")
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline:
                    state = self.request(path)
                    if state["status"] == "cancelled":
                        break
                    time.sleep(0.02)
                self.assertEqual(state["status"], "cancelled", state)
                self.assertNotIn("result", state)
                self.assertEqual(self.request(path + "/cancel", {})["status"], "cancelled")
                self.assertEqual(self.request("/api/catalog")["programs"], [])
        # Cancellation releases the worker for the next search.
        job = self.request("/api/search", {"dataset_id": dataset["id"], "config": {
            "backend": "python", "gates": 1, "population": 2, "generations": 1}})
        path = "/api/jobs/" + job["job_id"]
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            state = self.request(path)
            if state["status"] in ("done", "failed"):
                break
            time.sleep(0.02)
        self.assertEqual(state["status"], "done", state)

    def test_repair_freeze_and_unfreeze_api(self):
        from primitives.library import Library
        from primitives.dataset import preset
        from test_repair import MUL_APPROXIMATION
        library = Library(self.tmp.name)
        old = library.save_program({"circuit": MUL_APPROXIMATION.to_dict(), "search": {"history": []}}, preset("mul"))
        setting = self.request(f'/api/programs/{old["id"]}/frozen', {"frozen": True})
        self.assertTrue(setting["frozen"])
        repaired = self.request("/api/repair", {"program_id": old["id"]})
        self.assertTrue(repaired["fitness"]["verified_truth_table"])
        self.assertTrue(repaired["frozen"])
        self.assertEqual(len(repaired["correction"]["cases"]), 1)
        catalog = self.request("/api/catalog")
        self.assertEqual(len(catalog["programs"]), 1)
        self.assertEqual(catalog["programs"][0]["id"], repaired["id"])
        self.assertIn("background", catalog)
        self.request(f'/api/programs/{old["id"]}/frozen', {"frozen": False})
        self.assertFalse(self.request("/api/catalog")["programs"][0]["frozen"])
        evaluated = self.request("/api/evaluate", {"circuit": repaired["circuit"], "bits": [1, 1, 1, 1]})
        self.assertEqual(evaluated["outputs"], [1, 0, 0, 1])
        for path, obj in ((f'/api/programs/{old["id"]}/frozen', {"frozen": 1}),
                          ("/api/repair", {"program_id": repaired["id"]})):
            with self.assertRaises(HTTPError) as caught:
                self.request(path, obj)
            self.assertEqual(caught.exception.code, 400)
            caught.exception.close()


if __name__ == "__main__":
    unittest.main()

