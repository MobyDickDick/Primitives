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
from .evolution import Problem, search_python
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


def search(dataset, config, library=None, *, save=True, time_budget=None):
    config.validate()
    saved = library.programs() if library else []
    circuits = [Circuit.from_dict(p["circuit"]) for p in saved if p["fitness"]["exact_on_dataset"]]
    incumbent = next((p for p in saved if p["task_id"] == task_id(dataset)), None)
    started = time.monotonic()
    if config.backend == "python":
        result = search_python(Problem(dataset, config, circuits,
                                      Circuit.from_dict(incumbent["circuit"]) if incumbent else None,
                                      time_budget=time_budget))
    else:
        interpreter = tiny_interpreter()
        (ROOT / ".jobs").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / ".jobs") as temp:
            folder = Path(temp)
            job = folder / "job.json"
            job.write_text(json.dumps({"dataset": dataset.to_dict(), "config": asdict(config),
                                       "library": [c.to_dict() for c in circuits]}), encoding="utf-8")
            # JSON quoting is safe here: this is source text, never a shell command.
            prelude = f'''def bridge = Python.import_module("primitives.tiny_bridge", new["configure", "specimen", "score", "trace", "finish"]);
def configured = bridge.configure({json.dumps(str(job))});
if (configured != 0) {{ print(configured); }}
def n = {dataset.inputs};
def m = {dataset.outputs};
def gates = {config.gates};
def population = {config.population};
def generations = {config.generations};
def seed = {config.seed};
'''
            source = folder / "search.tiny"
            source.write_text(prelude + (ROOT / "tiny" / "evolve.tiny").read_text(encoding="utf-8"), encoding="utf-8")
            env = dict(os.environ, PYTHONPATH=str(ROOT) + os.pathsep + str(interpreter.parent),
                       PYTHONDONTWRITEBYTECODE="1")
            try:
                proc = subprocess.run([sys.executable, str(interpreter), str(source)], cwd=ROOT, env=env,
                                      text=True, encoding="utf-8", errors="replace", capture_output=True, timeout=300)
            except subprocess.TimeoutExpired as exc:
                raise ValueError("TinyLanguage-Suche nach 300 Sekunden abgebrochen; Budget verkleinern oder Python-Backend wählen.") from exc
            if proc.returncode:
                raise ValueError("TinyLanguage meldet: " + (proc.stderr or proc.stdout)[-5000:])
            try:
                result = json.loads(proc.stdout.strip().splitlines()[-1])
            except (ValueError, IndexError) as exc:
                raise ValueError("TinyLanguage lieferte kein gültiges Suchergebnis: " + proc.stdout[-1000:]) from exc
    result["search"]["elapsed_seconds"] = round(time.monotonic() - started, 3)
    result["search"]["seed_library"] = [p["id"] for p in saved if p["fitness"]["exact_on_dataset"]]
    if config.repair_cases:
        result["fitness"] = fitness(Circuit.from_dict(result["circuit"]), dataset)
        if incumbent and rank(incumbent) < rank(result):
            result = {"circuit": incumbent["circuit"], "fitness": incumbent["fitness"],
                      "search": result["search"],
                      **({"correction": incumbent["correction"]} if "correction" in incumbent else {})}
        result = repair_result(result, dataset, config.repair_cases)
    if library and save:
        result = library.save_program(result, dataset)
    return result

