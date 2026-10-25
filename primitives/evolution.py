"""Bit-parallel fitness, library grafting and the optional Python search backend."""
from dataclasses import dataclass, asdict
import random
import time
from .circuit import Circuit


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
        if self.optimize and self.backend != "python":
            raise ValueError("Strukturoptimierung verwendet das Python-Backend.")


def genome_circuit(genome, n, m):
    gate_genes = len(genome) - m
    return Circuit(n, tuple(tuple(genome[i:i+2]) for i in range(0, gate_genes, 2)), tuple(genome[-m:]))


class Problem:
    def __init__(self, dataset, config, library=(), incumbent=None, time_budget=None, cancel_event=None):
        config.validate()
        self.cancel_event = cancel_event
        check_cancelled(cancel_event)
        self.dataset, self.config = dataset, config
        self.n, self.m, self.g = dataset.inputs, dataset.outputs, config.gates
        self.width = self.g * 2 + self.m
        self.rng = random.Random(config.seed)
        self.library = [c.compact() for c in library if c.inputs <= self.n and len(c.compact().gates) <= self.g]
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
        self.incumbent = incumbent
        self.deadline = time.monotonic() + time_budget if time_budget is not None else None

    def initial_genome(self):
        c = self.incumbent.compact() if self.incumbent else None
        if c is None or c.inputs != self.n or len(c.outputs) != self.m or len(c.gates) > self.g:
            return self.specimen()
        genes = [ref for pair in c.gates for ref in pair]
        for i in range(len(c.gates), self.g):
            genes.extend(self.rng.randrange(self.n + i) for _ in range(2))
        return genes + list(c.outputs)

    def expired(self):
        return self.deadline is not None and time.monotonic() >= self.deadline

    def bound(self, gene):
        return self.n + (gene // 2 if gene < 2*self.g else self.g)

    def random_genome(self):
        return [self.rng.randrange(self.bound(i)) for i in range(self.width)]

    def specimen(self):
        """Compose expanded seeds on inputs and earlier gate outputs.

        Gate genes may subsequently mutate; no original block instance is claimed.
        """
        if not self.library:
            return self.random_genome()
        gates, outputs = [], list(range(self.n))
        for _ in range(2):
            options = [c for c in self.library if len(gates) + len(c.gates) <= self.g]
            if not options:
                break
            c = self.rng.choice(options)
            mapping = [self.rng.randrange(self.n + len(gates)) for _ in range(c.inputs)]
            for a, b in c.gates:
                mapping.append(self.n + len(gates))
                gates.append((mapping[a], mapping[b]))
            outputs = [mapping[o] for o in c.outputs]
        result = [r for pair in gates for r in pair]
        for i in range(len(gates), self.g):
            result.extend(self.rng.randrange(self.n + i) for _ in range(2))
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
        return errors * self.error_weight + gates * (self.g + 1) + depth

    def trace(self, generation, score):
        # Track best-so-far, independent of neutral drift in the live population.
        if self.best_score is None or score < self.best_score or generation == 0:
            self.best_score = score
            self.history.append({"generation": int(generation), "errors": int(score) // self.error_weight,
                                 "score": int(score), "evaluations": self.evaluations})
        return 0

    def result(self, genome, generation, parent_population=0):
        circuit = genome_circuit(genome, self.n, self.m).compact()
        errors, _, _ = self.metrics(genome)
        total = len(self.dataset.rows) * self.m
        return {"circuit": circuit.to_dict(), "fitness": {"errors": errors, "total_bits": total,
                "accuracy": (total - errors) / total, "exact_on_dataset": errors == 0,
                "verified_truth_table": errors == 0 and self.dataset.exhaustive,
                "gates": len(circuit.gates), "depth": circuit.depth},
                "search": {**asdict(self.config), "generation": int(generation), "evaluations": self.evaluations,
                           "history": self.history, "library_candidates": len(self.library),
                           "selection": "tournament", "tournament_size": min(3, self.config.population),
                           "parent_population": int(parent_population),
                           "evaluation_budget": self.config.evaluation_budget}}


def tournament(ranks, rng):
    """Select the best of up to three independently drawn population members."""
    contenders = (rng.randrange(len(ranks)) for _ in range(min(3, len(ranks))))
    return min(contenders, key=ranks.__getitem__)


def search_python(problem):
    p, rng = problem, problem.rng
    best = p.initial_genome()
    score = p.score(best)
    parents, ranks = [best], [score]
    while (len(parents) < p.config.population and not p.expired()
           and (p.config.optimize or score >= p.error_weight)):
        candidate = p.specimen()
        rank = p.score(candidate)
        parents.append(candidate)
        ranks.append(rank)
        if rank < score:
            best, score = candidate, rank
    p.trace(0, score)
    generation = 0
    while (generation < p.config.generations and not p.expired()
           and p.evaluations < p.config.evaluation_budget
           and (p.config.optimize or score >= p.error_weight)):
        generation += 1
        for _ in range(p.config.population):
            if p.expired() or p.evaluations >= p.config.evaluation_budget:
                break
            if rng.random() < 0.15:
                candidate = p.specimen()
            else:
                parent = parents[tournament(ranks, rng)]
                mate = parents[tournament(ranks, rng)]
                candidate = list(parent)
                crossover = rng.random() < 0.35
                for i in range(p.width):
                    if crossover and rng.random() < 0.5:
                        candidate[i] = mate[i]
                    if rng.random() < 1 / p.width:
                        candidate[i] = rng.randrange(p.bound(i))
            rank = p.score(candidate)
            # Replace a worst member, retaining the population's best rank.
            # New equal-ranked genomes can enter without mutating saved parents.
            worst_rank = max(ranks)
            worst = rng.choice([i for i, value in enumerate(ranks) if value == worst_rank])
            if rank <= ranks[worst]:
                parents[worst], ranks[worst] = candidate, rank
            if rank < score:
                best, score = candidate, rank
            if score < p.error_weight and not p.config.optimize:
                break
        p.trace(generation, score)
    return p.result(best, generation, len(parents))

