"""Visualize a DecisionDAG as a Markdown document with Mermaid diagrams.

Generates a readable report including a graph diagram, component
inventory, validation results, and coverage analysis.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from epinterface.sbem.decision_dag.dag import (
    AssignmentNode,
    ComponentRefNode,
    ConditionNode,
    DecisionDAG,
)
from epinterface.sbem.decision_dag.fields import UserFieldSet
from epinterface.sbem.decision_dag.schema_utils import _FIELD_GROUPS
from epinterface.sbem.decision_dag.validation import (
    _collect_reachable_assignments,
    validate_dag_structure,
)


def _sanitize_mermaid_id(node_id: str) -> str:
    """Make a node ID safe for mermaid (no hyphens, dots, etc.)."""
    return node_id.replace("-", "_").replace(".", "_").replace(" ", "_")


def _escape_mermaid_label(text: str) -> str:
    """Escape a label string for safe use in mermaid node definitions."""
    return text.replace('"', "'").replace("\n", " ")


def _truncate(text: str, max_len: int = 50) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def _build_mermaid_diagram(dag: DecisionDAG) -> str:
    """Build a mermaid flowchart string from a DecisionDAG."""
    lines: list[str] = ["flowchart TD"]

    entry_set = set(dag.entry_node_ids)
    comp_map = {c.id: c for c in dag.components}

    for node in dag.nodes:
        sid = _sanitize_mermaid_id(node.id)
        prefix = "ENTRY: " if node.id in entry_set else ""

        if isinstance(node, ConditionNode):
            label = _escape_mermaid_label(f"{prefix}{node.description}")
            lines.append(f"    {sid}{{{{{label}}}}}")

            for i, branch in enumerate(node.branches):
                tsid = _sanitize_mermaid_id(branch.target_node_id)
                cond = branch.condition
                if cond.value is not None:
                    edge_label = f"{cond.field} {cond.operator.value} {_truncate(str(cond.value), 30)}"
                else:
                    edge_label = f"{cond.field} {cond.operator.value}"
                edge_label = _escape_mermaid_label(edge_label)
                lines.append(f'    {sid} -->|"{edge_label}"| {tsid}')

            if node.default_target_id:
                dsid = _sanitize_mermaid_id(node.default_target_id)
                lines.append(f'    {sid} -->|"default"| {dsid}')

        elif isinstance(node, AssignmentNode):
            n_fields = len(node.assignments)
            label = _escape_mermaid_label(
                f"{prefix}{node.description} ({n_fields} fields)"
            )
            lines.append(f'    {sid}["{label}"]')

            for nid in node.next_node_ids:
                lines.append(f"    {sid} --> {_sanitize_mermaid_id(nid)}")

        elif isinstance(node, ComponentRefNode):
            comp = comp_map.get(node.component_id)
            comp_name = comp.name if comp else node.component_id
            n_fields = len(comp.assignments) if comp else "?"
            label = _escape_mermaid_label(f"{prefix}{comp_name} ({n_fields} fields)")
            lines.append(f'    {sid}(["{label}"])')

            for nid in node.next_node_ids:
                lines.append(f"    {sid} --> {_sanitize_mermaid_id(nid)}")

    return "\n".join(lines)


def _build_component_table(dag: DecisionDAG) -> str:
    """Build a markdown table summarizing intermediate components."""
    lines: list[str] = [
        "| ID | Name | Fields | Description |",
        "|---|---|---|---|",
    ]
    for comp in dag.components:
        field_list = ", ".join(f"`{k}`" for k in sorted(comp.assignments.keys()))
        desc = _truncate(comp.description, 80)
        lines.append(f"| `{comp.id}` | {comp.name} | {field_list} | {desc} |")
    return "\n".join(lines)


def _build_component_details(dag: DecisionDAG) -> str:
    """Build detailed component assignment listings."""
    sections: list[str] = []
    for comp in dag.components:
        lines = [f"#### {comp.name} (`{comp.id}`)", "", comp.description, ""]
        for k, v in comp.assignments.items():
            lines.append(f"- `{k}` = `{v}`")
        lines.append("")
        sections.append("\n".join(lines))
    return "\n".join(sections)


def _build_coverage_section(dag: DecisionDAG) -> str:
    """Build a coverage analysis section showing which groups are assigned."""
    reachable = _collect_reachable_assignments(dag)
    all_assigned: set[str] = set()
    for fields in reachable.values():
        all_assigned.update(fields)

    lines: list[str] = []
    for group_name, field_names in _FIELD_GROUPS.items():
        covered = [f for f in field_names if f in all_assigned]
        missing = [f for f in field_names if f not in all_assigned]
        total = len(field_names)
        n_covered = len(covered)

        if n_covered == total:
            status = "FULL"
        elif n_covered == 0:
            status = "NONE"
        else:
            status = "PARTIAL"

        lines.append(f"- **{group_name}**: {n_covered}/{total} ({status})")
        if missing and status != "NONE":
            lines.append(f"  - Missing: {', '.join(f'`{f}`' for f in missing)}")

    return "\n".join(lines)


def _build_validation_section(dag: DecisionDAG, field_set: UserFieldSet | None) -> str:
    """Build a validation results section."""
    errors = validate_dag_structure(
        dag, field_set=field_set, require_full_coverage=True
    )
    if not errors:
        return "All structural validation checks passed."

    lines = [f"Found **{len(errors)}** issue(s):", ""]
    for e in errors:
        lines.append(f"- {e}")
    return "\n".join(lines)


def _build_node_inventory(dag: DecisionDAG) -> str:
    """Build a summary of all nodes."""
    entry_set = set(dag.entry_node_ids)
    lines: list[str] = [
        "| ID | Type | Description | Entry? |",
        "|---|---|---|---|",
    ]
    for node in dag.nodes:
        ntype = node.node_type
        desc = _truncate(node.description, 60)
        entry = "yes" if node.id in entry_set else ""
        lines.append(f"| `{node.id}` | {ntype} | {desc} | {entry} |")
    return "\n".join(lines)


def visualize_dag(
    dag: DecisionDAG,
    field_set: UserFieldSet | None = None,
) -> str:
    """Generate a Markdown document visualizing a DecisionDAG.

    Args:
        dag: The decision DAG to visualize.
        field_set: Optional user field set for validation context.

    Returns:
        A complete Markdown string with mermaid diagrams and analysis.
    """
    sections: list[str] = []

    sections.append("# Decision DAG Visualization")
    sections.append("")
    sections.append(f"> {dag.description}")
    sections.append("")

    sections.append("## Summary")
    sections.append("")
    sections.append(f"- **Components**: {len(dag.components)}")
    sections.append(f"- **Nodes**: {len(dag.nodes)}")
    n_condition = sum(1 for n in dag.nodes if isinstance(n, ConditionNode))
    n_assign = sum(1 for n in dag.nodes if isinstance(n, AssignmentNode))
    n_ref = sum(1 for n in dag.nodes if isinstance(n, ComponentRefNode))
    sections.append(
        f"  - Condition: {n_condition}, Assignment: {n_assign}, ComponentRef: {n_ref}"
    )
    sections.append(
        f"- **Entry points**: {len(dag.entry_node_ids)} ({', '.join(f'`{e}`' for e in dag.entry_node_ids)})"
    )
    sections.append("")

    sections.append("## Graph")
    sections.append("")
    sections.append("```mermaid")
    sections.append(_build_mermaid_diagram(dag))
    sections.append("```")
    sections.append("")

    sections.append("## Node Inventory")
    sections.append("")
    sections.append(_build_node_inventory(dag))
    sections.append("")

    sections.append("## Intermediate Components")
    sections.append("")
    sections.append(_build_component_table(dag))
    sections.append("")

    sections.append("### Component Details")
    sections.append("")
    sections.append(_build_component_details(dag))

    sections.append("## Parameter Coverage")
    sections.append("")
    sections.append(_build_coverage_section(dag))
    sections.append("")

    sections.append("## Validation")
    sections.append("")
    sections.append(_build_validation_section(dag, field_set))
    sections.append("")

    if field_set is not None:
        sections.append("## User Fields")
        sections.append("")
        for f in field_set.fields:
            sections.append(f"- **{f.name}** ({f.field_type.value}): {f.description}")
            if f.data_quality_description:
                sections.append(f"  - Data quality: {f.data_quality_description}")
        sections.append("")

    return "\n".join(sections)


def visualize_dag_from_files(
    dag_path: str | Path,
    field_set_path: str | Path | None = None,
    output_path: str | Path | None = None,
) -> str:
    """Load a DAG and optional field set from files, generate visualization.

    Args:
        dag_path: Path to a DecisionDAG JSON file.
        field_set_path: Optional path to a UserFieldSet YAML file.
        output_path: Optional path to write the output Markdown.
            If None, defaults to the same directory as dag_path
            with the name ``visualized_dag.md``.

    Returns:
        The generated Markdown string.
    """
    dag_path = Path(dag_path)
    dag = DecisionDAG.model_validate_json(dag_path.read_text())

    field_set: UserFieldSet | None = None
    if field_set_path is not None:
        field_set_path = Path(field_set_path)
        raw = yaml.safe_load(field_set_path.read_text())
        field_set = UserFieldSet.model_validate(raw)

    md = visualize_dag(dag, field_set=field_set)

    if output_path is None:
        output_path = dag_path.parent / "visualized_dag.md"
    else:
        output_path = Path(output_path)

    output_path.write_text(md, encoding="utf-8")
    return md
