"""Common classes and mixins for the SBEM library."""

from typing import Annotated

from pydantic import BaseModel, BeforeValidator, Field, field_validator

from epinterface.sbem.annotations import (
    nan_to_none_or_str,
    str_to_bool,
    str_to_float_list,
)


def _ascii_safe(s: str) -> str:
    """Return an ascii-only string suitable for idf names."""
    return s.encode("ascii", "ignore").decode("ascii")


class NamedObject(BaseModel):
    """A Named object (with a name field)."""

    Name: str = Field(..., title="Name of the object used in referencing.")

    @field_validator("Name", mode="before")
    @classmethod
    def sanitize_name(cls, v: str) -> str:
        """Sanitize name to ascii-only, replacing spaces and commas with underscores."""
        if not isinstance(v, str):
            return v
        sanitized = _ascii_safe(v).replace(" ", "_").replace(",", "_")
        return sanitized

    # TODO: this is potentially a confusing footgun, but it's probably necessary.
    @property
    def safe_name(self) -> str:
        """Get the safe name of the object (same as Name after validation)."""
        return self.Name


NanStr = Annotated[str | None, BeforeValidator(nan_to_none_or_str)]
BoolStr = Annotated[bool, BeforeValidator(str_to_bool)]
FloatListStr = Annotated[list[float], BeforeValidator(str_to_float_list)]


# TODO: Make this at the library level not the row level?
class MetadataMixin(BaseModel):
    """Metadata for a SBEM template table object."""

    Category: NanStr | None = Field(default=None, title="Category of the object")
    Comment: NanStr | None = Field(default=None, title="Comment on the object")
    DataSource: NanStr | None = Field(default=None, title="Data source of the object")
    Version: NanStr | None = Field(default=None, title="Version of the object")
