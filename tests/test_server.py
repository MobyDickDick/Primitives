import json
import tempfile
import threading
import time
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from primitives.server import make_server
from primitives.runner import ROOT


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

