from typing import Optional

import unidiff
from sru_lint.plugin_manager import PluginManager
import typer

app = typer.Typer(help="punch - a CLI tool for managing your tasks")

@app.command()
def check(
    infile: typer.FileText = typer.Argument(
        "-", metavar="FILE", help="File to read, or '-' for stdin"
    )
):
    """
    Run the linter on the specified patch.
    """

    patchset = unidiff.PatchSet(infile.read())

    pm = PluginManager()
    plugins = pm.load_plugins()

    for plugin in plugins:
        plugin.process(patchset)


@app.command()
def inspect():
    """
    Inspect the patch and generate a HTML report.
    """
    typer.echo("Inspecting code...")

@app.command()
def help(
    ctx: typer.Context,
    command: Optional[list[str]] = typer.Argument(
        None,
        help="Show help for this app or a subcommand path, e.g. `help greet` or `help tools sub`.",
    )
):
    """Show the same help text as `--help`."""
    # `ctx` here is the context of the `help` command. Its parent is the app context.
    if not command:
        # Root help (same as `myprog --help`)
        typer.echo(ctx.parent.get_help())
        raise typer.Exit()

    # Resolve a nested command path (e.g. ["tools", "build"])
    cmd = ctx.parent.command  # start at the app (click.MultiCommand)
    target = None
    info_parts: list[str] = []

    for name in command:
        info_parts.append(name)
        target = cmd.get_command(ctx.parent, name)  # click API
        if target is None:
            typer.secho(f"Unknown command: {' '.join(info_parts)}", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=2)
        cmd = target  # descend

    # Show help for the resolved command
    with typer.Context(target, info_name=" ".join(info_parts), parent=ctx.parent) as subctx:
        typer.echo(target.get_help(subctx))
    raise typer.Exit()

if __name__ == "__main__":
    app()