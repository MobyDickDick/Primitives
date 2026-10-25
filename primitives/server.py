"""Local-only HTTP application, using only the Python standard library."""
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import time
from urllib.parse import urlsplit
import uuid
from .circuit import Circuit, parse_expression
from .dataset import Dataset, PRESETS, generate
from .evolution import SearchConfig
from .library import Library
from .runner import ROOT, search, tiny_interpreter


def make_server(port=8765, data_dir=None):
    library = Library(data_dir or ROOT / "data")
    jobs, lock = {}, threading.Lock()
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="evolution")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def send_data(self, data, status=200, content_type="application/json; charset=utf-8"):
            raw = json.dumps(data, ensure_ascii=False).encode() if content_type.startswith("application/json") else data
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'; object-src 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            path = urlsplit(self.path).path
            try:
                if path == "/api/catalog":
                    try:
                        tiny_interpreter()
                        tiny = True
                    except ValueError:
                        tiny = False
                    self.send_data({"presets": {k: {"inputs": v[0], "outputs": v[1], "expression": v[2]} for k, v in PRESETS.items()},
                                    "datasets": library.datasets(), "programs": library.programs(), "tiny_available": tiny})
                elif path.startswith("/api/datasets/"):
                    self.send_data(library.load_dataset(path.rsplit("/", 1)[1]).to_dict())
                elif path.startswith("/api/programs/"):
                    self.send_data(library.load_program(path.rsplit("/", 1)[1]))
                elif path.startswith("/api/jobs/"):
                    with lock:
                        job = dict(jobs[path.rsplit("/", 1)[1]])
                    job["elapsed_seconds"] = round(time.monotonic() - job.pop("started"), 1)
                    self.send_data(job)
                elif path in ("/", "/app.js", "/style.css"):
                    name = "index.html" if path == "/" else path[1:]
                    content_type = {"index.html": "text/html; charset=utf-8", "app.js": "text/javascript; charset=utf-8", "style.css": "text/css; charset=utf-8"}[name]
                    self.send_data((ROOT / "web" / name).read_bytes(), content_type=content_type)
                else:
                    self.send_data({"error": "Nicht gefunden."}, 404)
            except (FileNotFoundError, KeyError):
                self.send_data({"error": "Nicht gefunden."}, 404)
            except (ValueError, TypeError) as exc:
                self.send_data({"error": str(exc)}, 400)

        def do_POST(self):
            try:
                # Browser requests must originate at this same loopback app.
                origin = self.headers.get("Origin")
                expected = f"http://{self.headers.get('Host')}"
                if origin and origin != expected:
                    raise ValueError("Anfrage von einer fremden Seite abgelehnt.")
                if self.headers.get_content_type() != "application/json":
                    raise ValueError("Content-Type application/json erforderlich.")
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 16_000_000:
                    raise ValueError("Anfrage zu gross oder leer.")
                obj = json.loads(self.rfile.read(length))
                if not isinstance(obj, dict):
                    raise ValueError("Ein JSON-Objekt wird erwartet.")
                path = urlsplit(self.path).path
                if path == "/api/datasets":
                    dataset = Dataset.from_dict(obj) if "rows" in obj else generate(
                        obj["name"], obj["inputs"], obj["outputs"], obj["expression"], obj.get("samples"), obj.get("seed", 1))
                    key = library.save_dataset(dataset)
                    self.send_data({"id": key, "dataset": dataset.to_dict()})
                elif path == "/api/parse":
                    self.send_data({"circuit": parse_expression(obj["expression"], obj["inputs"]).to_dict()})
                elif path == "/api/evaluate":
                    circuit = Circuit.from_dict(obj["circuit"])
                    values = circuit.wires(obj["bits"])
                    self.send_data({"wires": values, "outputs": [values[o] for o in circuit.outputs]})
                elif path == "/api/search":
                    dataset = library.load_dataset(obj["dataset_id"]) if "dataset_id" in obj else Dataset.from_dict(obj["dataset"])
                    config = SearchConfig(**obj.get("config", {}))
                    config.validate()
                    if config.backend == "tiny":
                        tiny_interpreter()
                    with lock:
                        if any(j["status"] in ("queued", "running") for j in jobs.values()):
                            raise ValueError("Eine Suche läuft bereits. Bitte deren Ergebnis abwarten.")
                        key = uuid.uuid4().hex
                        jobs[key] = {"status": "queued", "started": time.monotonic()}

                    def work():
                        with lock:
                            jobs[key]["status"] = "running"
                        try:
                            result = search(dataset, config, library)
                            with lock:
                                jobs[key].update(status="done", result=result)
                        except Exception as exc:
                            with lock:
                                jobs[key].update(status="failed", error=str(exc))
                    executor.submit(work)
                    self.send_data({"job_id": key}, 202)
                else:
                    self.send_data({"error": "Nicht gefunden."}, 404)
            except (ValueError, TypeError, KeyError, FileNotFoundError, RecursionError) as exc:
                self.send_data({"error": str(exc)}, 400)

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    server.executor = executor
    return server


def serve(port=8765, data_dir=None):
    server = make_server(port, data_dir)
    print(f"Primitives läuft auf http://127.0.0.1:{server.server_port} – Beenden mit Ctrl+C", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        server.executor.shutdown(wait=True)

