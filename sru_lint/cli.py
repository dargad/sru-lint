from typing import Optional
import logging

from sru_lint.common.ui.snippet import render_snippet
from sru_lint.plugin_manager import PluginManager
from sru_lint.common.logging import setup_logger, get_logger
from sru_lint.common.patch_processor import process_patch_content
import typer

# Global state for CLI options
class GlobalOptions:
    verbose: int = 0
    quiet: bool = False

global_options = GlobalOptions()

def configure_logging():
    """Configure logging based on global options."""
    if global_options.quiet:
        log_level = logging.ERROR
    elif global_options.verbose >= 2:
        log_level = logging.DEBUG
    elif global_options.verbose >= 1:
        log_level = logging.INFO
    else:
        log_level = logging.WARNING
    
    setup_logger(level=log_level)

def verbose_callback(value: int):
    """Callback for verbose option."""
    global_options.verbose = value
    configure_logging()

def quiet_callback(value: bool):
    """Callback for quiet option."""
    global_options.quiet = value
    configure_logging()

app = typer.Typer(
    help="sru-lint - Static analysis tool for Ubuntu SRU patches",
    add_completion=False,
    callback=lambda: None  # Dummy callback to allow global options
)

# Add global options to the main app
@app.callback()
def main(
    verbose: int = typer.Option(
        0, "--verbose", "-v", count=True,
        help="Increase verbosity (-v for INFO, -vv for DEBUG)",
        callback=verbose_callback,
        is_eager=True
    ),
    quiet: bool = typer.Option(
        False, "--quiet", "-q",
        help="Suppress all output except errors",
        callback=quiet_callback,
        is_eager=True
    ),
):
    """Global options for sru-lint."""
    pass


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
    logger = get_logger("cli")
    logger.debug(f"Reading patch from {infile.name}")
    
    # Process comma-separated module names
    expanded_modules = []
    for module_item in modules:
        # Split by comma and strip whitespace
        expanded_modules.extend([m.strip() for m in module_item.split(',')])
    
    # Remove empty items
    expanded_modules = [m for m in expanded_modules if m]
    logger.debug(f"Modules to run: {expanded_modules}")
    
    # Read and process patch
    patch_content = infile.read()
    logger.debug(f"Read {len(patch_content)} characters from input")
    
    # Convert patch to ProcessedFile objects
    processed_files = process_patch_content(patch_content)
    if not processed_files:
        logger.error("No files found in patch or failed to parse patch")
        raise typer.Exit(code=2)
    
    logger.info(f"Converted patch to {len(processed_files)} processed files")

    # Load and filter plugins
    pm = PluginManager()
    plugins = pm.load_plugins()
    logger.debug(f"Loaded {len(plugins)} plugins")
    
    # Filter plugins based on modules
    if "all" not in expanded_modules:
        # Filter plugins by their symbolic names
        filtered_plugins = [p for p in plugins if p.__symbolic_name__ in expanded_modules]
        if not filtered_plugins:
            logger.warning(f"No plugins found matching the specified modules: {', '.join(expanded_modules)}")
            typer.echo("Available modules:")
            for plugin in plugins:
                typer.echo(f"- {plugin.__symbolic_name__}")
            return
        plugins = filtered_plugins
        logger.info(f"Filtered to {len(plugins)} plugins: {[p.__symbolic_name__ for p in plugins]}")
    
    logger.info(f"Running {len(plugins)} plugins")
    
    # Run plugins on processed files
    feedback = []
    for plugin in plugins:
        logger.debug(f"Running plugin: {plugin.__symbolic_name__}")
        plugin_feedback = plugin.process(processed_files)
        feedback.extend(plugin_feedback)
        logger.debug(f"Plugin {plugin.__symbolic_name__} generated {len(plugin_feedback)} feedback items")
    
    # Count feedback by severity
    error_count = sum(1 for item in feedback if item.severity.value == "error")
    warning_count = sum(1 for item in feedback if item.severity.value == "warning")
    info_count = sum(1 for item in feedback if item.severity.value == "info")
    
    logger.info(f"Collected {len(feedback)} feedback items: {error_count} errors, {warning_count} warnings, {info_count} info")
    
    # Print feedback summary (always shown unless quiet mode)
    if not global_options.quiet:
        if feedback:
            typer.echo("\nFeedback:")
            for item in feedback:
                # Format output based on severity
                severity_color = {
                    "error": typer.colors.RED,
                    "warning": typer.colors.YELLOW,
                    "info": typer.colors.BLUE,
                }.get(item.severity.value, None)
                
                typer.secho(f"- {item.message} (Severity: {item.severity.value})", fg=severity_color)

                print(f"Item span: {item.span.start_line}-{item.span.end_line} in {item.span.path}")
                render_snippet(
                    code="\n".join([line.content for line in item.span.lines_added]),
                    title=f"File: {item.span.path}",
                    highlight_lines=[item.span.start_line] if item.span.start_line >= 0 else [],
                    annotations={
                        item.span.start_line: [(item.message, item.span.start_col if item.span.start_col >= 0 else 0)]
                    }
                )
        else:
            typer.secho("✅ No issues found", fg=typer.colors.GREEN)
    
    # Exit with error code if there are any errors
    if error_count > 0:
        logger.error(f"Found {error_count} error(s)")
        raise typer.Exit(code=1)


@app.command()
def plugins():
    """
    List all available plugins.
    """
    logger = get_logger("cli")
    
    typer.echo("Available plugins:")
    
    pm = PluginManager()
    plugins = pm.load_plugins()
    logger.debug(f"Loaded {len(plugins)} plugins")
    
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
        logger.debug(f"Plugin {plugin_name}: {plugin.__class__.__module__}.{plugin.__class__.__name__}")


@app.command()
def inspect():
    """
    Inspect the patch and generate a HTML report.
    """
    logger = get_logger("cli")
    logger.info("Starting patch inspection")
    typer.echo("Inspecting code...")
    # TODO: Implement inspection logic


if __name__ == "__main__":
    app()