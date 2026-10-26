"""Explicit FFI allowlist for the TinyLanguage search; one process per job."""
from pathlib import Path
import json
from .dataset import Dataset
from .circuit import Circuit
from .evolution import Problem, SearchConfig, island_sizes

_problem = None


def configure(path):
    global _problem
    obj = json.loads(Path(path).read_text(encoding="utf-8"))
    _problem = Problem(Dataset.from_dict(obj["dataset"]), SearchConfig(**obj["config"]),
                       [Circuit.from_dict(c) for c in obj["library"]],
                       Circuit.from_dict(obj["incumbent"]) if obj.get("incumbent") else None,
                       library_sources=obj.get("library_sources"), incumbent_source=obj.get("incumbent_source"))
    return 0


def specimen():
    return _problem.specimen()


def population_buffer(size):
    # Host-backed lists cross the FFI as values; Tiny heap pointers do not.
    return [0] * (int(size) * _problem.width)


def begin_restart(index):
    _problem.start_restart(int(index))
    return 0


def initial(restart, position):
    return _problem.initial_genome() if restart == 0 and position == 0 else _problem.specimen()


def observe(parents, size, width, generation, stage, migrations):
    size, width = int(size), int(width)
    genomes = [list(parents[i * width:(i + 1) * width]) for i in range(size)]
    populations, offset = [], 0
    for capacity in island_sizes(_problem.config.population, _problem.config.islands):
        populations.append(genomes[offset:offset + capacity])
        offset += capacity
    return _problem.observe(populations, int(generation), stage, int(migrations))


def score(genome):
    return _problem.score(genome)


def trace(generation, value):
    return _problem.trace(generation, value)


def record(genome, generation, island, parent_id, mate_id, parents, offset, flags):
    offset = int(offset)
    return _problem.record(list(genome), int(generation), int(island), int(parent_id), int(mate_id),
                           list(parents[offset:offset + _problem.width]) if parent_id else None,
                           [int(flag) for flag in flags] if parent_id else None)


def migration(candidate_id, source, target, generation):
    _problem.ancestry.migrations.append({"restart": _problem.current_restart, "generation": int(generation),
        "source_island": int(source), "target_island": int(target), "candidate_id": int(candidate_id)})
    return 0


def finish(genome, generation, width, parent_population=0, candidate_id=None):
    if len(genome) != width:
        raise ValueError("Ungültige Genomlänge.")
    return json.dumps(_problem.result(genome, generation, parent_population, candidate_id))

