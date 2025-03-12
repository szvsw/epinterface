"""A module for specifying the fields in the GIS data."""

from typing import Generic, TypeVar

from pydantic import BaseModel, Field, model_validator

NumericOrString = TypeVar("NumericOrString", float, str, int)
Numeric = TypeVar("Numeric", float, int)


class FieldSpec(BaseModel):
    """A specification for a field in the GIS data."""

    Name: str = Field(
        ...,
        description="The name of the field (e.g. 'Typology') as it appears in the GIS data.",
    )


class CategoricalFieldSpec(FieldSpec, Generic[NumericOrString]):
    """A specification for a categorical field in the GIS data."""

    Options: list[NumericOrString] = Field(
        ..., description="The list of values that the field can take."
    )


class NumericFieldSpec(FieldSpec, Generic[Numeric]):
    """A specification for a numeric field in the GIS data."""

    Min: Numeric = Field(..., description="The minimum value that the field can take.")
    Max: Numeric = Field(..., description="The maximum value that the field can take.")


class SemanticModelFields(BaseModel):
    """A specification for the semantic fields in the GIS data."""

    Name: str = Field(..., description="The name of the model.")
    Fields: list[NumericFieldSpec | CategoricalFieldSpec] = Field(
        ..., description="The fields that make up the model."
    )
    WWR_col: str | None = Field(
        default=None, description="The window-to-wall ratio [0-1] column name."
    )
    Height_col: str | None = Field(
        default=None, description="The height [m] column name."
    )
    Num_Floors_col: str | None = Field(
        default=None, description="The number of floors column name [int]."
    )
    GFA_col: str | None = Field(
        default=None, description="The gross floor area column name [m2]."
    )

    @model_validator(mode="after")
    def check_at_least_one_height_or_num_floors(self):
        """Check that at least one of height or number of floors is provided."""
        if self.Height_col is None and self.Num_Floors_col is None:
            msg = "At least one of height or number of floors must be provided."
            raise ValueError(msg)
        return self


if __name__ == "__main__":
    typology_coarse_field = CategoricalFieldSpec(
        Name="Typology_Coarse",
        Options=["Residential", "Commercial"],
    )
    typology_fine_field = CategoricalFieldSpec(
        Name="Typology_Fine",
        Options=["Single_Family", "Multi_Family", "Retail", "Office", "Supermarket"],
    )
    age_bracket_field = CategoricalFieldSpec(
        Name="Age_Bracket",
        Options=["pre-1975", "1975-2003", "2003-2025", "post-2025"],
    )
    on_campus_field = CategoricalFieldSpec(
        Name="On_Campus",
        Options=["on_campus", "off_campus"],
    )
    model = SemanticModelFields(
        Name="Los Angeles Model",
        Fields=[
            typology_coarse_field,
            typology_fine_field,
            age_bracket_field,
            on_campus_field,
        ],
        Height_col="Height",
    )

    import yaml

    print(yaml.safe_dump(model.model_dump()))
