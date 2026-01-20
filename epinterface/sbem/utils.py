"""Utility functions for working with SBEMs."""

from pathlib import Path
from typing import Any, cast

import yaml
from tqdm.autonotebook import tqdm

from epinterface.sbem.components.composer import (
    construct_composer_model,
    construct_graph,
)
from epinterface.sbem.components.zones import ZoneComponent
from epinterface.sbem.fields.spec import SemanticModelFields
from epinterface.sbem.prisma.client import PrismaSettings


class ModelsNotConstructableError(Exception):
    """An error raised when the models are not constructable."""

    def __init__(self, failing_contexts: list[dict[str, Any]]):
        """Initialize the error."""
        self.failing_contexts = failing_contexts
        printable_contexts = failing_contexts[: min(10, len(failing_contexts))]
        msg = "The following contexts failed to resolve to a valid zone component:\n"
        msg += "\n\n"
        msg += yaml.dump(printable_contexts, indent=2, sort_keys=False)
        super().__init__(msg)


def check_model_existence(
    component_map_path: Path,
    semantic_fields_path: Path,
    db_path: Path,
    max_tests: int = 100,
    raise_on_error: bool = False,
) -> None:
    """Check if all semantic field combinations resolve to a valid zone component (up to some sampling limit).

    This will create a complete grid of all semantic field combos, and then check that
    some subsample of them resolve.  Although the complete grid might have some
    curse of dimensionality issues, as each component map selector probably only
    has 3-5 fields, a grid size of 100-500 is typically sufficient since
    the factorization of different components is independent.

    Args:
        component_map_path: Path to the component map file.
        semantic_fields_path: Path to the semantic fields file.
        db_path: Path to the database file.
        max_tests: Maximum number of tests to run.
        raise_on_error: Whether to raise an error if any tests fail.
    """
    with open(semantic_fields_path) as f:
        semantic_fields_yaml = yaml.safe_load(f)
    model = SemanticModelFields.model_validate(semantic_fields_yaml)

    g = construct_graph(ZoneComponent)
    SelectorModel = construct_composer_model(
        g,
        ZoneComponent,
        use_children=False,
    )

    with open(component_map_path) as f:
        component_map_yaml = yaml.safe_load(f)

    # checks that the component is valid
    selector = SelectorModel.model_validate(component_map_yaml)

    settings = PrismaSettings.New(
        database_path=Path(db_path), if_exists="ignore", auto_register=False
    )
    db = settings.db

    grid, field_vals = model.make_grid(numerical_discretization=10)
    grid = grid.sample(min(max_tests, len(grid)))

    # Checks that things that should be in the db are in the db
    failing_contexts = []
    with db:
        for _ix, row in tqdm(
            grid.iterrows(),
            total=len(grid),
            desc="Checking semantic field/component lib compatibility.",
        ):
            context = row.to_dict()
            for field_name, field_val in field_vals.items():
                context[field_name] = field_val[context[field_name]]
            try:
                _component = cast(
                    ZoneComponent, selector.get_component(context=context, db=db)
                )
            except Exception as e:
                print(f"\nError: {e}, context: {context}\n")
                failing_contexts.append(context)
    if raise_on_error and failing_contexts:
        raise ModelsNotConstructableError(failing_contexts)
