"""Tests for decision_dag.fields module."""

import pytest
from pydantic import ValidationError

from epinterface.sbem.decision_dag.fields import (
    FieldType,
    SupplementaryContext,
    UserFieldDefinition,
    UserFieldSet,
)


class TestUserFieldDefinition:
    """Tests for UserFieldDefinition validation."""

    def test_categorical_field_valid(self):
        field = UserFieldDefinition(
            name="building_type",
            field_type=FieldType.CATEGORICAL,
            description="Type of building",
            categories=["residential", "commercial", "industrial"],
        )
        assert field.categories == ["residential", "commercial", "industrial"]

    def test_categorical_field_missing_categories(self):
        with pytest.raises(ValidationError, match="categorical fields must specify"):
            UserFieldDefinition(
                name="building_type",
                field_type=FieldType.CATEGORICAL,
                description="Type of building",
            )

    def test_numeric_field_valid(self):
        field = UserFieldDefinition(
            name="year_built",
            field_type=FieldType.NUMERIC,
            description="Year the building was constructed",
            min_value=1800,
            max_value=2025,
            unit="year",
        )
        assert field.min_value == 1800
        assert field.max_value == 2025

    def test_numeric_field_missing_bounds(self):
        with pytest.raises(ValidationError, match="numeric fields must specify"):
            UserFieldDefinition(
                name="year_built",
                field_type=FieldType.NUMERIC,
                description="Year the building was constructed",
            )

    def test_numeric_field_missing_max(self):
        with pytest.raises(ValidationError, match="numeric fields must specify"):
            UserFieldDefinition(
                name="year_built",
                field_type=FieldType.NUMERIC,
                description="Year the building was constructed",
                min_value=1800,
            )

    def test_plaintext_field_valid(self):
        field = UserFieldDefinition(
            name="notes",
            field_type=FieldType.PLAINTEXT,
            description="Free-text notes about the building",
        )
        assert field.field_type == FieldType.PLAINTEXT
        assert field.categories is None
        assert field.min_value is None

    def test_data_quality_description(self):
        field = UserFieldDefinition(
            name="wall_r_value",
            field_type=FieldType.NUMERIC,
            description="Wall R-value",
            data_quality_description="Self-reported, unreliable for pre-1980 buildings",
            min_value=0,
            max_value=40,
            unit="m2K/W",
        )
        assert (
            field.data_quality_description
            == "Self-reported, unreliable for pre-1980 buildings"
        )


class TestSupplementaryContext:
    """Tests for SupplementaryContext."""

    def test_plaintext_context(self):
        ctx = SupplementaryContext(
            title="Regional construction practices",
            content="Pre-1940 buildings have double-wythe brick walls.",
        )
        assert ctx.format_hint == "plaintext"

    def test_json_context(self):
        ctx = SupplementaryContext(
            title="HVAC distribution",
            content='{"gas_furnace": 0.6, "heat_pump": 0.3, "electric_resistance": 0.1}',
            format_hint="json",
        )
        assert ctx.format_hint == "json"


class TestUserFieldSet:
    """Tests for UserFieldSet validation."""

    def test_valid_field_set(self):
        fs = UserFieldSet(
            fields=[
                UserFieldDefinition(
                    name="building_type",
                    field_type=FieldType.CATEGORICAL,
                    description="Type of building",
                    categories=["residential", "commercial"],
                ),
                UserFieldDefinition(
                    name="year_built",
                    field_type=FieldType.NUMERIC,
                    description="Construction year",
                    min_value=1800,
                    max_value=2025,
                ),
            ],
            context_description="Energy audit project",
            region_description="Boston, MA, Climate Zone 5A",
        )
        assert len(fs.fields) == 2

    def test_duplicate_field_names_rejected(self):
        with pytest.raises(ValidationError, match="Duplicate field names"):
            UserFieldSet(
                fields=[
                    UserFieldDefinition(
                        name="building_type",
                        field_type=FieldType.CATEGORICAL,
                        description="Type A",
                        categories=["a"],
                    ),
                    UserFieldDefinition(
                        name="building_type",
                        field_type=FieldType.CATEGORICAL,
                        description="Type B",
                        categories=["b"],
                    ),
                ],
            )

    def test_supplementary_context(self):
        fs = UserFieldSet(
            fields=[
                UserFieldDefinition(
                    name="typology",
                    field_type=FieldType.CATEGORICAL,
                    description="Building typology",
                    categories=["SF", "MF"],
                ),
            ],
            supplementary_context=[
                SupplementaryContext(
                    title="Wall types",
                    content="Most SF homes are wood-frame, MF are masonry.",
                ),
            ],
        )
        assert len(fs.supplementary_context) == 1

    def test_empty_fields_allowed(self):
        fs = UserFieldSet(fields=[])
        assert len(fs.fields) == 0

    def test_serialization_roundtrip(self):
        fs = UserFieldSet(
            fields=[
                UserFieldDefinition(
                    name="income",
                    field_type=FieldType.NUMERIC,
                    description="Household income",
                    min_value=0,
                    max_value=500000,
                    unit="USD",
                ),
            ],
            region_description="Northeast US",
            supplementary_context=[
                SupplementaryContext(
                    title="Income data",
                    content="Median income is $65,000",
                ),
            ],
        )
        data = fs.model_dump()
        fs2 = UserFieldSet.model_validate(data)
        assert fs2.fields[0].name == "income"
        assert len(fs2.supplementary_context) == 1
