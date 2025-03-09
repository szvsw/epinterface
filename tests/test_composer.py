"""Tests for the component composer."""

import pytest

from epinterface.sbem.common import NamedObject
from epinterface.sbem.components.composer import construct_graph


@pytest.fixture(scope="module")
def root_nodes():
    """A fixture that returns a tuple of the root nodes for the test."""

    class OmittedLeafComponent(NamedObject):
        a: int

    class OmittedComponent(NamedObject):
        a: int
        b: OmittedLeafComponent

    class TruncatedLeafAComponent(NamedObject):
        a: int
        b: str
        c: list[float]
        d: list[OmittedComponent]

    class LeafBComponent(NamedObject):
        d: bool
        e: list[str]

    class LeafCComponent(NamedObject):
        a: int
        b: str

    class MiddleComponent(NamedObject):
        a1: TruncatedLeafAComponent
        a2: TruncatedLeafAComponent
        b: LeafBComponent

    class RootComponent(NamedObject):
        a: MiddleComponent
        b: MiddleComponent
        c: LeafCComponent

    return (
        RootComponent,
        MiddleComponent,
        LeafCComponent,
        LeafBComponent,
        OmittedComponent,
        TruncatedLeafAComponent,
    )


def test_construct_graph(root_nodes: tuple[type[NamedObject], ...]):
    """Test the construction of a graph."""
    (
        RootComponent,
        MiddleComponent,
        LeafCComponent,
        LeafBComponent,
        OmittedComponent,
        TruncatedLeafAComponent,
    ) = root_nodes
    root_graph = construct_graph(RootComponent)
    middle_graph = construct_graph(MiddleComponent)
    leaf_c_graph = construct_graph(LeafCComponent)
    leaf_b_graph = construct_graph(LeafBComponent)
    truncated_leaf_a_graph = construct_graph(TruncatedLeafAComponent)
    omitted_graph = construct_graph(OmittedComponent)

    assert len(omitted_graph.edges) == 1
    assert len(omitted_graph.nodes) == 2
    assert len(truncated_leaf_a_graph.edges) == 0
    assert len(truncated_leaf_a_graph.nodes) == 0
    assert len(leaf_b_graph.edges) == 0
    assert len(leaf_b_graph.nodes) == 0
    assert len(leaf_c_graph.edges) == 0
    assert len(leaf_c_graph.nodes) == 0
    assert len(middle_graph.edges) == 2 * (
        len(truncated_leaf_a_graph.edges) + 1
    ) + 1 * (len(leaf_b_graph.edges) + 1)
    assert len(root_graph.edges) == 2 * (len(middle_graph.edges) + 1) + 1 * (
        len(leaf_c_graph.edges) + 1
    )

    assert (
        sum(
            1
            for edge in root_graph.edges(data=True)
            if edge[-1]["data"]["type"] is MiddleComponent
        )
        == 2
    )
    assert (
        sum(
            1
            for edge in root_graph.edges(data=True)
            if edge[-1]["data"]["type"] is LeafCComponent
        )
        == 1
    )
    assert (
        sum(
            1
            for edge in root_graph.edges(data=True)
            if edge[-1]["data"]["type"] is LeafBComponent
        )
        == 2
    )
    assert (
        sum(
            1
            for edge in root_graph.edges(data=True)
            if edge[-1]["data"]["type"] is TruncatedLeafAComponent
        )
        == 2 * 2
    )
    assert len(root_graph.edges) == 9
