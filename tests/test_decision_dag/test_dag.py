"""Tests for decision_dag.dag module -- serialization and schema validation."""

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


class TestFieldCondition:
    """Tests for FieldCondition."""

    def test_eq_condition(self):
        cond = FieldCondition(
            field="building_type",
            operator=ComparisonOperator.EQ,
            value="residential",
        )
        assert cond.field == "building_type"
        assert cond.operator == ComparisonOperator.EQ

    def test_is_missing_no_value_needed(self):
        cond = FieldCondition(
            field="renovation_year",
            operator=ComparisonOperator.IS_MISSING,
        )
        assert cond.value is None

    def test_numeric_comparison(self):
        cond = FieldCondition(
            field="year_built",
            operator=ComparisonOperator.LTE,
            value=1950,
        )
        assert cond.value == 1950


class TestNodes:
    """Tests for DAG node types."""

    def test_condition_node(self):
        node = ConditionNode(
            id="check_type",
            description="Check building type",
            branches=[
                ConditionalBranch(
                    condition=FieldCondition(
                        field="building_type",
                        operator=ComparisonOperator.EQ,
                        value="residential",
                    ),
                    target_node_id="residential_path",
                ),
            ],
            default_target_id="default_path",
        )
        assert node.node_type == "condition"
        assert len(node.branches) == 1

    def test_assignment_node(self):
        node = AssignmentNode(
            id="set_defaults",
            description="Set default HVAC parameters",
            assignments={
                "HeatingFuel": "NaturalGas",
                "HeatingSystemCOP": 0.85,
            },
            next_node_ids=["next_step"],
        )
        assert node.node_type == "assignment"
        assert node.assignments["HeatingFuel"] == "NaturalGas"

    def test_component_ref_node(self):
        node = ComponentRefNode(
            id="apply_wall",
            description="Apply high-perf wall component",
            component_id="high_perf_wall",
            next_node_ids=[],
        )
        assert node.node_type == "component_ref"

    def test_assignment_node_default_next_nodes(self):
        node = AssignmentNode(
            id="leaf",
            description="Terminal assignment",
            assignments={"InfiltrationACH": 0.5},
        )
        assert node.next_node_ids == []


class TestIntermediateComponent:
    """Tests for IntermediateComponent."""

    def test_create_component(self):
        comp = IntermediateComponent(
            id="old_leaky_wall",
            name="Old Leaky SF Wall",
            description="Pre-1950 uninsulated wood frame wall",
            assignments={
                "FacadeStructuralSystem": "woodframe",
                "FacadeCavityInsulationRValue": 0.0,
                "FacadeExteriorInsulationRValue": 0.0,
                "InfiltrationACH": 1.2,
            },
        )
        assert comp.name == "Old Leaky SF Wall"
        assert len(comp.assignments) == 4


class TestDecisionDAG:
    """Tests for DecisionDAG serialization and structure."""

    @pytest.fixture()
    def simple_dag(self) -> DecisionDAG:
        """A minimal DAG for testing."""
        return DecisionDAG(
            description="Simple test DAG",
            components=[
                IntermediateComponent(
                    id="default_envelope",
                    name="Default Envelope",
                    description="Baseline envelope assumptions",
                    assignments={
                        "FacadeStructuralSystem": "cmu",
                        "FacadeCavityInsulationRValue": 2.0,
                        "InfiltrationACH": 0.6,
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
                            target_node_id="old_building",
                        ),
                    ],
                    default_target_id="new_building",
                ),
                AssignmentNode(
                    id="old_building",
                    description="Old building defaults",
                    assignments={"InfiltrationACH": 1.5},
                ),
                ComponentRefNode(
                    id="new_building",
                    description="New building uses default envelope",
                    component_id="default_envelope",
                ),
            ],
            entry_node_ids=["check_age"],
        )

    def test_dag_structure(self, simple_dag: DecisionDAG):
        assert len(simple_dag.nodes) == 3
        assert len(simple_dag.components) == 1
        assert simple_dag.entry_node_ids == ["check_age"]

    def test_dag_serialization_roundtrip(self, simple_dag: DecisionDAG):
        data = simple_dag.model_dump()
        dag2 = DecisionDAG.model_validate(data)
        assert dag2.description == simple_dag.description
        assert len(dag2.nodes) == len(simple_dag.nodes)
        assert len(dag2.components) == len(simple_dag.components)

    def test_dag_json_roundtrip(self, simple_dag: DecisionDAG):
        json_str = simple_dag.model_dump_json()
        dag2 = DecisionDAG.model_validate_json(json_str)
        assert dag2.entry_node_ids == simple_dag.entry_node_ids

    def test_discriminated_union_deserialization(self):
        """Ensure node_type discriminator works correctly from raw dicts."""
        dag_data = {
            "description": "test",
            "components": [],
            "nodes": [
                {
                    "node_type": "condition",
                    "id": "c1",
                    "description": "cond",
                    "branches": [],
                },
                {
                    "node_type": "assignment",
                    "id": "a1",
                    "description": "assign",
                    "assignments": {"HeatingFuel": "Electricity"},
                },
                {
                    "node_type": "component_ref",
                    "id": "r1",
                    "description": "ref",
                    "component_id": "comp1",
                },
            ],
            "entry_node_ids": ["c1"],
        }
        dag = DecisionDAG.model_validate(dag_data)
        assert isinstance(dag.nodes[0], ConditionNode)
        assert isinstance(dag.nodes[1], AssignmentNode)
        assert isinstance(dag.nodes[2], ComponentRefNode)
