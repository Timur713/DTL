"""Exact polynomial sign cells on a closed rational interval (degree <= 6).

Sturm isolation proves root counts; finite depth/node limits fail unresolved.
No floating roots, sampled safety claims or threshold tolerances are used.
"""
from dataclasses import dataclass
from fractions import Fraction as Q
from math import comb


def trim(p):
    p = list(map(Q, p)) or [Q(0)]
    while len(p) > 1 and not p[-1]:
        p.pop()
    return tuple(p)


def add(p, q):
    return trim([(p[i] if i < len(p) else 0) + (q[i] if i < len(q) else 0)
                 for i in range(max(len(p), len(q)))])


def scale(p, a):
    return trim([a * v for v in p])


def mul(p, q):
    out = [Q(0)] * (len(p) + len(q) - 1)
    for i, a in enumerate(p):
        for j, b in enumerate(q):
            out[i + j] += a * b
    return trim(out)


def at(p, x):
    value = Q(0)
    for c in reversed(p):
        value = value * x + c
    return value


def derivative(p):
    return trim([i * p[i] for i in range(1, len(p))])


def divide(p, q):
    p, q = list(trim(p)), trim(q)
    if q == (0,):
        raise ZeroDivisionError("zero polynomial")
    out = [Q(0)] * max(1, len(p) - len(q) + 1)
    while len(p) >= len(q) and p != [0]:
        power, factor = len(p) - len(q), p[-1] / q[-1]
        out[power] = factor
        for i, c in enumerate(q):
            p[i + power] -= factor * c
        p = list(trim(p))
    return trim(out), trim(p)


def monic(p):
    return scale(p, 1 / p[-1])


def square_free(p):
    p = trim(p)
    if len(p) <= 1:
        return p
    a, b = p, derivative(p)
    while b != (0,):
        a, b = b, divide(a, b)[1]
    return monic(divide(p, monic(a))[0])


def sturm(p):
    chain = [p, derivative(p)]
    while chain[-1] != (0,):
        remainder = scale(divide(chain[-2], chain[-1])[1], -1)
        if remainder == (0,):
            break
        # Positive normalization keeps signs while reducing coefficient size.
        chain.append(scale(remainder, 1 / abs(remainder[-1])))
    return [p for p in chain if p != (0,)]


def variations(chain, x):
    signs = [1 if value > 0 else -1 for p in chain if (value := at(p, x))]
    return sum(a != b for a, b in zip(signs, signs[1:]))


class IsolationUnresolved(Exception):
    pass


@dataclass(frozen=True)
class Boundary:
    low: Q
    high: Q

    @classmethod
    def exact(cls, value):
        return cls(Q(value), Q(value))

    def to_dict(self):
        return dict(lower_s=float(self.low), upper_s=float(self.high),
                    lower_exact=str(self.low), upper_exact=str(self.high))

    @property
    def midpoint(self):
        return (self.low + self.high) / 2


def isolate_roots(p, low, high, *, bits=36, max_depth=160, max_nodes=10000):
    """Isolate every distinct interior root; endpoint roots remain endpoints."""
    p = square_free(p)
    if len(p) <= 1:
        return []
    chain, roots, nodes = sturm(p), [], 0
    tolerance = Q(1, 2**bits)

    def walk(a, b, depth):
        nonlocal nodes
        nodes += 1
        if nodes > max_nodes:
            raise IsolationUnresolved("root isolation node budget exhausted")
        count = variations(chain, a) - variations(chain, b) - int(at(p, b) == 0)
        if count < 0:
            raise IsolationUnresolved("inconsistent Sturm root count")
        if count == 0:
            return
        if count == 1 and b - a <= tolerance and at(p, a) and at(p, b):
            roots.append(Boundary(a, b))
            return
        if depth >= max_depth:
            raise IsolationUnresolved("root isolation depth budget exhausted")
        mid = (a + b) / 2
        walk(a, mid, depth + 1)
        if at(p, mid) == 0:
            roots.append(Boundary.exact(mid))
        walk(mid, b, depth + 1)

    walk(Q(low), Q(high), 0)
    return roots


def bernstein_bounds(p, a, b):
    """Convex hull bounds after exact power-to-Bernstein conversion."""
    n = len(p) - 1
    power = [sum(p[i] * comb(i, j) * a**(i-j) * (b-a)**j
                 for i in range(j, n+1)) for j in range(n+1)]
    coeff = [sum(power[j] * Q(comb(k, j), comb(n, j)) for j in range(k+1)) for k in range(n+1)]
    return min(coeff), max(coeff)


@dataclass(frozen=True)
class NegativeCell:
    start: Boundary
    end: Boundary
    start_inclusive: bool
    end_inclusive: bool
    witness: Q

    def to_dict(self):
        return dict(start_s=float(self.start.midpoint), end_s=float(self.end.midpoint),
                    start_bracket=self.start.to_dict(), end_bracket=self.end.to_dict(),
                    start_inclusive=self.start_inclusive, end_inclusive=self.end_inclusive,
                    witness_s=float(self.witness), witness_exact=str(self.witness))


def negative_cells(polynomials, low, high, **limits):
    """Maximal cells where ALL polynomials are strictly negative.

    All interior product roots are safe for this strict conjunction. Repeated
    roots are retained as separate boundaries, including isolated safe instants.
    """
    polys = [trim(p) for p in polynomials]
    a, b = Q(low), Q(high)
    if a >= b:
        raise ValueError("Expected a positive interval")
    active = []
    for p in polys:
        lower, upper = bernstein_bounds(p, a, b)
        if lower >= 0:
            return []
        if upper < 0:
            continue
        active.append(p)
    if not active:
        return [NegativeCell(Boundary.exact(a), Boundary.exact(b), True, True, (a+b)/2)]
    product = (Q(1),)
    for p in active:
        product = mul(product, p)
    roots = isolate_roots(product, a, b, **limits)
    bounds = [Boundary.exact(a), *roots, Boundary.exact(b)]
    cells = []
    for index, (left, right) in enumerate(zip(bounds, bounds[1:])):
        sample = (left.high + right.low) / 2
        if not a < sample < b or not all(at(p, sample) < 0 for p in polys):
            continue
        cells.append(NegativeCell(left, right,
                     index == 0 and all(at(p, a) < 0 for p in polys),
                     index == len(bounds)-2 and all(at(p, b) < 0 for p in polys), sample))
    return cells
