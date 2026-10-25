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
from .operations import OPERATIONS, generate_operation, operation_variant
from .formula import parse_formula, python_expressions, to_formula
from .evolution import SearchCancelled, SearchConfig, check_cancelled
from .library import Library
from .runner import ROOT, search, tiny_interpreter
from .background import BackgroundOptimizer
from .repair import repair_result


def make_server(port=8765, data_dir=None, *, background=True):
    library = Library(data_dir or ROOT / "data")
    jobs, cancellations, lock = {}, {}, threading.Lock()
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="evolution")
    optimizer = BackgroundOptimizer(library, enabled=background)

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
                                    "operations": OPERATIONS,
                                    "datasets": library.datasets(), "programs": library.programs(), "tiny_available": tiny,
                                    "background": optimizer.status()})
                elif path.startswith("/api/datasets/"):
                    self.send_data(library.load_dataset(path.rsplit("/", 1)[1]).to_dict())
                elif path.startswith("/api/programs/"):
                    self.send_data(library.load_program(path.rsplit("/", 1)[1]))
                elif path.startswith("/api/jobs/"):
                    with lock:
                        job = dict(jobs[path.rsplit("/", 1)[1]])
                    job["elapsed_seconds"] = round(time.monotonic() - job.pop("started"), 1)
                    self.send_data(job)
                elif path in ("/", "/app.js", "/graph.js", "/viewport.js", "/style.css"):
                    name = "index.html" if path == "/" else path[1:]
                    content_type = {"index.html": "text/html; charset=utf-8", "app.js": "text/javascript; charset=utf-8", "graph.js": "text/javascript; charset=utf-8", "viewport.js": "text/javascript; charset=utf-8", "style.css": "text/css; charset=utf-8"}[name]
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
                    if "rows" in obj:
                        dataset = Dataset.from_dict(obj)
                    elif "operation" in obj:
                        dataset = generate_operation(obj["operation"], obj.get("samples"), obj.get("seed", 1), obj.get("name"))
                    else:
                        dataset = generate(obj["name"], obj["inputs"], obj["outputs"], obj.get("expression"),
                                           obj.get("samples"), obj.get("seed", 1), ports=obj.get("interface"),
                                           reference_circuit=obj.get("reference_circuit"), formula=obj.get("formula"))
                    key = library.save_dataset(dataset)
                    self.send_data({"id": key, "dataset": dataset.to_dict()})
                elif path == "/api/operations/variant":
                    operation, ports, expressions = operation_variant(obj)
                    self.send_data({"operation": operation, "interface": ports, "expression": expressions})
                elif path == "/api/formulas/parse":
                    self.send_data({"expression": parse_formula(obj["formula"], obj.get("result_name", "c"))})
                elif path == "/api/formulas/convert":
                    self.send_data({"formula": to_formula(obj["expression"])})
                elif path == "/api/formulas/expressions":
                    self.send_data({"expression": python_expressions(obj["formula"], obj.get("result_name", "c"))})
                elif path == "/api/parse":
                    circuit = parse_expression(obj["expression"], obj["inputs"])
                    self.send_data({"circuit": circuit.to_dict(), "expressions": circuit.expressions()})
                elif path in ("/api/layout/load", "/api/layout/save"):
                    circuit = Circuit.from_dict(obj["circuit"])
                    if path.endswith("/save"):
                        library.save_layout(circuit, obj["positions"], obj.get("wires", {}))
                    self.send_data(library.load_layout_data(circuit))
                elif path == "/api/evaluate":
                    circuit = Circuit.from_dict(obj["circuit"])
                    values = circuit.wires(obj["bits"])
                    self.send_data({"wires": values, "outputs": [values[o] for o in circuit.outputs]})
                elif path.startswith("/api/jobs/") and path.endswith("/cancel"):
                    key = path.split("/")[-2]
                    with lock:
                        job = jobs[key]
                        if job["status"] in ("queued", "running", "cancelling"):
                            cancellations[key].set()
                            job["status"] = "cancelling"
                        status = job["status"]
                    self.send_data({"status": status})
                elif path.startswith("/api/programs/") and path.endswith("/frozen"):
                    setting = library.set_frozen(path.split("/")[-2], obj["frozen"])
                    if setting["frozen"]:
                        optimizer.cancel_task(setting["task_id"])
                    self.send_data(setting)
                elif path == "/api/repair":
                    old = library.load_program(obj["program_id"])
                    dataset = library.load_dataset(old["dataset_id"])
                    corrected = repair_result(old, dataset)
                    if corrected is old:
                        raise ValueError("Keine Restfallkorrektur möglich: erforderlich sind 1–4 fehlerhafte Eingaben, höchstens ein Viertel der Testfälle und maximal 512 Gatter.")
                    corrected.pop("comparison", None)
                    self.send_data(library.save_program(corrected, dataset))
                elif path == "/api/search":
                    dataset = library.load_dataset(obj["dataset_id"]) if "dataset_id" in obj else Dataset.from_dict(obj["dataset"])
                    config = SearchConfig(**obj.get("config", {}))
                    config.validate()
                    if config.backend == "tiny":
                        tiny_interpreter()
                    with lock:
                        if any(j["status"] in ("queued", "running", "cancelling") for j in jobs.values()):
                            raise ValueError("Eine Suche läuft bereits. Bitte deren Ergebnis abwarten.")
                        key = uuid.uuid4().hex
                        jobs[key] = {"status": "queued", "started": time.monotonic()}
                        cancellations[key] = threading.Event()
                        optimizer.pause()

                    def work():
                        try:
                            with lock:
                                check_cancelled(cancellations[key])
                                jobs[key]["status"] = "running"
                            result = search(dataset, config, library, save=False, cancel_event=cancellations[key])
                            with lock:
                                check_cancelled(cancellations[key])
                                result = library.save_program(result, dataset)
                                jobs[key].update(status="done", result=result)
                        except SearchCancelled:
                            with lock:
                                jobs[key].update(status="cancelled")
                        except Exception as exc:
                            with lock:
                                jobs[key].update(status="failed", error=str(exc))
                        finally:
                            with lock:
                                if not any(j["status"] in ("queued", "running", "cancelling") for j in jobs.values()):
                                    optimizer.resume()
                    executor.submit(work)
                    self.send_data({"job_id": key}, 202)
                else:
                    self.send_data({"error": "Nicht gefunden."}, 404)
            except (ValueError, TypeError, KeyError, FileNotFoundError, RecursionError) as exc:
                self.send_data({"error": str(exc)}, 400)

    class LocalServer(ThreadingHTTPServer):
        def serve_forever(self, poll_interval=0.5):
            optimizer.start()
            try:
                super().serve_forever(poll_interval)
            finally:
                optimizer.close()

        def shutdown(self):
            optimizer.close()
            super().shutdown()

        def server_close(self):
            with lock:
                for event in cancellations.values():
                    event.set()
            optimizer.close()
            super().server_close()

    server = LocalServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    server.executor = executor
    server.optimizer = optimizer
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

