"""Bit-parallel fitness, library grafting and the optional Python search backend."""
from dataclasses import dataclass, asdict
import random
from .circuit import Circuit


@dataclass
class SearchConfig:
    gates: int = 12
    population: int = 24
    generations: int = 200
    seed: int = 1
    backend: str = "tiny"

    def validate(self):
        for name, lo, hi in (("gates", 1, 128), ("population", 2, 256), ("generations", 1, 20000), ("seed", 0, 2**31-1)):
            value = getattr(self, name)
            if type(value) is not int or not lo <= value <= hi:
                raise ValueError(f"{name} muss zwischen {lo} und {hi} liegen.")
        if self.backend not in ("tiny", "python"):
            raise ValueError("backend muss tiny oder python sein.")
        if self.population * self.generations > 500000:
            raise ValueError("Pro Lauf sind höchstens 500000 Kandidaten erlaubt.")


def genome_circuit(genome, n, m):
    gate_genes = len(genome) - m
    return Circuit(n, tuple(tuple(genome[i:i+2]) for i in range(0, gate_genes, 2)), tuple(genome[-m:]))


class Problem:
    def __init__(self, dataset, config, library=()):
        config.validate()
        self.dataset, self.config = dataset, config
        self.n, self.m, self.g = dataset.inputs, dataset.outputs, config.gates
        self.width = self.g * 2 + self.m
        self.rng = random.Random(config.seed)
        self.library = [c.compact() for c in library if c.inputs <= self.n and len(c.compact().gates) <= self.g]
        self.mask = (1 << len(dataset.rows)) - 1
        columns = [0] * (self.n + self.m)
        for i, row in enumerate(dataset.rows):
            for j, bit in enumerate(row):
                columns[j] |= bit << i
        self.columns, self.targets = columns[:self.n], columns[self.n:]
        # Any single error outweighs all possible gate and depth costs.
        self.error_weight = (self.g + 1) ** 2
        self.history, self.evaluations = [], 0
        self.best_score = None

    def bound(self, gene):
        return self.n + (gene // 2 if gene < 2*self.g else self.g)

    def random_genome(self):
        return [self.rng.randrange(self.bound(i)) for i in range(self.width)]

    def specimen(self):
        """Compose up to two saved circuits on inputs AND earlier gate outputs."""
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

    def result(self, genome, generation):
        circuit = genome_circuit(genome, self.n, self.m).compact()
        errors, _, _ = self.metrics(genome)
        total = len(self.dataset.rows) * self.m
        return {"circuit": circuit.to_dict(), "fitness": {"errors": errors, "total_bits": total,
                "accuracy": (total - errors) / total, "exact_on_dataset": errors == 0,
                "verified_truth_table": errors == 0 and self.dataset.exhaustive,
                "gates": len(circuit.gates), "depth": circuit.depth},
                "search": {**asdict(self.config), "generation": int(generation), "evaluations": self.evaluations,
                           "history": self.history, "library_candidates": len(self.library)}}


def search_python(problem):
    p, rng = problem, problem.rng
    parent, mate = p.specimen(), p.specimen()
    score = p.score(parent)
    p.trace(0, score)
    generation = 0
    while generation < p.config.generations and score >= p.error_weight:
        generation += 1
        for _ in range(p.config.population):
            candidate = list(parent)
            if rng.random() < 0.15:
                candidate = p.specimen()
            else:
                crossover = rng.random() < 0.35
                for i in range(p.width):
                    if crossover and rng.random() < 0.5:
                        candidate[i] = mate[i]
                    if rng.random() < 1 / p.width:
                        candidate[i] = rng.randrange(p.bound(i))
            rank = p.score(candidate)
            if rank <= score:
                mate, parent, score = parent, candidate, rank
            if score < p.error_weight:
                break
        p.trace(generation, score)
    return p.result(parent, generation)

