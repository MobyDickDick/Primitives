"""Candidate identities and a self-contained ancestry DAG for the search winner."""
import hashlib
import json


def circuit_source(circuit, kind="circuit", key=None):
    document = circuit.compact().to_dict()
    key = key or hashlib.sha256(json.dumps(document, sort_keys=True).encode()).hexdigest()
    return {"kind": kind, "id": key, "circuit": document}


class Ancestry:
    def __init__(self):
        self.nodes = {}
        self.migrations = []
        self.sources = {}

    def source(self, source):
        key = source["kind"] + ":" + source["id"]
        self.sources[key] = source
        return key

    def record(self, key, genome, score, restart, generation, island, origin,
               parent_id=0, mate_id=0, parent=None, flags=None):
        flags = flags or [0] * len(genome)
        node = {"id": key, "restart": restart, "generation": int(generation),
                "island": int(island), "score": score,
                "parents": [int(parent_id)] if parent_id else []}
        if parent_id:
            if mate_id:
                node["parents"].append(int(mate_id))
            node.update(operator="variation",
                        changes=[[i, value] for i, value in enumerate(genome) if value != parent[i]],
                        crossover_genes=[i for i, flag in enumerate(flags) if flag & 1],
                        mutation_genes=[i for i, flag in enumerate(flags) if flag & 2])
        else:
            node.update(operator=origin["kind"], genome=list(genome), origin=origin)
        self.nodes[key] = node
        return key

    def export(self, root):
        # Iterative traversal also supports very long neutral lineages.
        reachable, pending = set(), [root]
        while pending:
            key = pending.pop()
            if key not in reachable:
                reachable.add(key)
                pending.extend(self.nodes[key]["parents"])
        sources = {seed["source"] for key in reachable
                   for seed in self.nodes[key].get("origin", {}).get("seeds", [])}
        return {"schema": 1, "scope": "winner_ancestors", "root": root,
                "nodes": [self.nodes[key] for key in sorted(reachable)],
                "sources": {key: self.sources[key] for key in sorted(sources)},
                "migrations": [event for event in self.migrations if event["candidate_id"] in reachable],
                "transformations": []}


def transformed(result, operation, circuit, **details):
    """Keep the selected candidate distinct from subsequent circuit rewrites."""
    search = result.get("search", {})
    ancestry = search.get("ancestry")
    if ancestry is None:
        return result
    ancestry = {**ancestry, "transformations": [*ancestry["transformations"],
                {"operation": operation, "circuit": circuit.to_dict(), **details}]}
    return {**result, "search": {**search, "ancestry": ancestry}}
