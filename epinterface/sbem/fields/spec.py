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
    Building_ID_col: str | None = Field(
        default=None, description="The building ID column name."
    )

    @model_validator(mode="after")
    def check_at_least_one_height_or_num_floors(self):
        """Check that at least one of height or number of floors is provided."""
        if self.Height_col is None and self.Num_Floors_col is None:
            msg = "At least one of height or number of floors must be provided."
            raise ValueError(msg)
        return self

    def make_grid(self, numerical_discretization: int = 10):
        """Make a grid of the fields."""
        import gc

        import numpy as np
        import pandas as pd

        options = []
        option_vals = {}
        for field in self.Fields:
            if isinstance(field, CategoricalFieldSpec):
                options.append(list(range(len(field.Options))))
                option_vals[field.Name] = field.Options
            elif isinstance(field, NumericFieldSpec):
                options.append(list(range(numerical_discretization)))
                option_vals[field.Name] = np.linspace(
                    field.Min, field.Max, numerical_discretization
                )
            else:
                msg = f"Unexpected field type: {type(field)}"
                raise TypeError(msg)
        options = [np.array(opt, dtype=np.int8) for opt in options]

        arrs = np.meshgrid(*options, indexing="ij", copy=False)
        df = pd.DataFrame()
        for arr, field in zip(arrs, self.Fields, strict=True):
            df[field.Name] = arr.ravel()
            del arr
            gc.collect()
        # df = pd.DataFrame(
        #     np.column_stack(arrs), columns=[field.Name for field in self.Fields]
        # )
        return df, option_vals
