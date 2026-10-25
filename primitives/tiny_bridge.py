"""Explicit FFI allowlist for the TinyLanguage search; one process per job."""
from pathlib import Path
import json
from .dataset import Dataset
from .circuit import Circuit
from .evolution import Problem, SearchConfig

_problem = None


def configure(path):
    global _problem
    obj = json.loads(Path(path).read_text(encoding="utf-8"))
    _problem = Problem(Dataset.from_dict(obj["dataset"]), SearchConfig(**obj["config"]),
                       [Circuit.from_dict(c) for c in obj["library"]])
    return 0


def specimen():
    return _problem.specimen()


def score(genome):
    return _problem.score(genome)


def trace(generation, value):
    return _problem.trace(generation, value)


def finish(genome, generation, width):
    if len(genome) != width:
        raise ValueError("Ungültige Genomlänge.")
    return json.dumps(_problem.result(genome, generation))

