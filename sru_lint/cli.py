from typing import Optional

import unidiff
from sru_lint.plugin_manager import PluginManager
import typer

app = typer.Typer(help="punch - a CLI tool for managing your tasks")

@app.command()
def check(
    infile: typer.FileText = typer.Argument(
        "-", metavar="FILE", help="File to read, or '-' for stdin"
    ),
    modules: Optional[list[str]] = typer.Option(
        ["all"], "--modules", "-m", 
        help="Only run the specified module(s). Default is 'all'. Can be specified as comma-separated list or multiple times"
    ),
):
    """
    Run the linter on the specified patch.
    """
    # Process comma-separated module names
    expanded_modules = []
    for module_item in modules:
        # Split by comma and strip whitespace
        expanded_modules.extend([m.strip() for m in module_item.split(',')])
    
    # Remove empty items
    expanded_modules = [m for m in expanded_modules if m]
    
    patchset = unidiff.PatchSet(infile.read())

    pm = PluginManager()
    plugins = pm.load_plugins()
    
    # Filter plugins based on modules
    if "all" not in expanded_modules:
        # Filter plugins by their symbolic names
        filtered_plugins = [p for p in plugins if p.__symbolic_name__ in expanded_modules]
        if not filtered_plugins:
            typer.echo(f"Warning: No plugins found matching the specified modules: {', '.join(expanded_modules)}")
            typer.echo("Available modules:")
            for plugin in plugins:
                typer.echo(f"- {plugin.__symbolic_name__}")
            return
        plugins = filtered_plugins
    
    feedback = []
    for plugin in plugins:
        feedback.extend(plugin.process(patchset))
    
    print(f"Collected {len(feedback)} feedback items from {len(plugins)} plugin(s).")


@app.command()
def plugins():
    """
    List all available plugins.
    """
    typer.echo("Available plugins:")
    
    pm = PluginManager()
    plugins = pm.load_plugins()
    
    if not plugins:
        typer.echo("No plugins found.")
        return
    
    # Calculate the maximum length of plugin names for alignment
    max_name_length = max(len(plugin.__symbolic_name__) for plugin in plugins)
    
    for plugin in plugins:
        # Get the class name
        plugin_name = plugin.__symbolic_name__
        # Get the docstring (description)
        plugin_description = plugin.__class__.__doc__ or "No description available"
        # Clean up the description (remove leading/trailing whitespace and newlines)
        plugin_description = " ".join(plugin_description.split())
        # Print formatted output with aligned descriptions
        typer.echo(f"- {plugin_name:<{max_name_length}} : {plugin_description}")


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