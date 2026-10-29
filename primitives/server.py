"""Local-only HTTP application, using only the Python standard library."""
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import re
from pathlib import Path
import threading
import time
from urllib.parse import urlsplit
import uuid
from .circuit import Circuit, parse_expression
from .dataset import Dataset, PRESETS, generate, validate_description
from .operations import OPERATIONS, generate_operation, operation_variant
from .formula import parse_formula, python_expressions, to_formula
from .evolution import SearchCancelled, SearchConfig, check_cancelled
from .library import Library, function_id, fitness
from .runner import ROOT, search, tiny_interpreter
from .background import BackgroundOptimizer
from .repair import repair_result
from .blocks import BlockBundle
from .program import Program, ProgramCancelled
from .templates import Template
from .synthesis import synthesize


def debug_document(snapshot):
    """Encode large debug integers as decimal strings for exact browser display."""
    if type(snapshot) is int and abs(snapshot) > 2**53 - 1:
        return str(snapshot)
    if isinstance(snapshot, dict):
        return {key: debug_document(value) for key, value in snapshot.items()}
    if isinstance(snapshot, list):
        return [debug_document(value) for value in snapshot]
    return snapshot


def make_server(port=8765, data_dir=None, *, background=True, seed_examples=True):
    library = Library(data_dir or ROOT / "data")
    if seed_examples:
        from .examples import (install_examples, install_structured_examples, install_standard_arithmetic_examples,
                               install_arithmetic_comments, install_zero_count_examples, install_priority_encoder_examples)
        install_examples(library)
        install_structured_examples(library)
        install_standard_arithmetic_examples(library)
        install_zero_count_examples(library)
        install_priority_encoder_examples(library)
        install_arithmetic_comments(library)
    jobs, cancellations, lock = {}, {}, threading.Lock()
    debuggers = {}
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
                                    "operations": OPERATIONS, "blocks": library.blocks(), "templates": library.templates(),
                                    "datasets": library.datasets(), "programs": library.programs(), "tree": library.tree(), "tiny_available": tiny,
                                    "background": optimizer.status()})
                elif path.startswith("/api/datasets/"):
                    self.send_data(library.dataset_document(library.load_dataset(path.rsplit("/", 1)[1])))
                elif path.startswith("/api/blocks/"):
                    self.send_data(library.load_block(path.rsplit("/", 1)[1]).to_dict())
                elif path.startswith("/api/templates/"):
                    self.send_data(library.load_template(path.rsplit("/", 1)[1]).to_dict())
                elif path.startswith("/api/programs/"):
                    self.send_data(library.load_program(path.rsplit("/", 1)[1]))
                elif path.startswith("/api/jobs/"):
                    with lock:
                        job = dict(jobs[path.rsplit("/", 1)[1]])
                    job["elapsed_seconds"] = round(time.monotonic() - job.pop("started"), 1)
                    self.send_data(job)
                elif path in ("/", "/app.js", "/graph.js", "/viewport.js", "/playback.js", "/block-debug.js", "/style.css"):
                    name = "index.html" if path == "/" else path[1:]
                    content_type = "text/html; charset=utf-8" if name == "index.html" else "text/css; charset=utf-8" if name == "style.css" else "text/javascript; charset=utf-8"
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
                # A 65536-row dataset can now contain 128 input + 128 output bits.
                if not 0 < length <= 64_000_000:
                    raise ValueError("Anfrage zu gross oder leer.")
                obj = json.loads(self.rfile.read(length))
                if not isinstance(obj, dict):
                    raise ValueError("Ein JSON-Objekt wird erwartet.")
                path = urlsplit(self.path).path
                if "program" in obj and any(k in obj for k in ("rows", "expression", "formula", "operation", "reference_circuit", "block")):
                    raise ValueError("Programmreferenz nicht mit anderen Referenzen oder rows kombinieren.")
                if path == "/api/library/folders":
                    self.send_data(library.save_folder(obj.get("name"), obj.get("description", ""), obj.get("parent"), obj.get("id")))
                elif path == "/api/library/folders/delete":
                    self.send_data(library.delete_folder(obj.get("id")))
                elif path == "/api/library/move":
                    self.send_data(library.move_entry(obj.get("kind"), obj.get("id"), obj.get("folder")))
                elif path == "/api/templates/synthesize":
                    program = (library.load_template(obj["template_id"]).instantiate(obj.get("parameters"))
                               if "template_id" in obj else Program(obj["program"], obj.get("interface")))
                    circuit = synthesize(program)
                    dataset = generate(obj.get("name", "NAND-Template"), circuit.inputs, len(circuit.outputs),
                                       ports=program.ports, program=program.spec, samples=obj.get("samples", 256),
                                       seed=obj.get("seed", 1))
                    dataset.metadata["description"] = validate_description(obj.get("description", ""))
                    result = {"circuit": circuit.to_dict(), "synthesis": {"method": "structural-bitwise", "version": 1}}
                    if fitness(circuit, dataset)["errors"]:
                        raise ValueError("NAND-Synthese stimmt nicht mit den Referenzvektoren überein.")
                    with lock:
                        saved = library.save_program(result, dataset)
                        dataset_id = library.save_dataset(dataset)
                        library.update_function(function_id(dataset), dataset.name, dataset.metadata["description"])
                        saved = {**saved, **library.load_program(saved["id"])}
                    self.send_data({"id": dataset_id, "dataset": library.dataset_document(dataset), "result": saved})
                elif path == "/api/templates":
                    template = Template(obj)
                    key = library.save_template(template)
                    self.send_data({"id": key, "template": template.to_dict()})
                elif path == "/api/templates/specialize":
                    program = (library.load_template(obj["template_id"]).instantiate(obj.get("parameters"))
                               if "template_id" in obj else Program(obj["program"], obj.get("interface")))
                    self.send_data({"program": program.spec, "interface": program.ports,
                                    "inputs": sum(p["bits"] for p in program.ports["inputs"]),
                                    "outputs": sum(p["bits"] for p in program.ports["outputs"])})
                elif path == "/api/circuits/check":
                    circuit = Circuit.from_dict(obj["circuit"])
                    result = {"circuit": circuit.to_dict(), "manual_edit": True}
                    try:
                        result["expressions"] = circuit.expressions()
                    except ValueError:
                        result["expressions"] = None
                    if obj.get("dataset_id"):
                        dataset = library.load_dataset(obj["dataset_id"])
                        result.update(dataset_id=obj["dataset_id"], dataset_name=dataset.name,
                                      dataset_metadata=dataset.metadata, fitness=fitness(circuit, dataset))
                    self.send_data(result)
                elif path == "/api/source-debug/start":
                    x = obj["x"]
                    if isinstance(x, str):
                        if not re.fullmatch(r"[0-9]{1,39}", x):
                            raise ValueError("Testeingabe x muss eine ganze unsigned Dezimalzahl bis 128 Bits sein.")
                        x = int(x)
                    execution = Program(obj["program"], obj["interface"]).debug(x)
                    with lock:
                        # Sessions are ephemeral; cap abandoned browser sessions.
                        if len(debuggers) >= 32:
                            debuggers.pop(next(iter(debuggers)))
                        key = uuid.uuid4().hex
                        debuggers[key] = execution
                    self.send_data(debug_document({"id": key, **execution.snapshot()}))
                elif path.startswith("/api/source-debug/") and len(path.split("/")) == 5:
                    _, _, _, key, action = path.split("/")
                    with lock:
                        execution = debuggers[key]
                        if action == "close":
                            del debuggers[key]
                            result = {"status": "closed"}
                        elif action == "reset":
                            result = execution.reset()
                        elif action == "stop":
                            result = execution.stop()
                        elif action in ("step", "continue"):
                            result = execution.step(1 if action == "step" else 100)
                        else:
                            raise ValueError("Unbekannte Debugaktion.")
                    self.send_data(debug_document({"id": key, **result}))
                elif path == "/api/datasets":
                    description = validate_description(obj["description"]) if "description" in obj else None
                    if "rows" in obj:
                        dataset = Dataset.from_dict(obj)
                    elif "operation" in obj:
                        dataset = generate_operation(obj["operation"], obj.get("samples"), obj.get("seed", 1), obj.get("name"))
                    elif "block" in obj:
                        dataset = BlockBundle(obj["block"]).dataset(obj.get("samples"), obj.get("seed", 1))
                    else:
                        dataset = generate(obj["name"], obj["inputs"], obj["outputs"], obj.get("expression"),
                                           obj.get("samples"), obj.get("seed", 1), ports=obj.get("interface"),
                                           reference_circuit=obj.get("reference_circuit"), formula=obj.get("formula"), program=obj.get("program"))
                    if description is not None:
                        dataset.metadata = {**dataset.metadata, "description": description}
                    key = library.save_dataset(dataset)
                    if description is not None:
                        library.update_function(function_id(dataset), dataset.name, description)
                    self.send_data({"id": key, "dataset": library.dataset_document(dataset)})
                elif path.startswith("/api/functions/") and path.endswith("/details") and len(path.split("/")) == 5:
                    self.send_data(library.update_function(path.split("/")[-2], obj.get("name"), obj.get("description", "")))
                elif path.startswith("/api/functions/") and path.endswith("/delete") and len(path.split("/")) == 5:
                    with lock:
                        if any(j["status"] in ("queued", "running", "cancelling") for j in jobs.values()):
                            raise ValueError("Zum Löschen zuerst den laufenden Auftrag abwarten oder abbrechen.")
                        optimizer.pause()
                        try:
                            deleted = library.delete_function(path.split("/")[-2])
                        finally:
                            optimizer.resume()
                    self.send_data(deleted)
                elif path == "/api/datasets/generate":
                    description = validate_description(obj["description"]) if "description" in obj else None
                    if "program" not in obj:
                        raise ValueError("Dieser Auftrag benötigt eine Programmreferenz.")
                    with lock:
                        if any(j["status"] in ("queued", "running", "cancelling") for j in jobs.values()):
                            raise ValueError("Ein Auftrag läuft bereits. Bitte abwarten oder abbrechen.")
                        key = uuid.uuid4().hex
                        jobs[key] = {"kind": "dataset", "status": "queued", "started": time.monotonic()}
                        cancellations[key] = threading.Event()
                        optimizer.pause()

                    def generate_vectors():
                        try:
                            with lock:
                                if cancellations[key].is_set(): raise ProgramCancelled()
                                jobs[key]["status"] = "running"
                            dataset = generate(obj["name"], obj["inputs"], obj["outputs"],
                                               samples=obj.get("samples"), seed=obj.get("seed", 1),
                                               ports=obj.get("interface"), program=obj["program"],
                                               cancel_event=cancellations[key])
                            if description is not None:
                                dataset.metadata = {**dataset.metadata, "description": description}
                            with lock:
                                if cancellations[key].is_set(): raise ProgramCancelled()
                                dataset_id = library.save_dataset(dataset)
                                if description is not None:
                                    library.update_function(function_id(dataset), dataset.name, description)
                                jobs[key].update(status="done", result={"id": dataset_id, "dataset": library.dataset_document(dataset)})
                        except ProgramCancelled:
                            with lock:
                                jobs[key].update(status="cancelled")
                        except Exception as exc:
                            with lock:
                                jobs[key].update(status="failed", error=str(exc))
                        finally:
                            with lock:
                                if not any(j["status"] in ("queued", "running", "cancelling") for j in jobs.values()):
                                    optimizer.resume()
                    executor.submit(generate_vectors)
                    self.send_data({"job_id": key}, 202)
                elif path == "/api/blocks":
                    if "program_id" in obj:
                        bundle = library.block_from_program(obj["program_id"], obj.get("name"), obj.get("interface"), obj.get("version", 1))
                    elif "definition" in obj:
                        deps = [library.load_block(key) for key in obj.get("dependencies", [])]
                        bundle = BlockBundle.create(obj["definition"], deps)
                    else:
                        bundle = BlockBundle(obj)
                    summary = library.save_block(bundle)
                    self.send_data({"block": bundle.to_dict(), "summary": summary})
                elif path in ("/api/blocks/view", "/api/blocks/layout/load", "/api/blocks/layout/save"):
                    bundle = library.load_block(obj["block_id"]) if "block_id" in obj else BlockBundle(obj["block"])
                    instance_path = obj.get("path", [])
                    view = bundle.view(instance_path)
                    if path.endswith("view"):
                        self.send_data(view)
                    else:
                        circuit = Circuit.from_dict(view["circuit"])
                        identity = {"block": bundle.root, "path": instance_path}
                        if path.endswith("/save"):
                            library.save_layout(circuit, obj["positions"], obj.get("wires", {}),
                                                identity=identity, nodes=view["circuit"].get("view_nodes"))
                        self.send_data(library.load_layout_data(circuit, identity=identity))
                elif path in ("/api/blocks/evaluate", "/api/blocks/expand"):
                    bundle = library.load_block(obj["block_id"]) if "block_id" in obj else BlockBundle(obj["block"])
                    if path.endswith("evaluate"):
                        self.send_data({"outputs": bundle.evaluate(obj["bits"])})
                    else:
                        self.send_data({"circuit": bundle.expand().to_dict(), "hierarchy": bundle.to_dict()})
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
                    with lock:
                        old = library.load_program(obj["program_id"])
                        dataset = library.load_dataset(old["dataset_id"])
                        corrected = repair_result(old, dataset)
                        if corrected is old:
                            raise ValueError("Keine Restfallkorrektur möglich: erforderlich sind 1–4 fehlerhafte Eingaben, höchstens ein Viertel der Testfälle und maximal 512 Gatter.")
                        corrected.pop("comparison", None)
                        saved = library.save_program(corrected, dataset)
                    self.send_data(saved)
                elif path == "/api/search":
                    config = SearchConfig(**obj.get("config", {}))
                    config.validate()
                    if config.backend == "tiny":
                        tiny_interpreter()
                    with lock:
                        if any(j["status"] in ("queued", "running", "cancelling") for j in jobs.values()):
                            raise ValueError("Ein Auftrag läuft bereits. Bitte abwarten oder abbrechen.")
                        dataset = library.load_dataset(obj["dataset_id"]) if "dataset_id" in obj else Dataset.from_dict(obj["dataset"])
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

