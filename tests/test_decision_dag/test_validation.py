"""Tests for decision_dag.validation module."""

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
from epinterface.sbem.decision_dag.fields import (
    FieldType,
    UserFieldDefinition,
    UserFieldSet,
)
from epinterface.sbem.decision_dag.schema_utils import (
    get_flat_model_field_names,
    get_flat_model_schema_description,
    validate_dag_assignments,
)
from epinterface.sbem.decision_dag.validation import (
    _validate_acyclic,
    _validate_component_refs,
    _validate_coverage,
    _validate_entry_nodes,
    _validate_field_refs,
    _validate_node_refs,
    validate_dag_structure,
)


@pytest.fixture()
def valid_dag() -> DecisionDAG:
    """A structurally valid DAG."""
    return DecisionDAG(
        description="Valid test DAG",
        components=[
            IntermediateComponent(
                id="comp1",
                name="Test Component",
                description="A test component",
                assignments={"HeatingFuel": "NaturalGas"},
            ),
        ],
        nodes=[
            ConditionNode(
                id="root",
                description="Root condition",
                branches=[
                    ConditionalBranch(
                        condition=FieldCondition(
                            field="building_type",
                            operator=ComparisonOperator.EQ,
                            value="residential",
                        ),
                        target_node_id="assign1",
                    ),
                ],
                default_target_id="ref1",
            ),
            AssignmentNode(
                id="assign1",
                description="Residential assignments",
                assignments={"HeatingFuel": "NaturalGas"},
            ),
            ComponentRefNode(
                id="ref1",
                description="Default component",
                component_id="comp1",
            ),
        ],
        entry_node_ids=["root"],
    )


@pytest.fixture()
def field_set() -> UserFieldSet:
    """A simple field set for validation tests."""
    return UserFieldSet(
        fields=[
            UserFieldDefinition(
                name="building_type",
                field_type=FieldType.CATEGORICAL,
                description="Building type",
                categories=["residential", "commercial"],
            ),
            UserFieldDefinition(
                name="year_built",
                field_type=FieldType.NUMERIC,
                description="Year built",
                min_value=1800,
                max_value=2025,
            ),
        ],
    )


class TestNodeRefValidation:
    """Tests for _validate_node_refs."""

    def test_valid_refs(self, valid_dag: DecisionDAG):
        assert _validate_node_refs(valid_dag) == []

    def test_invalid_branch_target(self):
        dag = DecisionDAG(
            description="test",
            components=[],
            nodes=[
                ConditionNode(
                    id="root",
                    description="Root",
                    branches=[
                        ConditionalBranch(
                            condition=FieldCondition(
                                field="x",
                                operator=ComparisonOperator.EQ,
                                value="y",
                            ),
                            target_node_id="nonexistent",
                        ),
                    ],
                ),
            ],
            entry_node_ids=["root"],
        )
        errors = _validate_node_refs(dag)
        assert any("nonexistent" in e for e in errors)

    def test_invalid_default_target(self):
        dag = DecisionDAG(
            description="test",
            components=[],
            nodes=[
                ConditionNode(
                    id="root",
                    description="Root",
                    branches=[],
                    default_target_id="missing",
                ),
            ],
            entry_node_ids=["root"],
        )
        errors = _validate_node_refs(dag)
        assert any("missing" in e for e in errors)

    def test_invalid_next_node_id(self):
        dag = DecisionDAG(
            description="test",
            components=[],
            nodes=[
                AssignmentNode(
                    id="a",
                    description="A",
                    assignments={},
                    next_node_ids=["ghost"],
                ),
            ],
            entry_node_ids=["a"],
        )
        errors = _validate_node_refs(dag)
        assert any("ghost" in e for e in errors)


class TestEntryNodeValidation:
    """Tests for _validate_entry_nodes."""

    def test_valid_entries(self, valid_dag: DecisionDAG):
        assert _validate_entry_nodes(valid_dag) == []

    def test_invalid_entry(self):
        dag = DecisionDAG(
            description="test",
            components=[],
            nodes=[],
            entry_node_ids=["missing"],
        )
        errors = _validate_entry_nodes(dag)
        assert len(errors) == 1


class TestComponentRefValidation:
    """Tests for _validate_component_refs."""

    def test_valid_refs(self, valid_dag: DecisionDAG):
        assert _validate_component_refs(valid_dag) == []

    def test_invalid_component_ref(self):
        dag = DecisionDAG(
            description="test",
            components=[],
            nodes=[
                ComponentRefNode(
                    id="ref",
                    description="Bad ref",
                    component_id="nonexistent_comp",
                ),
            ],
            entry_node_ids=["ref"],
        )
        errors = _validate_component_refs(dag)
        assert any("nonexistent_comp" in e for e in errors)


class TestAcyclicValidation:
    """Tests for _validate_acyclic."""

    def test_acyclic_dag(self, valid_dag: DecisionDAG):
        assert _validate_acyclic(valid_dag) == []

    def test_cycle_detected(self):
        dag = DecisionDAG(
            description="cyclic",
            components=[],
            nodes=[
                AssignmentNode(
                    id="a",
                    description="A",
                    assignments={},
                    next_node_ids=["b"],
                ),
                AssignmentNode(
                    id="b",
                    description="B",
                    assignments={},
                    next_node_ids=["a"],
                ),
            ],
            entry_node_ids=["a"],
        )
        errors = _validate_acyclic(dag)
        assert len(errors) > 0
        assert any("Cycle" in e for e in errors)


class TestFieldRefValidation:
    """Tests for _validate_field_refs."""

    def test_valid_field_refs(self, valid_dag: DecisionDAG, field_set: UserFieldSet):
        assert _validate_field_refs(valid_dag, field_set) == []

    def test_unknown_field_ref(self, field_set: UserFieldSet):
        dag = DecisionDAG(
            description="test",
            components=[],
            nodes=[
                ConditionNode(
                    id="root",
                    description="Root",
                    branches=[
                        ConditionalBranch(
                            condition=FieldCondition(
                                field="unknown_field",
                                operator=ComparisonOperator.EQ,
                                value="x",
                            ),
                            target_node_id="root",
                        ),
                    ],
                ),
            ],
            entry_node_ids=["root"],
        )
        errors = _validate_field_refs(dag, field_set)
        assert any("unknown_field" in e for e in errors)


class TestAssignmentValidation:
    """Tests for validate_dag_assignments."""

    def test_valid_assignments(self, valid_dag: DecisionDAG):
        assert validate_dag_assignments(valid_dag) == []

    def test_invalid_field_name_in_assignment(self):
        dag = DecisionDAG(
            description="test",
            components=[],
            nodes=[
                AssignmentNode(
                    id="bad",
                    description="Bad assignment",
                    assignments={"NotARealField": 42},
                ),
            ],
            entry_node_ids=["bad"],
        )
        errors = validate_dag_assignments(dag)
        assert any("NotARealField" in e for e in errors)

    def test_invalid_field_in_component(self):
        dag = DecisionDAG(
            description="test",
            components=[
                IntermediateComponent(
                    id="bad_comp",
                    name="Bad",
                    description="Bad component",
                    assignments={"FakeParameter": 99},
                ),
            ],
            nodes=[],
            entry_node_ids=[],
        )
        errors = validate_dag_assignments(dag)
        assert any("FakeParameter" in e for e in errors)


class TestCoverageValidation:
    """Tests for _validate_coverage."""

    def test_incomplete_coverage(self, valid_dag: DecisionDAG):
        errors = _validate_coverage(valid_dag)
        assert len(errors) > 0
        assert any("never assigned" in e for e in errors)


class TestFullValidation:
    """Tests for validate_dag_structure (all checks combined)."""

    def test_valid_dag_passes(self, valid_dag: DecisionDAG, field_set: UserFieldSet):
        errors = validate_dag_structure(valid_dag, field_set=field_set)
        assert errors == []

    def test_full_validation_catches_multiple_issues(self):
        dag = DecisionDAG(
            description="broken",
            components=[],
            nodes=[
                ConditionNode(
                    id="root",
                    description="Root",
                    branches=[
                        ConditionalBranch(
                            condition=FieldCondition(
                                field="x",
                                operator=ComparisonOperator.EQ,
                                value="y",
                            ),
                            target_node_id="ghost",
                        ),
                    ],
                ),
            ],
            entry_node_ids=["root", "also_missing"],
        )
        errors = validate_dag_structure(dag)
        assert len(errors) >= 2


class TestSchemaUtils:
    """Tests for schema introspection utilities."""

    def test_get_field_names(self):
        names = get_flat_model_field_names()
        assert "HeatingFuel" in names
        assert "InfiltrationACH" in names
        assert "WWR" in names
        assert "FacadeStructuralSystem" in names

    def test_schema_description_includes_groups(self):
        desc = get_flat_model_schema_description()
        assert "HVAC Systems" in desc
        assert "Facade Construction" in desc
        assert "HeatingFuel" in desc
        assert "InfiltrationACH" in desc

    def test_schema_description_includes_constraints(self):
        desc = get_flat_model_schema_description()
        assert "ge=" in desc or "le=" in desc
