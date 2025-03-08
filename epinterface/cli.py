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

import click


@click.group()
def cli():
    """CLI for epinterface."""
    pass


@cli.command(help="Generate the prisma client for epinterface.")
def generate():
    """Generate the prisma client."""
    # check the install location of epinterface
    epinterface_dir = files("epinterface")
    path_to_schema = epinterface_dir / "sbem" / "prisma" / "schema.prisma"

    # Try to find the prisma executable
    accepted_commands = ("prisma", "prisma.exe")
    prisma_cmd = shutil.which("prisma")
    if not prisma_cmd or not prisma_cmd.lower().endswith(accepted_commands):
        click.echo("Error: Invalid prisma executable path", err=True)
        sys.exit(1)

    try:
        subprocess.run(  # noqa: S603
            [prisma_cmd, "generate", "--schema", str(path_to_schema)],
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


@cli.command(
    help="Return the path to the prisma schema file. "
    "This is useful for passing the `--schema` flag to `prisma <subcommand>`."
)
def schemapath():
    """Return the path to the prisma schema file."""
    epinterface_dir = files("epinterface")
    path_to_schema = epinterface_dir / "sbem" / "prisma" / "schema.prisma"
    click.echo(str(path_to_schema))
