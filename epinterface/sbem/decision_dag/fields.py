"""User field definitions for the decision DAG module.

Defines the schema for users to describe their available data fields,
supplementary context, and building stock characteristics that will be
used by an LLM to generate a decision DAG.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator


class FieldType(str, Enum):
    """The type of a user-provided data field."""

    CATEGORICAL = "categorical"
    NUMERIC = "numeric"
    PLAINTEXT = "plaintext"


class UserFieldDefinition(BaseModel):
    """A definition of a single field in the user's data.

    Describes the field's name, type, semantics, and data quality
    so the LLM can make informed decisions about how to use it
    in the decision DAG.
    """

    name: str = Field(description="Column/field name as it appears in the user's data.")
    field_type: FieldType = Field(
        description="Whether this field is categorical, numeric, or free-text."
    )
    description: str = Field(
        description="Plain English description of what this field represents."
    )
    data_quality_description: str = Field(
        default="",
        description="Description of the data quality, completeness, and reliability of this field.",
    )
    categories: list[str] | None = Field(
        default=None,
        description="Allowed category values (required for categorical fields).",
    )
    min_value: float | None = Field(
        default=None,
        description="Minimum value (required for numeric fields).",
    )
    max_value: float | None = Field(
        default=None,
        description="Maximum value (required for numeric fields).",
    )
    unit: str | None = Field(
        default=None,
        description="Unit of measurement for numeric fields (e.g. 'm2K/W', 'years').",
    )

    @model_validator(mode="after")
    def _check_type_specific_fields(self) -> UserFieldDefinition:
        if self.field_type == FieldType.CATEGORICAL and not self.categories:
            msg = f"Field '{self.name}': categorical fields must specify 'categories'."
            raise ValueError(msg)
        if self.field_type == FieldType.NUMERIC:
            if self.min_value is None or self.max_value is None:
                msg = f"Field '{self.name}': numeric fields must specify 'min_value' and 'max_value'."
                raise ValueError(msg)
        return self


class SupplementaryContext(BaseModel):
    """An unstructured knowledge document that provides additional context to the LLM.

    Users can attach any number of these to describe their building stock
    in detail. Content can be plain text, JSON, CSV, markdown, or any other
    text-based format.
    """

    title: str = Field(
        description="Short title for this context document (e.g. 'HVAC System Frequency Distribution')."
    )
    content: str = Field(description="The context content in any text-based format.")
    format_hint: str = Field(
        default="plaintext",
        description="Format of the content: 'plaintext', 'json', 'csv', 'markdown', etc.",
    )


class UserFieldSet(BaseModel):
    """Complete specification of the user's available data and context.

    Combines field definitions with contextual information that helps
    the LLM generate an appropriate decision DAG for the building stock.
    """

    fields: list[UserFieldDefinition] = Field(
        description="Definitions of all data fields available in the user's dataset.",
    )
    context_description: str = Field(
        default="",
        description="Overall project context and goals.",
    )
    region_description: str = Field(
        default="",
        description="Geographic and climate context (e.g. 'Northeast US, IECC Climate Zone 5A').",
    )
    building_stock_description: str = Field(
        default="",
        description="General description of the building stock characteristics.",
    )
    supplementary_context: list[SupplementaryContext] = Field(
        default_factory=list,
        description="Additional unstructured knowledge documents about the building stock.",
    )

    @model_validator(mode="after")
    def _check_unique_field_names(self) -> UserFieldSet:
        names = [f.name for f in self.fields]
        if len(names) != len(set(names)):
            seen: set[str] = set()
            dupes = [n for n in names if n in seen or seen.add(n)]  # type: ignore[func-returns-value]
            msg = f"Duplicate field names: {dupes}"
            raise ValueError(msg)
        return self
