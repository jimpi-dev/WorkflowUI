import pytest

from services.graph_hash import graph_hash


def test_graph_hash_deterministic():
    g1 = {"a": 1, "b": 2}
    g2 = {"b": 2, "a": 1}
    assert graph_hash(g1) == graph_hash(g2)


def test_graph_hash_different_graphs_differ():
    g1 = {"a": 1}
    g2 = {"a": 2}
    g3 = {"b": 1}
    h1, h2, h3 = graph_hash(g1), graph_hash(g2), graph_hash(g3)
    assert h1 != h2 and h1 != h3 and h2 != h3


def test_graph_hash_nested_order():
    g1 = {"outer": {"inner_b": 2, "inner_a": 1}}
    g2 = {"outer": {"inner_a": 1, "inner_b": 2}}
    assert graph_hash(g1) == graph_hash(g2)


def test_graph_hash_hex_digest():
    h = graph_hash({"x": 1})
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)
