"""Structural validation of a DecisionDAG.

Checks graph integrity, reference consistency, acyclicity,
field existence, and parameter coverage.
"""

from __future__ import annotations

from collections import deque
from typing import Any

from epinterface.sbem.decision_dag.dag import (
    AssignmentNode,
    ComponentRefNode,
    ConditionNode,
    DecisionDAG,
)
from epinterface.sbem.decision_dag.fields import UserFieldSet
from epinterface.sbem.decision_dag.schema_utils import (
    GEOMETRY_AND_WEATHER_FIELDS,
    get_flat_model_field_names,
    validate_dag_assignments,
)


def validate_dag_structure(
    dag: DecisionDAG,
    field_set: UserFieldSet | None = None,
    require_full_coverage: bool = False,
) -> list[str]:
    """Run all structural validation checks on a DAG.

    Args:
        dag: The decision DAG to validate.
        field_set: If provided, validates that all field references in
            conditions exist in the user's field set.
        require_full_coverage: If True, checks that every non-geometry/weather
            FlatModel field is assigned on at least one path.

    Returns:
        A list of error messages (empty if valid).
    """
    errors: list[str] = []

    errors.extend(_validate_node_refs(dag))
    errors.extend(_validate_entry_nodes(dag))
    errors.extend(_validate_component_refs(dag))
    errors.extend(_validate_acyclic(dag))
    errors.extend(validate_dag_assignments(dag))

    if field_set is not None:
        errors.extend(_validate_field_refs(dag, field_set))

    if require_full_coverage:
        errors.extend(_validate_coverage(dag))

    return errors


def _validate_node_refs(dag: DecisionDAG) -> list[str]:
    """Check that all target_node_id and next_node_ids reference existing nodes."""
    errors: list[str] = []
    node_ids = {n.id for n in dag.nodes}

    for node in dag.nodes:
        if isinstance(node, ConditionNode):
            for branch in node.branches:
                if branch.target_node_id not in node_ids:
                    errors.append(
                        f"ConditionNode '{node.id}': branch target '{branch.target_node_id}' does not exist."
                    )
            if node.default_target_id and node.default_target_id not in node_ids:
                errors.append(
                    f"ConditionNode '{node.id}': default target '{node.default_target_id}' does not exist."
                )
        elif isinstance(node, (AssignmentNode, ComponentRefNode)):
            for nid in node.next_node_ids:
                if nid not in node_ids:
                    errors.append(
                        f"Node '{node.id}': next_node_id '{nid}' does not exist."
                    )

    return errors


def _validate_entry_nodes(dag: DecisionDAG) -> list[str]:
    """Check that all entry_node_ids reference existing nodes."""
    errors: list[str] = []
    node_ids = {n.id for n in dag.nodes}
    for eid in dag.entry_node_ids:
        if eid not in node_ids:
            errors.append(f"entry_node_id '{eid}' does not exist.")
    return errors


def _validate_component_refs(dag: DecisionDAG) -> list[str]:
    """Check that all ComponentRefNode.component_id values reference existing components."""
    errors: list[str] = []
    comp_ids = {c.id for c in dag.components}
    for node in dag.nodes:
        if isinstance(node, ComponentRefNode) and node.component_id not in comp_ids:
            errors.append(
                f"ComponentRefNode '{node.id}': references unknown component '{node.component_id}'."
            )
    return errors


def _get_successors(node: Any) -> list[str]:
    """Get all successor node IDs from a node."""
    if isinstance(node, ConditionNode):
        targets = [b.target_node_id for b in node.branches]
        if node.default_target_id:
            targets.append(node.default_target_id)
        return targets
    if isinstance(node, (AssignmentNode, ComponentRefNode)):
        return list(node.next_node_ids)
    return []


def _validate_acyclic(dag: DecisionDAG) -> list[str]:
    """Check that the DAG has no cycles using DFS-based topological ordering."""
    errors: list[str] = []
    node_map = {n.id: n for n in dag.nodes}

    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = dict.fromkeys(node_map, WHITE)

    def dfs(nid: str) -> bool:
        color[nid] = GRAY
        node = node_map.get(nid)
        if node is not None:
            for succ_id in _get_successors(node):
                if succ_id not in color:
                    continue
                if color[succ_id] == GRAY:
                    errors.append(
                        f"Cycle detected involving node '{nid}' -> '{succ_id}'."
                    )
                    return True
                if color[succ_id] == WHITE and dfs(succ_id):
                    return True
        color[nid] = BLACK
        return False

    for nid in node_map:
        if color[nid] == WHITE:
            dfs(nid)

    return errors


def _validate_field_refs(dag: DecisionDAG, field_set: UserFieldSet) -> list[str]:
    """Check that all field references in conditions exist in the user's field set."""
    errors: list[str] = []
    user_fields = {f.name for f in field_set.fields}

    for node in dag.nodes:
        if isinstance(node, ConditionNode):
            for branch in node.branches:
                if branch.condition.field not in user_fields:
                    errors.append(
                        f"ConditionNode '{node.id}': references unknown user field '{branch.condition.field}'."
                    )

    return errors


def _validate_coverage(dag: DecisionDAG) -> list[str]:
    """Check that every non-geometry/weather FlatModel field is assigned somewhere in the DAG.

    This is a conservative check: it verifies that each field appears
    in at least one assignment node or component, not that every
    execution path covers it.
    """
    errors: list[str] = []
    required = get_flat_model_field_names() - GEOMETRY_AND_WEATHER_FIELDS

    assigned: set[str] = set()
    for node in dag.nodes:
        if isinstance(node, AssignmentNode):
            assigned.update(node.assignments.keys())

    comp_map = {c.id: c for c in dag.components}
    for node in dag.nodes:
        if isinstance(node, ComponentRefNode):
            comp = comp_map.get(node.component_id)
            if comp is not None:
                assigned.update(comp.assignments.keys())

    missing = sorted(required - assigned)
    if missing:
        errors.append(f"The following FlatModel fields are never assigned: {missing}")

    return errors


def _collect_reachable_assignments(dag: DecisionDAG) -> dict[str, set[str]]:
    """For each entry node, collect the set of FlatModel fields potentially assigned.

    Traverses all possible paths via BFS (following all branches).
    Returns a mapping of entry_node_id -> set of field names.
    """
    node_map = {n.id: n for n in dag.nodes}
    comp_map = {c.id: c for c in dag.components}
    result: dict[str, set[str]] = {}

    for entry_id in dag.entry_node_ids:
        fields: set[str] = set()
        visited: set[str] = set()
        queue: deque[str] = deque([entry_id])

        while queue:
            nid = queue.popleft()
            if nid in visited:
                continue
            visited.add(nid)
            node = node_map.get(nid)
            if node is None:
                continue

            if isinstance(node, AssignmentNode):
                fields.update(node.assignments.keys())
                queue.extend(node.next_node_ids)
            elif isinstance(node, ComponentRefNode):
                comp = comp_map.get(node.component_id)
                if comp is not None:
                    fields.update(comp.assignments.keys())
                queue.extend(node.next_node_ids)
            elif isinstance(node, ConditionNode):
                for branch in node.branches:
                    queue.append(branch.target_node_id)
                if node.default_target_id:
                    queue.append(node.default_target_id)

        result[entry_id] = fields

    return result
