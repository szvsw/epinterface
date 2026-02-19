"""Decision DAG module for LLM-driven FlatModel inference.

Provides schemas for user field definitions, a decision DAG structure
that maps user data to FlatModel parameters, an execution engine,
structural validation, and a Pydantic AI agent for DAG generation.
"""

from epinterface.sbem.decision_dag.dag import (
    AssignmentNode,
    ComparisonOperator,
    ComponentRefNode,
    ConditionalBranch,
    ConditionNode,
    DAGNode,
    DecisionDAG,
    FieldCondition,
    IntermediateComponent,
)
from epinterface.sbem.decision_dag.executor import (
    DAGExecutionResult,
    DAGExecutionTrace,
    DAGExecutor,
)
from epinterface.sbem.decision_dag.fields import (
    FieldType,
    SupplementaryContext,
    UserFieldDefinition,
    UserFieldSet,
)
from epinterface.sbem.decision_dag.schema_utils import (
    get_flat_model_field_names,
    get_flat_model_schema_description,
    validate_dag_assignments,
)

__all__ = [
    "AssignmentNode",
    "ComparisonOperator",
    "ComponentRefNode",
    "ConditionNode",
    "ConditionalBranch",
    "DAGExecutionResult",
    "DAGExecutionTrace",
    "DAGExecutor",
    "DAGNode",
    "DecisionDAG",
    "FieldCondition",
    "FieldType",
    "IntermediateComponent",
    "SupplementaryContext",
    "UserFieldDefinition",
    "UserFieldSet",
    "get_flat_model_field_names",
    "get_flat_model_schema_description",
    "validate_dag_assignments",
]
