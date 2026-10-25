"""Example oracle: a 2-bit half adder, x0 + x1 as a 2-bit integer."""


def oracle(x):
    return (x & 1) + ((x >> 1) & 1)

