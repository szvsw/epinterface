"""CLI for epinterface.

Because we use prisma, we need to generate the client before we can use it.  However, when epinterface is installed by another package, e.g. via pip or poetry,
the prisma client is not yet generated since it does not get committed to version control.  If the installing context wanted to run prisma generate however,
it would not be able to find the prisma schema file because it exists inside *this* package, at epinterface/sbem/prisma/schema.prisma.

As such, we need to provide a way to generate the prisma client by passing the --schema flag to prisma generate.
"""

import shutil
import subprocess
import sys
from importlib.resources import files
from pathlib import Path
from typing import Literal

import click


@click.group()
def cli():
    """CLI for epinterface."""
    pass


# Create a group for prisma-related commands
@cli.group(help="Commands related to Prisma ORM for epinterface.")
def prisma():
    """Commands for working with Prisma ORM for epinterface."""
    pass


@prisma.command(help="Generate the prisma client for epinterface.")
def generate():
    """Generate the prisma client."""
    # check the install location of epinterface
    epinterface_dir = files("epinterface")
    path_to_schema = epinterface_dir / "sbem" / "prisma" / "schema.prisma"
    path_to_partials = epinterface_dir / "sbem" / "prisma" / "partial_types.py"

    # Try to find the prisma executable
    accepted_commands = ("prisma", "prisma.exe")
    prisma_cmd = shutil.which("prisma")
    if not prisma_cmd or not prisma_cmd.lower().endswith(accepted_commands):
        click.echo("Error: Invalid prisma executable path", err=True)
        sys.exit(1)

    try:
        subprocess.run(  # noqa: S603
            [
                prisma_cmd,
                "py",
                "generate",
                "--schema",
                str(path_to_schema),
                "--partials",
                str(path_to_partials),
            ],
            check=True,
            text=True,
            capture_output=True,
            shell=False,
        )
        click.echo("Prisma client generated successfully.")
    except subprocess.CalledProcessError as e:
        click.echo(f"Error generating prisma client: {e}", err=True)
        if e.stderr:
            click.echo(e.stderr, err=True)
        sys.exit(1)


@prisma.command(
    help="Return the path to the prisma schema file. "
    "This is useful for passing the `--schema` flag to `prisma <subcommand>`."
)
def schemapath():
    """Return the path to the prisma schema file."""
    epinterface_dir = files("epinterface")
    path_to_schema = epinterface_dir / "sbem" / "prisma" / "schema.prisma"
    click.echo(str(path_to_schema))


@prisma.command(
    help="Return the path to the prisma partials file. "
    "This is useful for passing the `--partials` flag to `prisma <subcommand>`."
)
def partials_path():
    """Return the path to the prisma partials file."""
    epinterface_dir = files("epinterface")
    path_to_partials = epinterface_dir / "sbem" / "prisma" / "partial_types.py"
    click.echo(str(path_to_partials))


# Create a group for database-related commands
@cli.group(help="Commands for working with epinterface databases.")
def db():
    """Commands for working with epinterface databases."""
    pass


@db.command(help="Create a new database file at the given path.")
@click.option(
    "--path",
    type=click.Path(
        exists=False,
        path_type=Path,
    ),
    default="components.db",
    prompt="Enter the path to the database file.",
)
@click.option(
    "--if-exists",
    type=click.Choice(["raise", "overwrite", "ignore"]),
    default="raise",
    help="What to do if the database file already exists. 'raise' will raise an error, "
    "'overwrite' will create a new empty database, 'migrate' will preserve the data "
    "and apply any schema changes, 'ignore' will use the existing database as-is.",
    prompt="What to do if the database file already exists?",
)
def make(path: Path, if_exists: Literal["raise", "overwrite", "migrate", "ignore"]):
    """Create a new database file at the given path."""
    from epinterface.sbem.prisma.client import PrismaSettings

    if path.suffix != ".db":
        click.echo("Error: The database file should have a .db suffix.", err=True)
        sys.exit(1)

    try:
        PrismaSettings.New(database_path=path, if_exists=if_exists, auto_register=False)
    except FileExistsError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    click.echo(f"Database available at {path}.")


@db.command(help="Convert an excel file to a database file.")
@click.option(
    "--excel-path",
    type=click.Path(
        exists=True,
        path_type=Path,
    ),
    prompt="Enter the path to the excel file to convert (should have a .xlsx suffix).",
    help="The excel file should be a template excel file.  See https://github.com/mitsustainabledesignlab/epinterface for more info.",
)
@click.option(
    "--db-path",
    type=click.Path(
        exists=False,
        path_type=Path,
    ),
    default="components.db",
    prompt="Enter the path to the database file to create (should have a .db suffix).",
    help="The database file will be created at the given path.  If the file already exists, an error will be raised.",
)
def convert(excel_path: Path, db_path: Path):
    """Convert an excel file to a database file."""
    from epinterface.sbem.interface import add_excel_to_db
    from epinterface.sbem.prisma.client import PrismaSettings

    if excel_path.suffix != ".xlsx":
        msg = "Error: The excel file should have a .xlsx suffix."
        click.echo(msg, err=True)
        sys.exit(1)
    if db_path.suffix != ".db":
        msg = "Error: The database file should have a .db suffix."
        click.echo(msg, err=True)
        sys.exit(1)

    settings = PrismaSettings.New(
        database_path=db_path, if_exists="raise", auto_register=True
    )
    try:
        with settings.db:
            add_excel_to_db(excel_path, settings.db, erase_db=True)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    click.echo(f"Database available at {db_path}.")


# Create a group for component-related commands
@cli.group(help="Commands for working with components")
def components():
    """Commands for working with components."""
    pass


@components.command(help="Create a yaml template file for entering component maps.")
@click.option(
    "--path",
    type=click.Path(
        exists=False,
        path_type=Path,
    ),
    default="component_map.yaml",
    prompt="Enter the path to the yaml template file for entering component maps.",
)
def template(path: Path):
    """Create a yaml template file for entering component maps."""
    from epinterface.sbem.components.composer import (
        construct_composer_model,
        construct_graph,
    )
    from epinterface.sbem.components.zones import ZoneComponent

    g = construct_graph(ZoneComponent)
    model = construct_composer_model(g, ZoneComponent, use_children=False)
    template_yaml = model.create_data_entry_template()
    with open(path, "w") as f:
        f.write(template_yaml)
