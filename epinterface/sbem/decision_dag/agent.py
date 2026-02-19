"""Pydantic AI agent for generating DecisionDAGs from user field definitions.

Uses structured output to have an LLM produce a validated DecisionDAG
that maps user data fields to FlatModel parameters.

Requires the ``pydantic-ai`` optional dependency::

    pip install epinterface[llm]
"""

from __future__ import annotations

from pydantic_ai import Agent

from epinterface.sbem.decision_dag.dag import DecisionDAG
from epinterface.sbem.decision_dag.fields import (
    FieldType,
    SupplementaryContext,
    UserFieldDefinition,
    UserFieldSet,
)
from epinterface.sbem.decision_dag.schema_utils import get_flat_model_schema_description

INSTRUCTIONS_TEMPLATE = """\
You are an expert building energy modeler. Your task is to create a decision DAG \
(directed acyclic graph) that maps user-provided building data fields to the \
parameters of a building energy model (FlatModel).

The DAG you produce will be executed against individual rows of building data. \
Each row contains values for the user's fields. Your DAG must assign values to \
ALL required FlatModel parameters for every possible execution path.

## Key Concepts

- **ConditionNode**: Branches based on evaluating a user field. Branches are \
checked in order; the first match is followed. Always include a default_target_id \
as a fallback.
- **AssignmentNode**: Directly sets FlatModel parameter values. Can chain to \
further nodes via next_node_ids.
- **ComponentRefNode**: References a reusable IntermediateComponent -- a named \
bundle of parameter assignments (e.g. "High Performance Residential Envelope"). \
Use these for common parameter combinations.
- **IntermediateComponent**: A reusable set of FlatModel parameter assignments \
with a descriptive name and explanation.

## Design Guidelines

1. **Handle sparse data**: User fields may be incomplete. Use IS_MISSING / \
IS_NOT_MISSING conditions extensively with sensible defaults.
2. **Use intermediate components**: Group related parameters into named \
components that represent building archetypes or subsystem types. This makes \
the DAG readable and maintainable.
3. **Multiple entry nodes**: Use separate sub-DAGs for orthogonal parameter \
groups (e.g. one for envelope, one for HVAC, one for schedules) rather than \
one monolithic tree.
4. **Regional specificity**: Apply your knowledge of regional building codes, \
construction practices, and climate-appropriate defaults based on the user's \
context.
5. **Data quality awareness**: When a field has low data quality, prefer \
cross-referencing with other fields rather than trusting it directly.
6. **Always provide defaults**: Every execution path must assign all required \
FlatModel parameters. Use sensible defaults for the given region and building stock.
7. **Refinement chains**: Start with broad defaults, then override with more \
specific values as conditions narrow. Later assignments override earlier ones.
8. **Geometry and weather**: Fields like WWR, F2FHeight, NFloors, Width, Depth, \
Rotation, and EPWURI are typically provided directly by the user and don't need \
to be assigned by the DAG, unless the user's field set suggests the DAG should \
infer them.

{flat_model_schema}
"""


def _format_field_definition(field_def: UserFieldDefinition) -> str:
    """Format a single field definition for the user message."""
    lines = [f"### {field_def.name}"]
    lines.append(f"- Type: {field_def.field_type.value}")
    lines.append(f"- Description: {field_def.description}")

    if field_def.data_quality_description:
        lines.append(f"- Data quality: {field_def.data_quality_description}")

    if field_def.field_type == FieldType.CATEGORICAL and field_def.categories:
        lines.append(f"- Categories: {field_def.categories}")
    elif field_def.field_type == FieldType.NUMERIC:
        range_str = f"{field_def.min_value} to {field_def.max_value}"
        if field_def.unit:
            range_str += f" {field_def.unit}"
        lines.append(f"- Range: {range_str}")

    return "\n".join(lines)


def _format_supplementary_context(ctx: SupplementaryContext) -> str:
    """Format a supplementary context document for the user message."""
    return f"### {ctx.title} (format: {ctx.format_hint})\n\n{ctx.content}"


def build_user_message(field_set: UserFieldSet) -> str:
    """Construct the user message from a UserFieldSet.

    Includes field definitions, supplementary context, and
    regional/building stock descriptions.
    """
    sections: list[str] = []

    if field_set.context_description:
        sections.append(f"## Project Context\n\n{field_set.context_description}")

    if field_set.region_description:
        sections.append(f"## Region & Climate\n\n{field_set.region_description}")

    if field_set.building_stock_description:
        sections.append(f"## Building Stock\n\n{field_set.building_stock_description}")

    sections.append("## Available Data Fields\n")
    for field_def in field_set.fields:
        sections.append(_format_field_definition(field_def))

    if field_set.supplementary_context:
        sections.append("## Supplementary Context\n")
        for ctx in field_set.supplementary_context:
            sections.append(_format_supplementary_context(ctx))

    sections.append(
        "## Task\n\n"
        "Based on the above field definitions, context, and supplementary "
        "information, create a DecisionDAG that maps these user data fields "
        "to all required FlatModel parameters. Use intermediate components "
        "for common parameter bundles, handle missing data gracefully, and "
        "apply regionally appropriate defaults."
    )

    return "\n\n".join(sections)


def build_instructions() -> str:
    """Build the full agent instructions including the FlatModel schema."""
    schema_desc = get_flat_model_schema_description()
    return INSTRUCTIONS_TEMPLATE.format(flat_model_schema=schema_desc)


def create_dag_agent(model: str = "openai:gpt-4o") -> Agent[None, DecisionDAG]:
    """Create a Pydantic AI agent configured for DAG generation.

    Args:
        model: The LLM model identifier (e.g. 'openai:gpt-4o',
            'anthropic:claude-sonnet-4-20250514').

    Returns:
        A configured Agent instance with DecisionDAG as the output type.
    """
    return Agent(
        model,
        output_type=DecisionDAG,
        instructions=build_instructions(),
        output_retries=2,
    )


async def generate_dag(
    field_set: UserFieldSet,
    model: str = "openai:gpt-4o",
) -> DecisionDAG:
    """Generate a DecisionDAG from user field definitions using an LLM.

    This is the main entry point for DAG generation. It creates an agent,
    constructs the prompt from the field set, and returns the structured DAG.

    Args:
        field_set: Complete specification of the user's available data and context.
        model: The LLM model identifier.

    Returns:
        A DecisionDAG ready for validation and execution.
    """
    agent = create_dag_agent(model=model)
    user_message = build_user_message(field_set)
    result = await agent.run(user_message)
    return result.output
