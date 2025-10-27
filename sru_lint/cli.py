from typing import Optional, List, Tuple
import logging
import json
import time

from sru_lint.common.errors import ErrorEnumEncoder
from sru_lint.common.ui.snippet import render_snippet
from sru_lint.plugin_manager import PluginManager
from sru_lint.common.logging import setup_logger, get_logger
from sru_lint.common.patch_processor import process_patch_content
from sru_lint.common.feedback import FeedbackItem
import typer
from enum import Enum
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.console import Console

# Format options enum
class OutputFormat(str, Enum):
    console = "console"
    json = "json"

# Global state for CLI options
class GlobalOptions:
    verbose: int = 0
    quiet: bool = False

global_options = GlobalOptions()
console = Console()

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

def feedback_to_dict(feedback_item):
    """Convert a FeedbackItem to a dictionary for JSON serialization."""
    result = {
        "message": feedback_item.message,
        "rule_id": feedback_item.rule_id,
        "severity": feedback_item.severity.value,
        "span": {
            "path": feedback_item.span.path,
            "start_line": feedback_item.span.start_line,
            "start_col": feedback_item.span.start_col,
            "end_line": feedback_item.span.end_line,
            "end_col": feedback_item.span.end_col,
        }
    }

    if feedback_item.doc_url:
        result["doc_url"] = feedback_item.doc_url

    return result

def process_module_list(modules: List[str]) -> List[str]:
    """Process comma-separated module names into a flat list."""
    logger = get_logger("cli")

    expanded_modules = []
    for module_item in modules:
        # Split by comma and strip whitespace
        expanded_modules.extend([m.strip() for m in module_item.split(',')])

    # Remove empty items
    expanded_modules = [m for m in expanded_modules if m]
    logger.debug(f"Modules to run: {expanded_modules}")

    return expanded_modules

def read_input_content(infile: typer.FileText) -> str:
    """Read patch content from input file."""
    logger = get_logger("cli")
    logger.debug(f"Reading patch from {infile.name}")

    patch_content = infile.read()
    logger.debug(f"Read {len(patch_content)} characters from input")

    return patch_content

def process_input_to_files(patch_content: str):
    """Convert patch content to ProcessedFile objects."""
    logger = get_logger("cli")

    processed_files = process_patch_content(patch_content)
    if not processed_files:
        logger.error("No files found in patch or failed to parse patch")
        raise typer.Exit(code=2)

    logger.info(f"Converted patch to {len(processed_files)} processed files")
    return processed_files

def load_and_filter_plugins(modules: List[str], output_format: OutputFormat):
    """Load plugins and filter them based on specified modules."""
    logger = get_logger("cli")

    # Load all plugins
    pm = PluginManager()
    plugins = pm.load_plugins()
    logger.debug(f"Loaded {len(plugins)} plugins")

    # Filter plugins based on modules
    if "all" not in modules:
        filtered_plugins = [p for p in plugins if p.__symbolic_name__ in modules]
        if not filtered_plugins:
            logger.warning(f"No plugins found matching the specified modules: {', '.join(modules)}")

            if output_format == OutputFormat.console:
                typer.echo("Available modules:")
                for plugin in plugins:
                    typer.echo(f"- {plugin.__symbolic_name__}")
            else:
                # For JSON format, output empty array when no modules found
                typer.echo(json.dumps([]))
            return []

        plugins = filtered_plugins
        logger.info(f"Filtered to {len(plugins)} plugins: {[p.__symbolic_name__ for p in plugins]}")

    logger.info(f"Running {len(plugins)} plugins")
    return plugins

def run_plugins(plugins, processed_files, output_format: OutputFormat) -> List[FeedbackItem]:
    """Run all plugins on the processed files and collect feedback."""
    logger = get_logger("cli")

    feedback = []

    # Don't show progress in JSON mode or if quiet
    if output_format == OutputFormat.json or global_options.quiet:
        for plugin in plugins:
            logger.debug(f"Running plugin: {plugin.__symbolic_name__}")

            with plugin as p:
                plugin.process(processed_files)

            plugin_feedback = plugin.feedback
            feedback.extend(plugin.feedback)
            logger.debug(f"Plugin {plugin.__symbolic_name__} generated {len(plugin_feedback)} feedback items")

    else:
        # Show progress with rich progress bar
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            console=console,
            transient=True  # Remove progress bar when done
        ) as progress:

            for plugin in plugins:
                # Create a task for this plugin
                task = progress.add_task(f"Running {plugin.__symbolic_name__}...", total=None)

                logger.debug(f"Running plugin: {plugin.__symbolic_name__}")
                start_time = time.time()

                with plugin as p:
                    plugin.process(processed_files)

                plugin_feedback = plugin.feedback
                feedback.extend(plugin_feedback)

                elapsed = time.time() - start_time
                logger.debug(f"Plugin {plugin.__symbolic_name__} generated {len(plugin_feedback)} feedback items in {elapsed:.2f}s")

                # Update task description to show completion
                progress.update(task, description=f"✓ {plugin.__symbolic_name__} ({len(plugin_feedback)} items)")

                # Brief pause to show the completed status
                time.sleep(0.1)

                # Remove the completed task
                progress.remove_task(task)

    return feedback

def analyze_feedback(feedback: List[FeedbackItem]) -> Tuple[int, int, int]:
    """Analyze feedback and count items by severity."""
    logger = get_logger("cli")

    error_count = sum(1 for item in feedback if item.severity.value == "error")
    warning_count = sum(1 for item in feedback if item.severity.value == "warning")
    info_count = sum(1 for item in feedback if item.severity.value == "info")

    logger.info(f"Collected {len(feedback)} feedback items: {error_count} errors, {warning_count} warnings, {info_count} info")

    return error_count, warning_count, info_count

def output_json_feedback(feedback: List[FeedbackItem]):
    """Output feedback in JSON format."""
    feedback_dicts = [feedback_to_dict(item) for item in feedback]
    typer.echo(json.dumps(feedback_dicts, indent=2, cls=ErrorEnumEncoder))

def output_console_feedback(feedback: List[FeedbackItem]):
    """Output feedback in console format with snippets."""
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

                typer.secho(f"- {item.message} (Severity: {item.severity.value}): {item.span.path}", fg=severity_color)

                if not item.span.is_empty():
                    render_snippet(
                        code="\n".join([line.content for line in item.span.lines_added]),
                        title=f"File: {item.span.path}",
                        highlight_lines=[item.span.start_line] if item.span.start_line >= 0 else [],
                        severity=item.severity,
                        annotations={
                            item.span.start_line: [(item.message, item.span.start_col if item.span.start_col >= 0 else 0)]
                        }
                    )
                if item.doc_url:
                    typer.secho(f"  More info: {item.doc_url}", fg=typer.colors.CYAN)
        else:
            typer.secho("✅ No issues found", fg=typer.colors.GREEN)

def output_feedback(feedback: List[FeedbackItem], output_format: OutputFormat):
    """Output feedback in the specified format."""
    if output_format == OutputFormat.json:
        output_json_feedback(feedback)
    else:
        output_console_feedback(feedback)

def show_processing_summary(processed_files, plugins, output_format: OutputFormat):
    """Show a summary of what will be processed."""
    if output_format == OutputFormat.json or global_options.quiet:
        return

    file_count = len(processed_files)
    plugin_count = len(plugins)

    console.print(f"[blue]Processing {file_count} file(s) with {plugin_count} plugin(s)...[/blue]")

    if global_options.verbose >= 1:
        console.print("[dim]Files:[/dim]")
        for f in processed_files:
            console.print(f"  [dim]• {f.path}[/dim]")

        console.print("[dim]Plugins:[/dim]")
        for p in plugins:
            console.print(f"  [dim]• {p.__symbolic_name__}[/dim]")
        console.print()

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
    format: OutputFormat = typer.Option(
        OutputFormat.console, "--format", "-f",
        help="Output format: 'console' for human-readable output with snippets, 'json' for machine-readable JSON array"
    ),
):
    """
    Run the linter on the specified patch.
    """
    logger = get_logger("cli")
    logger.debug(f"Output format: {format}")

    # Process input parameters
    expanded_modules = process_module_list(modules)

    # Read and process input
    patch_content = read_input_content(infile)
    processed_files = process_input_to_files(patch_content)

    # Load and filter plugins
    plugins = load_and_filter_plugins(expanded_modules, format)
    if not plugins:
        return  # Early exit if no plugins found

    # Show processing summary
    show_processing_summary(processed_files, plugins, format)

    # Run plugins and collect feedback
    feedback = run_plugins(plugins, processed_files, format)

    # Analyze feedback
    error_count, warning_count, info_count = analyze_feedback(feedback)

    # Output results
    output_feedback(feedback, format)

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


@app.command("help")
def help_cmd(
    ctx: typer.Context,
    command: Optional[list[str]] = typer.Argument(
        None,
        help="Show help for this app or a subcommand path, e.g. `help greet` or `help tools sub`.",
    ),
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
