"""DAG execution engine.

Processes individual data rows through a DecisionDAG to produce
FlatModel parameter assignments via BFS traversal.
"""

from __future__ import annotations

from collections import deque
from typing import Any

from pydantic import BaseModel, Field

from epinterface.sbem.decision_dag.dag import (
    AssignmentNode,
    ComparisonOperator,
    ComponentRefNode,
    ConditionNode,
    DecisionDAG,
    FieldCondition,
)


class DAGExecutionTrace(BaseModel):
    """Audit trail of a single DAG execution."""

    visited_node_ids: list[str] = Field(
        default_factory=list,
        description="Node IDs visited during execution, in order.",
    )
    applied_component_ids: list[str] = Field(
        default_factory=list,
        description="Component IDs whose assignments were applied.",
    )
    unresolved_fields: list[str] = Field(
        default_factory=list,
        description="FlatModel fields that were not assigned by the DAG.",
    )


class DAGExecutionResult(BaseModel):
    """Result of executing a DAG against a single data row."""

    assignments: dict[str, Any] = Field(
        default_factory=dict,
        description="Collected FlatModel field assignments.",
    )
    trace: DAGExecutionTrace = Field(
        default_factory=DAGExecutionTrace,
        description="Execution audit trail.",
    )


def _is_missing(row: dict[str, Any], field: str) -> bool:
    """Check if a field is absent or None in the data row."""
    return field not in row or row[field] is None


def _evaluate_condition(condition: FieldCondition, row: dict[str, Any]) -> bool:
    """Evaluate a single FieldCondition against a data row."""
    op = condition.operator

    if op == ComparisonOperator.IS_MISSING:
        return _is_missing(row, condition.field)
    if op == ComparisonOperator.IS_NOT_MISSING:
        return not _is_missing(row, condition.field)

    if _is_missing(row, condition.field):
        return False

    row_val = row[condition.field]
    cmp_val = condition.value

    if op == ComparisonOperator.EQ:
        return row_val == cmp_val  # type: ignore[no-any-return]
    if op == ComparisonOperator.NEQ:
        return row_val != cmp_val  # type: ignore[no-any-return]
    if op == ComparisonOperator.LT:
        return row_val < cmp_val  # type: ignore[no-any-return]
    if op == ComparisonOperator.LTE:
        return row_val <= cmp_val  # type: ignore[no-any-return]
    if op == ComparisonOperator.GT:
        return row_val > cmp_val  # type: ignore[no-any-return]
    if op == ComparisonOperator.GTE:
        return row_val >= cmp_val  # type: ignore[no-any-return]
    if op == ComparisonOperator.IN:
        return row_val in cmp_val  # type: ignore[no-any-return]
    if op == ComparisonOperator.NOT_IN:
        return row_val not in cmp_val  # type: ignore[no-any-return]
    if op == ComparisonOperator.CONTAINS:
        return cmp_val in row_val  # type: ignore[no-any-return]

    msg = f"Unknown operator: {op}"
    raise ValueError(msg)


class DAGExecutor:
    """Executes a DecisionDAG against data rows to produce FlatModel assignments.

    Traversal uses BFS from entry nodes. Each node is visited at most once
    to prevent cycles. Later assignments override earlier ones, allowing
    refinement chains.
    """

    def __init__(self, dag: DecisionDAG) -> None:
        """Initialize the executor with a validated DAG."""
        self.dag = dag
        self._node_map = {n.id: n for n in dag.nodes}
        self._component_map = {c.id: c for c in dag.components}

    def execute(self, row: dict[str, Any]) -> DAGExecutionResult:
        """Execute the DAG against a single data row.

        Args:
            row: A dictionary of user field values for one data record.

        Returns:
            DAGExecutionResult with collected assignments and execution trace.
        """
        assignments: dict[str, Any] = {}
        trace = DAGExecutionTrace()
        visited: set[str] = set()
        queue: deque[str] = deque(self.dag.entry_node_ids)

        while queue:
            node_id = queue.popleft()
            if node_id in visited:
                continue
            visited.add(node_id)
            trace.visited_node_ids.append(node_id)

            node = self._node_map.get(node_id)
            if node is None:
                continue

            if isinstance(node, ConditionNode):
                self._process_condition(node, row, queue)
            elif isinstance(node, AssignmentNode):
                assignments.update(node.assignments)
                queue.extend(node.next_node_ids)
            elif isinstance(node, ComponentRefNode):
                comp = self._component_map.get(node.component_id)
                if comp is not None:
                    assignments.update(comp.assignments)
                    trace.applied_component_ids.append(comp.id)
                queue.extend(node.next_node_ids)

        from epinterface.sbem.decision_dag.schema_utils import (
            get_flat_model_field_names,
        )

        all_fields = get_flat_model_field_names()
        trace.unresolved_fields = sorted(all_fields - set(assignments.keys()))

        return DAGExecutionResult(assignments=assignments, trace=trace)

    def execute_to_flat_model(
        self,
        row: dict[str, Any],
        direct_values: dict[str, Any] | None = None,
    ):
        """Execute the DAG and construct a FlatModel instance.

        Args:
            row: A dictionary of user field values for one data record.
            direct_values: Optional dict of FlatModel field values that
                override DAG assignments (e.g. geometry, weather).

        Returns:
            A FlatModel instance with all parameters populated.

        Raises:
            pydantic.ValidationError: If the combined assignments don't
                satisfy FlatModel's validation constraints.
        """
        from epinterface.sbem.flat_model import FlatModel

        result = self.execute(row)
        combined = {**result.assignments}
        if direct_values:
            combined.update(direct_values)
        return FlatModel(**combined)

    @staticmethod
    def _process_condition(
        node: ConditionNode,
        row: dict[str, Any],
        queue: deque[str],
    ) -> None:
        """Evaluate branches and enqueue the first matching target."""
        for branch in node.branches:
            if _evaluate_condition(branch.condition, row):
                queue.append(branch.target_node_id)
                return
        if node.default_target_id is not None:
            queue.append(node.default_target_id)
