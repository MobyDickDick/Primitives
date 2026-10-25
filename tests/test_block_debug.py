"""Check visible pins against independent hierarchical execution."""
import copy
import unittest

from primitives.blocks import BlockBundle
from primitives.circuit import Circuit
from primitives.dataset import bits
from tools.export_blocks import examples


class BlockDebugTests(unittest.TestCase):
    def test_every_visible_pin_matches_expansion_and_local_execution(self):
        for original in examples().values():
            bundle = original.wrap("Mehrbitige Box")
            document = bundle.to_dict()

            def check(path):
                view = bundle.view(path)
                c = Circuit.from_dict(view["circuit"])
                nodes = view["circuit"].get("view_nodes", [])
                for x in range(1 << c.inputs):
                    values = c.wires(bits(x, c.inputs))
                    for node in nodes:
                        for port, source in enumerate(node["sources"]):
                            slot = node["sourceBits"][port]
                            source_signal = nodes[source]["signalRefs"][slot]
                            target_signal = node["inputRefs"][port] if node["kind"] in ("instance", "gate") else node["signalRefs"][0]
                            self.assertEqual(values[source_signal], values[target_signal])
                        if node["kind"] == "instance":
                            local = BlockBundle({**document, "root": node["definition"]})
                            inputs = [values[r] for r in node["inputRefs"]]
                            self.assertEqual(local.evaluate(inputs), [values[r] for r in node["signalRefs"]])
                    outputs = [values[n["signalRefs"][0]] for n in nodes if n["kind"] == "output"]
                    if nodes:
                        self.assertEqual(outputs, c.evaluate(bits(x, c.inputs)))
                for node in nodes:
                    if node["kind"] == "instance":
                        check([*path, node["id"]])
            check([])

    def test_multibit_ports_and_instance_paths_are_distinct(self):
        bundle = examples()["ripple-adder-2"]
        boxes = bundle.wrap("Wrapper").view()["circuit"]["view_nodes"]
        body = next(n for n in boxes if n["kind"] == "instance")
        self.assertEqual([p["bits"] for p in body["interface"]["outputs"]], [2, 1])
        self.assertEqual((len(body["inputRefs"]), len(body["signalRefs"])), (5, 3))
        low, high = bundle.view(["low"]), bundle.view(["high"])
        self.assertEqual(low, high)  # Same fixed definition; caller keeps separate instance paths.
        before = copy.deepcopy(bundle.to_dict())
        low["circuit"]["gates"].clear()
        self.assertEqual(bundle.to_dict(), before)
        for invalid in (["absent"], ["low", "absent"], "low", [1], ["low"] * 33):
            with self.assertRaises(ValueError):
                bundle.view(invalid)

    def test_direct_and_shared_outputs_with_a_local_nand(self):
        from tools.export_blocks import inp, out, ports, instance
        leaf = BlockBundle.from_circuit("Bit permutation", Circuit(2, (), (1, 0, 1)),
                                        ports([("word", 2)], [("pair", 2), ("again", 1)]))
        bundle = BlockBundle.create({"name": "Direct wires and NAND", "version": 1,
            "interface": ports([("a", 2)], [("result", 2)]),
            "nodes": [instance("bus", leaf, word=[inp("a", 1), inp("a", 0)]),
                      {"id": "invert", "type": "nand", "inputs": [out("bus", "again"), out("bus", "pair", 0)]}],
            "outputs": {"result": [out("invert", "out"), out("bus", "pair", 1)]}}, [leaf])
        view = bundle.view()["circuit"]
        bus = next(n for n in view["view_nodes"] if n["kind"] == "instance")
        self.assertEqual(bus["signalRefs"], [0, 1, 0])
        gate = next(n for n in view["view_nodes"] if n["kind"] == "gate")
        self.assertEqual(gate["sourceBits"], [2, 0])
        for x in range(4):
            values = Circuit.from_dict(view).wires(bits(x, 2))
            self.assertEqual([values[n["signalRefs"][0]] for n in view["view_nodes"] if n["kind"] == "output"], bundle.evaluate(bits(x, 2)))


if __name__ == "__main__":
    unittest.main()
