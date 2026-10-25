import json
import tempfile
import threading
import time
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from primitives.server import make_server
from primitives.runner import ROOT
from primitives.blocks import BlockBundle
from primitives.circuit import Circuit


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
        self.assertGreater(state["result"]["comparison"]["candidate_fitness"]["errors"], 0)
        self.assertEqual([p["id"] for p in self.request("/api/catalog")["programs"]], [saved["id"]])

    def test_contradiction_and_origin_rejected(self):
        for obj, headers in (({"name": "bad", "inputs": 1, "outputs": 1, "rows": [[0, 0], [0, 1]]}, {}),
                             ({}, {"Origin": "https://foreign.invalid"})):
            with self.assertRaises(HTTPError) as caught:
                self.request("/api/datasets", obj, headers)
            self.assertEqual(caught.exception.code, 400)
            caught.exception.close()

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

