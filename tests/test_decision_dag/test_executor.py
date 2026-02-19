"""Tests for decision_dag.executor module."""

import pytest

from epinterface.sbem.decision_dag.dag import (
    AssignmentNode,
    ComparisonOperator,
    ComponentRefNode,
    ConditionalBranch,
    ConditionNode,
    DecisionDAG,
    FieldCondition,
    IntermediateComponent,
)
from epinterface.sbem.decision_dag.executor import DAGExecutor, _evaluate_condition


class TestEvaluateCondition:
    """Tests for individual condition evaluation."""

    def test_eq_match(self):
        cond = FieldCondition(
            field="type", operator=ComparisonOperator.EQ, value="residential"
        )
        assert _evaluate_condition(cond, {"type": "residential"}) is True

    def test_eq_no_match(self):
        cond = FieldCondition(
            field="type", operator=ComparisonOperator.EQ, value="residential"
        )
        assert _evaluate_condition(cond, {"type": "commercial"}) is False

    def test_neq(self):
        cond = FieldCondition(
            field="type", operator=ComparisonOperator.NEQ, value="residential"
        )
        assert _evaluate_condition(cond, {"type": "commercial"}) is True

    def test_lt(self):
        cond = FieldCondition(field="year", operator=ComparisonOperator.LT, value=1960)
        assert _evaluate_condition(cond, {"year": 1950}) is True
        assert _evaluate_condition(cond, {"year": 1960}) is False

    def test_lte(self):
        cond = FieldCondition(field="year", operator=ComparisonOperator.LTE, value=1960)
        assert _evaluate_condition(cond, {"year": 1960}) is True

    def test_gt(self):
        cond = FieldCondition(field="year", operator=ComparisonOperator.GT, value=2000)
        assert _evaluate_condition(cond, {"year": 2010}) is True

    def test_gte(self):
        cond = FieldCondition(field="year", operator=ComparisonOperator.GTE, value=2000)
        assert _evaluate_condition(cond, {"year": 2000}) is True

    def test_in_operator(self):
        cond = FieldCondition(
            field="type", operator=ComparisonOperator.IN, value=["a", "b"]
        )
        assert _evaluate_condition(cond, {"type": "a"}) is True
        assert _evaluate_condition(cond, {"type": "c"}) is False

    def test_not_in_operator(self):
        cond = FieldCondition(
            field="type", operator=ComparisonOperator.NOT_IN, value=["a", "b"]
        )
        assert _evaluate_condition(cond, {"type": "c"}) is True

    def test_contains(self):
        cond = FieldCondition(
            field="notes", operator=ComparisonOperator.CONTAINS, value="renovated"
        )
        assert _evaluate_condition(cond, {"notes": "recently renovated home"}) is True
        assert _evaluate_condition(cond, {"notes": "original condition"}) is False

    def test_is_missing_true(self):
        cond = FieldCondition(field="income", operator=ComparisonOperator.IS_MISSING)
        assert _evaluate_condition(cond, {}) is True
        assert _evaluate_condition(cond, {"income": None}) is True

    def test_is_missing_false(self):
        cond = FieldCondition(field="income", operator=ComparisonOperator.IS_MISSING)
        assert _evaluate_condition(cond, {"income": 50000}) is False

    def test_is_not_missing(self):
        cond = FieldCondition(
            field="income", operator=ComparisonOperator.IS_NOT_MISSING
        )
        assert _evaluate_condition(cond, {"income": 50000}) is True
        assert _evaluate_condition(cond, {}) is False

    def test_missing_field_returns_false_for_comparison(self):
        cond = FieldCondition(field="year", operator=ComparisonOperator.LT, value=2000)
        assert _evaluate_condition(cond, {}) is False


@pytest.fixture()
def branching_dag() -> DecisionDAG:
    """A DAG with branching conditions, components, and assignments."""
    return DecisionDAG(
        description="Test DAG with branching",
        components=[
            IntermediateComponent(
                id="high_perf_wall",
                name="High Performance Wall",
                description="Well-insulated wall assembly",
                assignments={
                    "FacadeStructuralSystem": "woodframe",
                    "FacadeCavityInsulationRValue": 3.5,
                    "FacadeExteriorInsulationRValue": 2.0,
                    "InfiltrationACH": 0.3,
                },
            ),
            IntermediateComponent(
                id="old_wall",
                name="Old Uninsulated Wall",
                description="Pre-1960 uninsulated wall",
                assignments={
                    "FacadeStructuralSystem": "masonry",
                    "FacadeCavityInsulationRValue": 0.0,
                    "FacadeExteriorInsulationRValue": 0.0,
                    "InfiltrationACH": 1.2,
                },
            ),
        ],
        nodes=[
            ConditionNode(
                id="check_age",
                description="Check building age",
                branches=[
                    ConditionalBranch(
                        condition=FieldCondition(
                            field="year_built",
                            operator=ComparisonOperator.LTE,
                            value=1960,
                        ),
                        target_node_id="apply_old_wall",
                    ),
                    ConditionalBranch(
                        condition=FieldCondition(
                            field="year_built",
                            operator=ComparisonOperator.GT,
                            value=1960,
                        ),
                        target_node_id="apply_high_perf_wall",
                    ),
                ],
                default_target_id="apply_old_wall",
            ),
            ComponentRefNode(
                id="apply_old_wall",
                description="Apply old wall component",
                component_id="old_wall",
                next_node_ids=["set_hvac"],
            ),
            ComponentRefNode(
                id="apply_high_perf_wall",
                description="Apply high performance wall component",
                component_id="high_perf_wall",
                next_node_ids=["set_hvac"],
            ),
            AssignmentNode(
                id="set_hvac",
                description="Set default HVAC",
                assignments={
                    "HeatingFuel": "NaturalGas",
                    "HeatingSystemCOP": 0.85,
                    "CoolingFuel": "Electricity",
                    "CoolingSystemCOP": 3.0,
                },
            ),
        ],
        entry_node_ids=["check_age"],
    )


class TestDAGExecutor:
    """Tests for DAGExecutor."""

    def test_old_building_path(self, branching_dag: DecisionDAG):
        executor = DAGExecutor(branching_dag)
        result = executor.execute({"year_built": 1940})

        assert result.assignments["FacadeStructuralSystem"] == "masonry"
        assert result.assignments["InfiltrationACH"] == 1.2
        assert result.assignments["HeatingFuel"] == "NaturalGas"
        assert "apply_old_wall" in result.trace.visited_node_ids
        assert "old_wall" in result.trace.applied_component_ids

    def test_new_building_path(self, branching_dag: DecisionDAG):
        executor = DAGExecutor(branching_dag)
        result = executor.execute({"year_built": 2005})

        assert result.assignments["FacadeStructuralSystem"] == "woodframe"
        assert result.assignments["FacadeCavityInsulationRValue"] == 3.5
        assert result.assignments["InfiltrationACH"] == 0.3
        assert "apply_high_perf_wall" in result.trace.visited_node_ids
        assert "high_perf_wall" in result.trace.applied_component_ids

    def test_missing_field_uses_default(self, branching_dag: DecisionDAG):
        executor = DAGExecutor(branching_dag)
        result = executor.execute({})

        assert result.assignments["FacadeStructuralSystem"] == "masonry"
        assert "apply_old_wall" in result.trace.visited_node_ids

    def test_hvac_always_set(self, branching_dag: DecisionDAG):
        executor = DAGExecutor(branching_dag)
        for row in [{"year_built": 1940}, {"year_built": 2005}, {}]:
            result = executor.execute(row)
            assert "HeatingFuel" in result.assignments
            assert "CoolingSystemCOP" in result.assignments

    def test_trace_records_all_visited(self, branching_dag: DecisionDAG):
        executor = DAGExecutor(branching_dag)
        result = executor.execute({"year_built": 1940})
        assert "check_age" in result.trace.visited_node_ids
        assert "apply_old_wall" in result.trace.visited_node_ids
        assert "set_hvac" in result.trace.visited_node_ids

    def test_cycle_protection(self):
        """Nodes referencing each other should not cause infinite loops."""
        dag = DecisionDAG(
            description="Cyclic DAG for testing",
            components=[],
            nodes=[
                AssignmentNode(
                    id="a",
                    description="Node A",
                    assignments={"HeatingFuel": "Electricity"},
                    next_node_ids=["b"],
                ),
                AssignmentNode(
                    id="b",
                    description="Node B",
                    assignments={"CoolingFuel": "Electricity"},
                    next_node_ids=["a"],
                ),
            ],
            entry_node_ids=["a"],
        )
        executor = DAGExecutor(dag)
        result = executor.execute({})
        assert result.assignments["HeatingFuel"] == "Electricity"
        assert result.assignments["CoolingFuel"] == "Electricity"

    def test_multiple_entry_nodes(self):
        """Independent sub-DAGs for different parameter groups."""
        dag = DecisionDAG(
            description="Multi-entry DAG",
            components=[],
            nodes=[
                AssignmentNode(
                    id="envelope",
                    description="Set envelope params",
                    assignments={"InfiltrationACH": 0.5, "WindowUValue": 2.0},
                ),
                AssignmentNode(
                    id="hvac",
                    description="Set HVAC params",
                    assignments={
                        "HeatingFuel": "NaturalGas",
                        "CoolingFuel": "Electricity",
                    },
                ),
            ],
            entry_node_ids=["envelope", "hvac"],
        )
        executor = DAGExecutor(dag)
        result = executor.execute({})
        assert result.assignments["InfiltrationACH"] == 0.5
        assert result.assignments["HeatingFuel"] == "NaturalGas"

    def test_later_assignments_override_earlier(self):
        """Refinement chain: later nodes override earlier values."""
        dag = DecisionDAG(
            description="Override test",
            components=[],
            nodes=[
                AssignmentNode(
                    id="defaults",
                    description="Broad defaults",
                    assignments={"InfiltrationACH": 0.6, "HeatingFuel": "NaturalGas"},
                    next_node_ids=["override"],
                ),
                AssignmentNode(
                    id="override",
                    description="Override infiltration",
                    assignments={"InfiltrationACH": 0.2},
                ),
            ],
            entry_node_ids=["defaults"],
        )
        executor = DAGExecutor(dag)
        result = executor.execute({})
        assert result.assignments["InfiltrationACH"] == 0.2
        assert result.assignments["HeatingFuel"] == "NaturalGas"

    def test_unresolved_fields_tracked(self, branching_dag: DecisionDAG):
        executor = DAGExecutor(branching_dag)
        result = executor.execute({"year_built": 2005})
        assert len(result.trace.unresolved_fields) > 0
        assert "WindowUValue" in result.trace.unresolved_fields
