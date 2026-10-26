"""Bit-parallel fitness, library grafting and the optional Python search backend."""
from dataclasses import dataclass, asdict
from collections import Counter
import random
import time
from .circuit import Circuit
from .ancestry import Ancestry, circuit_source, transformed


class SearchCancelled(Exception):
    """The user stopped the current search."""


def check_cancelled(cancel_event):
    if cancel_event is not None and cancel_event.is_set():
        raise SearchCancelled("Suche abgebrochen.")


@dataclass
class SearchConfig:
    gates: int = 12
    population: int = 24
    generations: int = 200
    seed: int = 1
    backend: str = "tiny"
    repair_cases: int = 0
    optimize: bool = False
    restarts: int = 1
    islands: int = 1
    migration_interval: int = 10
    neutral: bool = False

    @property
    def evaluation_budget(self):
        # Initialization is charged to the same budget as offspring.
        return min(500000, 1 + self.population * self.generations)

    def validate(self):
        for name, lo, hi in (("gates", 1, 128), ("population", 2, 256), ("generations", 1, 20000), ("seed", 0, 2**31-1)):
            value = getattr(self, name)
            if type(value) is not int or not lo <= value <= hi:
                raise ValueError(f"{name} muss zwischen {lo} und {hi} liegen.")
        if self.backend not in ("tiny", "python"):
            raise ValueError("backend muss tiny oder python sein.")
        if self.population * self.generations > 500000:
            raise ValueError("Pro Lauf sind höchstens 500000 Kandidaten erlaubt.")
        if type(self.repair_cases) is not int or not 0 <= self.repair_cases <= 4:
            raise ValueError("repair_cases muss zwischen 0 und 4 liegen.")
        if type(self.optimize) is not bool:
            raise ValueError("optimize muss ein Wahrheitswert sein.")
        if type(self.neutral) is not bool:
            raise ValueError("neutral muss ein Wahrheitswert sein.")
        if self.optimize and self.backend != "python":
            raise ValueError("Strukturoptimierung verwendet das Python-Backend.")
        for name, lo, hi in (("restarts", 1, 32), ("islands", 1, 16), ("migration_interval", 1, 20000)):
            value = getattr(self, name)
            if type(value) is not int or not lo <= value <= hi:
                raise ValueError(f"{name} muss zwischen {lo} und {hi} liegen.")
        if self.population < 2 * self.islands:
            raise ValueError("Jede Insel benötigt mindestens zwei Eltern.")
        if self.evaluation_budget // self.restarts < self.population:
            raise ValueError("Das Kandidatenbudget muss für die Elternpopulation jedes Neustarts reichen.")


def diversity(genomes):
    """Genotypic diversity, including inactive genes; no extra fitness evaluations."""
    size = len(genomes)
    unique = len({tuple(g) for g in genomes})
    pairs = size * (size - 1) // 2
    width = len(genomes[0]) if size else 0
    differences = sum(pairs - sum(count * (count - 1) // 2 for count in Counter(column).values())
                      for column in zip(*genomes))
    return {"size": size, "unique_genomes": unique, "unique_fraction": unique / size if size else 0,
            "mean_hamming": differences / (pairs * width) if pairs and width else 0}


def island_sizes(population, islands):
    return [population // islands + (i < population % islands) for i in range(islands)]


def genome_circuit(genome, n, m):
    gate_genes = len(genome) - m
    return Circuit(n, tuple(tuple(genome[i:i+2]) for i in range(0, gate_genes, 2)), tuple(genome[-m:]))


class Problem:
    def __init__(self, dataset, config, library=(), incumbent=None, time_budget=None, cancel_event=None,
                 *, library_sources=None, incumbent_source=None):
        config.validate()
        self.cancel_event = cancel_event
        check_cancelled(cancel_event)
        self.dataset, self.config = dataset, config
        self.n, self.m, self.g = dataset.inputs, dataset.outputs, config.gates
        self.width = self.g * 2 + self.m
        self.rng = random.Random(config.seed)
        library = list(library)
        sources = library_sources if library_sources is not None else [circuit_source(c) for c in library]
        eligible = [(c.compact(), source) for c, source in zip(library, sources)
                    if c.inputs <= self.n and len(c.compact().gates) <= self.g]
        self.library = [c for c, _ in eligible]
        self.library_sources = [source for _, source in eligible]
        self.ancestry = Ancestry()
        self.pending_origin = {"kind": "random"}
        self.incumbent_source = incumbent_source or (circuit_source(incumbent) if incumbent else None)
        self.mask = (1 << len(dataset.rows)) - 1
        columns = [0] * (self.n + self.m)
        for i, row in enumerate(dataset.rows):
            if i % 256 == 0:
                check_cancelled(cancel_event)
            for j, bit in enumerate(row):
                columns[j] |= bit << i
        self.columns, self.targets = columns[:self.n], columns[self.n:]
        # Any single error outweighs all possible gate and depth costs.
        self.error_weight = (self.g + 1) ** 2
        self.history, self.evaluations = [], 0
        self.best_score = None
        self.runs = []
        self.diversity_history = []
        self.current_restart = 0
        self.incumbent = incumbent
        self.deadline = time.monotonic() + time_budget if time_budget is not None else None

    def initial_genome(self):
        c = self.incumbent.compact() if self.incumbent else None
        if c is None or c.inputs != self.n or len(c.outputs) != self.m or len(c.gates) > self.g:
            return self.specimen()
        self.pending_origin = {"kind": "incumbent", "seeds": [
            {"source": self.ancestry.source(self.incumbent_source)}]}
        genes = [ref for pair in c.gates for ref in pair]
        for i in range(len(c.gates), self.g):
            genes.extend(self.rng.randrange(self.n + i) for _ in range(2))
        return genes + list(c.outputs)

    def expired(self):
        return self.deadline is not None and time.monotonic() >= self.deadline

    def start_restart(self, index):
        check_cancelled(self.cancel_event)
        self.current_restart = index
        if self.config.restarts > 1:
            self.rng = random.Random((self.config.seed + index) % 2**31)
        self.run_start = self.evaluations
        self.run_best_score = None
        return self.config.evaluation_budget * (index + 1) // self.config.restarts

    def observe(self, populations, generation, stage, migrations=0):
        snapshot = {"restart": self.current_restart, "generation": generation, "stage": stage,
                    "evaluations": self.evaluations,
                    **diversity([g for group in populations for g in group]),
                    "islands": [diversity(group) for group in populations]}
        self.diversity_history.append(snapshot)
        if stage == "final":
            self.runs.append({"restart": self.current_restart,
                              "seed": (self.config.seed + self.current_restart) % 2**31,
                              "evaluations": self.evaluations - self.run_start,
                              "best_score": self.run_best_score,
                              "generation": generation, "migrations": migrations,
                              "island_populations": [len(group) for group in populations],
                              "diversity": snapshot})
        return 0

    def bound(self, gene):
        return self.n + (gene // 2 if gene < 2*self.g else self.g)

    def random_genome(self):
        return [self.rng.randrange(self.bound(i)) for i in range(self.width)]

    def specimen(self):
        """Compose expanded seeds on inputs and earlier gate outputs.

        Gate genes may subsequently mutate; no original block instance is claimed.
        """
        self.pending_origin = {"kind": "random"}
        if not self.library:
            return self.random_genome()
        gates, outputs, seeds = [], list(range(self.n)), []
        for _ in range(2):
            options = [i for i, c in enumerate(self.library) if len(gates) + len(c.gates) <= self.g]
            if not options:
                break
            index = self.rng.choice(options)
            c = self.library[index]
            mapping = [self.rng.randrange(self.n + len(gates)) for _ in range(c.inputs)]
            seeds.append({"source": self.ancestry.source(self.library_sources[index]),
                          "inputs": list(mapping), "gate_offset": len(gates)})
            for a, b in c.gates:
                mapping.append(self.n + len(gates))
                gates.append((mapping[a], mapping[b]))
            outputs = [mapping[o] for o in c.outputs]
        result = [r for pair in gates for r in pair]
        for i in range(len(gates), self.g):
            result.extend(self.rng.randrange(self.n + i) for _ in range(2))
        self.pending_origin = {"kind": "library", "seeds": seeds}
        return result + [self.rng.choice(outputs) for _ in range(self.m)]

    def metrics(self, genome):
        circuit = genome_circuit(genome, self.n, self.m)
        values = list(self.columns)
        for a, b in circuit.gates:
            values.append(self.mask ^ (values[a] & values[b]))
        errors = sum((values[o] ^ target).bit_count() for o, target in zip(circuit.outputs, self.targets))
        return errors, len(circuit.active()), circuit.depth

    def score(self, genome):
        check_cancelled(self.cancel_event)
        self.evaluations += 1
        errors, gates, depth = self.metrics(genome)
        score = errors * self.error_weight
        if not self.config.neutral:
            score += gates * (self.g + 1) + depth
        if getattr(self, "run_best_score", None) is None or score < self.run_best_score:
            self.run_best_score = score
        self.last_score = score
        return score

    def record(self, genome, generation, island, parent_id=0, mate_id=0, parent=None, flags=None):
        key = self.ancestry.record(self.evaluations, genome, self.last_score, self.current_restart,
                                   generation, island, self.pending_origin,
                                   parent_id, mate_id, parent, flags)
        self.pending_origin = {"kind": "random"}
        return key

    def trace(self, generation, score):
        # Track best-so-far, independent of neutral drift in the live population.
        if self.best_score is None or score < self.best_score:
            self.best_score = score
            self.history.append({"generation": int(generation), "errors": int(score) // self.error_weight,
                                 "score": int(score), "evaluations": self.evaluations})
        return 0

    def result(self, genome, generation, parent_population=0, candidate_id=None):
        circuit = genome_circuit(genome, self.n, self.m).compact()
        errors, _, _ = self.metrics(genome)
        total = len(self.dataset.rows) * self.m
        phases = []
        if self.config.neutral:
            before = {"errors": errors, "gates": len(circuit.gates), "depth": circuit.depth}
            phases.append({"name": "neutral_evolution", "objective": "errors_only",
                           "evaluations": self.evaluations, "result": before})
            # A separate bounded pass; these identities preserve every input,
            # including inputs absent from a sampled training dataset.
            circuit = circuit.simplify(check=lambda: check_cancelled(self.cancel_event))
            phases.append({"name": "simplification", "method": "nand-identities-v1",
                           "evaluations": 0, "before": before,
                           "result": {"errors": errors, "gates": len(circuit.gates), "depth": circuit.depth},
                           "removed_gates": before["gates"] - len(circuit.gates)})
        result = {"circuit": circuit.to_dict(), "fitness": {"errors": errors, "total_bits": total,
                "accuracy": (total - errors) / total, "exact_on_dataset": errors == 0,
                "verified_truth_table": errors == 0 and self.dataset.exhaustive,
                "gates": len(circuit.gates), "depth": circuit.depth},
                "search": {**asdict(self.config), "generation": int(generation), "evaluations": self.evaluations,
                           "history": self.history, "library_candidates": len(self.library),
                           "selection": "tournament",
                           "objective": "errors_only" if self.config.neutral else "errors_gates_depth",
                           "phases": phases,
                           "tournament_size": min(3, max(island_sizes(self.config.population, self.config.islands))),
                           "parent_population": int(parent_population),
                           "restarts_completed": len(self.runs), "runs": self.runs,
                           "diversity_history": self.diversity_history,
                           "diversity": self.diversity_history[-1] if self.diversity_history else None,
                           "evaluation_budget": self.config.evaluation_budget}}
        if candidate_id is not None:
            result["search"]["ancestry"] = self.ancestry.export(int(candidate_id))
            compact = genome_circuit(genome, self.n, self.m).compact()
            result = transformed(result, "compact", compact)
            if self.config.neutral:
                result = transformed(result, "simplification", circuit, method="nand-identities-v1")
        return result


def tournament(ranks, rng):
    """Select the best of up to three independently drawn population members."""
    contenders = (rng.randrange(len(ranks)) for _ in range(min(3, len(ranks))))
    return min(contenders, key=ranks.__getitem__)


def migrate(populations, ranks, identities=None, ancestry=None, restart=0, generation=0):
    """Simultaneous ring migration of one elite per island, without re-scoring."""
    elites = [(list(group[min(range(len(group)), key=scores.__getitem__)]), min(scores))
              for group, scores in zip(populations, ranks)]
    accepted = 0
    elite_ids = ([ids[min(range(len(scores)), key=scores.__getitem__)]
                  for ids, scores in zip(identities, ranks)] if identities is not None else None)
    for target, (genome, score) in enumerate(elites[-1:] + elites[:-1]):
        worst = max(range(len(ranks[target])), key=ranks[target].__getitem__)
        if score <= ranks[target][worst]:
            populations[target][worst], ranks[target][worst] = genome, score
            if elite_ids is not None:
                source = (target - 1) % len(populations)
                identities[target][worst] = elite_ids[source]
                ancestry.migrations.append({"restart": restart, "generation": generation,
                    "source_island": source, "target_island": target, "candidate_id": elite_ids[source]})
            accepted += 1
    return accepted


def search_python(problem):
    p = problem
    best, score, generation, best_id = None, None, 0, None
    capacities = island_sizes(p.config.population, p.config.islands)
    for restart in range(p.config.restarts):
        if restart and p.expired():
            break
        limit = p.start_restart(restart)
        rng = p.rng
        populations, ranks = [[] for _ in capacities], [[] for _ in capacities]
        identities = [[] for _ in capacities]
        for island, capacity in enumerate(capacities):
            for _ in range(capacity):
                if p.evaluations > p.run_start and (p.expired() or (score < p.error_weight and not p.config.optimize)):
                    break
                candidate = p.initial_genome() if restart == 0 and p.evaluations == 0 else p.specimen()
                rank = p.score(candidate)
                candidate_id = p.record(candidate, generation, island)
                populations[island].append(candidate)
                ranks[island].append(rank)
                identities[island].append(candidate_id)
                if score is None or rank < score:
                    best, score = candidate, rank
                    best_id = candidate_id
        p.trace(generation, score)
        p.observe(populations, generation, "initial")
        rounds, migrations = 0, 0
        while (rounds < p.config.generations and not p.expired() and p.evaluations < limit
               and (p.config.optimize or score >= p.error_weight)):
            rounds += 1
            generation += 1
            for attempt in range(p.config.population):
                if p.expired() or p.evaluations >= limit:
                    break
                island = attempt % p.config.islands
                parents, scores = populations[island], ranks[island]
                parent_id, mate_id, parent, flags = 0, 0, None, None
                if rng.random() < 0.15:
                    candidate = p.specimen()
                else:
                    selected, selected_mate = tournament(scores, rng), tournament(scores, rng)
                    parent, mate = parents[selected], parents[selected_mate]
                    parent_id = identities[island][selected]
                    candidate = list(parent)
                    crossover = rng.random() < 0.35
                    mate_id = identities[island][selected_mate] if crossover else 0
                    flags = [0] * p.width
                    for i in range(p.width):
                        if crossover and rng.random() < 0.5:
                            candidate[i] = mate[i]
                            flags[i] |= 1
                        if rng.random() < 1 / p.width:
                            candidate[i] = rng.randrange(p.bound(i))
                            flags[i] |= 2
                rank = p.score(candidate)
                candidate_id = p.record(candidate, generation, island, parent_id, mate_id, parent, flags)
                worst_rank = max(scores)
                worst = rng.choice([i for i, value in enumerate(scores) if value == worst_rank])
                if rank <= scores[worst]:
                    parents[worst], scores[worst] = candidate, rank
                    identities[island][worst] = candidate_id
                if rank < score:
                    best, score = candidate, rank
                    best_id = candidate_id
                if score < p.error_weight and not p.config.optimize:
                    break
            if (p.config.islands > 1 and rounds % p.config.migration_interval == 0
                    and all(populations) and (p.config.optimize or score >= p.error_weight)):
                migrations += migrate(populations, ranks, identities, p.ancestry, restart, generation)
            p.trace(generation, score)
        p.observe(populations, generation, "final", migrations)
        if score < p.error_weight and not p.config.optimize:
            break
    return p.result(best, generation, sum(map(len, populations)), best_id)

