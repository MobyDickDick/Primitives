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
    @classmethod
    def setUpClass(cls):
        (ROOT / ".jobs").mkdir(exist_ok=True)
        cls.tmp = tempfile.TemporaryDirectory(dir=ROOT / ".jobs")
        cls.server = make_server(0, cls.tmp.name)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.server.executor.shutdown()
        cls.tmp.cleanup()

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

    def test_contradiction_and_origin_rejected(self):
        for obj, headers in (({"name": "bad", "inputs": 1, "outputs": 1, "rows": [[0, 0], [0, 1]]}, {}),
                             ({}, {"Origin": "https://foreign.invalid"})):
            with self.assertRaises(HTTPError) as caught:
                self.request("/api/datasets", obj, headers)
            self.assertEqual(caught.exception.code, 400)
            caught.exception.close()


if __name__ == "__main__":
    unittest.main()

