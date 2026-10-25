"""Search orchestration and TinyLanguage subprocess isolation."""
from dataclasses import asdict
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from .circuit import Circuit
from .evolution import Problem, check_cancelled, search_python
from .library import fitness, rank, task_id
from .repair import repair_result

ROOT = Path(__file__).resolve().parent.parent


def tiny_interpreter():
    configured = os.environ.get("TINYLANGUAGE_HOME")
    home = Path(configured).expanduser() if configured else ROOT / ".runtime" / "tinylanguage"
    path = home / "src" / "tiny_language.py"
    if not path.is_file():
        raise ValueError("TinyLanguage fehlt. Zuerst python tools/setup_tiny.py --source ../TinyLanguage ausführen oder --backend python wählen.")
    return path


def search(dataset, config, library=None, *, save=True, time_budget=None, cancel_event=None):
    config.validate()
    check_cancelled(cancel_event)
    saved = library.programs() if library else []
    circuits = [Circuit.from_dict(p["circuit"]) for p in saved if p["fitness"]["exact_on_dataset"]]
    blocks = library.blocks() if library else []
    circuits += [library.load_block(b["id"]).expand() for b in blocks]
    incumbent = next((p for p in saved if p["task_id"] == task_id(dataset)), None)
    started = time.monotonic()
    if config.backend == "python":
        result = search_python(Problem(dataset, config, circuits,
                                      Circuit.from_dict(incumbent["circuit"]) if incumbent else None,
                                      time_budget=time_budget, cancel_event=cancel_event))
    else:
        interpreter = tiny_interpreter()
        (ROOT / ".jobs").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / ".jobs") as temp:
            folder = Path(temp)
            job = folder / "job.json"
            job.write_text(json.dumps({"dataset": dataset.to_dict(), "config": asdict(config),
                                       "library": [c.to_dict() for c in circuits],
                                       "incumbent": incumbent["circuit"] if incumbent else None}), encoding="utf-8")
            # JSON quoting is safe here: this is source text, never a shell command.
            prelude = f'''def bridge = Python.import_module("primitives.tiny_bridge", new["configure", "specimen", "score", "trace", "finish", "begin_restart", "initial", "observe", "population_buffer"]);
def configured = bridge.configure({json.dumps(str(job))});
if (configured != 0) {{ print(configured); }}
def n = {dataset.inputs};
def m = {dataset.outputs};
def gates = {config.gates};
def population = {config.population};
def generations = {config.generations};
def seed = {config.seed};
def evaluation_budget = {config.evaluation_budget};
def restarts = {config.restarts};
def islands = {config.islands};
def migration_interval = {config.migration_interval};
'''
            source = folder / "search.tiny"
            source.write_text(prelude + (ROOT / "tiny" / "evolve.tiny").read_text(encoding="utf-8"), encoding="utf-8")
            env = dict(os.environ, PYTHONPATH=str(ROOT) + os.pathsep + str(interpreter.parent),
                       PYTHONDONTWRITEBYTECODE="1")
            flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            with subprocess.Popen([sys.executable, str(interpreter), str(source)], cwd=ROOT, env=env,
                                  text=True, encoding="utf-8", errors="replace", stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, creationflags=flags) as proc:
                deadline = time.monotonic() + 300
                try:
                    while True:
                        check_cancelled(cancel_event)
                        if time.monotonic() >= deadline:
                            raise ValueError("TinyLanguage-Suche nach 300 Sekunden abgebrochen; Budget verkleinern oder Python-Backend wählen.")
                        try:
                            stdout, stderr = proc.communicate(timeout=0.1)
                            break
                        except subprocess.TimeoutExpired:
                            pass
                finally:
                    if proc.poll() is None:
                        proc.kill()
                        proc.communicate()
            if proc.returncode:
                raise ValueError("TinyLanguage meldet: " + (stderr or stdout)[-5000:])
            try:
                result = json.loads(stdout.strip().splitlines()[-1])
            except (ValueError, IndexError) as exc:
                raise ValueError("TinyLanguage lieferte kein gültiges Suchergebnis: " + stdout[-1000:]) from exc
    check_cancelled(cancel_event)
    result["search"]["elapsed_seconds"] = round(time.monotonic() - started, 3)
    result["search"]["seed_library"] = [p["id"] for p in saved if p["fitness"]["exact_on_dataset"]]
    # Available expanded seeds, not a claim of preserved instances or ancestry.
    result["search"]["seed_blocks"] = [b["id"] for b in blocks]
    if config.repair_cases:
        result["fitness"] = fitness(Circuit.from_dict(result["circuit"]), dataset)
        if incumbent and rank(incumbent) < rank(result):
            result = {"circuit": incumbent["circuit"], "fitness": incumbent["fitness"],
                      "search": result["search"],
                      **({"correction": incumbent["correction"]} if "correction" in incumbent else {})}
        result = repair_result(result, dataset, config.repair_cases, cancel_event=cancel_event)
    check_cancelled(cancel_event)
    if library and save:
        check_cancelled(cancel_event)
        result = library.save_program(result, dataset)
    return result

