# pip install rich
from collections.abc import Iterable

from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from sru_lint.common.feedback import Severity

console = Console()
POINTER_CHAR = "^"


def _get_severity_style(severity: Severity | None = None) -> str:
    """
    Get the appropriate style (color and weight) based on severity level.

    Args:
        severity: Severity enum value (Severity.ERROR, Severity.WARNING, Severity.INFO, or None)

    Returns:
        Rich style string combining color and weight
    """
    print(f"Severity received: {severity}")
    if severity == Severity.ERROR:
        return "bold red"
    elif severity == Severity.WARNING:
        return "bold yellow"
    elif severity == Severity.INFO:
        return "cyan"
    else:
        return "bold red"  # Default fallback


def _create_column_pointer(line: str, col_start: int, col_end: int) -> str:
    """
    Create a pointer line that shows an up-arrow at the specified column.

    Args:
        line: The source line to point at
        col_start: Starting column position (1-based) to point to
        col_end: Ending column position (1-based) to point to

    Returns:
        String with spaces and an up-arrow at the correct position
    """
    if col_start < 1:
        col_start = 1

    # Convert 1-based column to 0-based index
    col_index = col_start - 1

    # Handle tabs by expanding them to match visual alignment
    visual_line = line.expandtabs(4)  # Expand tabs to 4 spaces for consistent alignment

    # Ensure we don't go beyond the line length
    pointer_length = min(col_index, len(visual_line))

    # Create the pointer line with spaces up to the column, then an arrow
    pointer_chars = []
    for i in range(pointer_length):
        if visual_line[i] == "\t":
            pointer_chars.append("    ")  # Match tab expansion
        else:
            pointer_chars.append(" ")

    pointer_line = "".join(pointer_chars) + POINTER_CHAR * (max(1, col_end - col_start))
    return pointer_line


def _create_centered_message(message: str, arrow_col: int, line_width: int) -> str:
    """
    Create a message line centered below the arrow position.

    Args:
        message: The message to display
        arrow_col: Column position (1-based) where the arrow is
        line_width: Total width of the line for context

    Returns:
        String with the message positioned to be centered under the arrow
    """
    message_len = len(message)
    arrow_pos = arrow_col - 1  # Convert to 0-based

    # Calculate where to start the message so it's centered under the arrow
    message_start = max(0, arrow_pos - message_len // 2)

    # Create padding and the message
    padding = " " * message_start
    return padding + message


def render_snippet(
    code: str,
    *,
    language: str = "python",
    start_line: int = 1,
    start_col: int = 1,
    highlight_lines: Iterable[int] | None = None,
    severity: Severity | None = None,
    annotations: dict[int, list[str] | list[tuple[str, int]]] | None = None,
    title: str | None = None,
):
    """
    Render a code snippet with a gutter, line numbers, optional highlighted lines,
    and inline annotation lines placed *under* the referenced code line.

    - highlight_lines: set/list of line numbers (1-based within snippet) to emphasize.
    - annotations: dict of {line_number: [messages...]} where messages can be:
        - str: simple message without column positioning
        - tuple(message, column): message with up-arrow pointing to specific column
    """
    highlight_lines = set(highlight_lines or [])
    annotations = annotations or {}

    lines = code.splitlines()
    ln_width = len(str(start_line + len(lines) - 1))

    table = Table.grid(padding=(0, 1))
    table.expand = True
    # gutter pointer, line number, code
    table.add_column("g", width=1, justify="right", no_wrap=True)
    table.add_column("#", width=ln_width, justify="right", no_wrap=True, style="dim")
    table.add_column("code")

    for i, raw in enumerate(lines, start=start_line):
        is_hot = (i - start_line + 1) in highlight_lines  # highlight uses snippet-local numbers
        pointer = "❱" if is_hot else "│"
        # Build the code cell; keep whitespace, no wrap
        code_cell = Text(raw, no_wrap=True)
        if is_hot:
            code_cell.stylize("bold")

        table.add_row(pointer, f"{i}", code_cell)

        # Insert any annotations under this line (span across columns 2..3)
        annos = annotations.get(i - start_line + 1) or annotations.get(
            i
        )  # support local or absolute
        if annos:
            for annotation in annos:
                # Handle both string and tuple formats
                if isinstance(annotation, tuple):
                    msg, col_start, col_end = annotation
                    # Create pointer line with arrow at specified column
                    pointer_line = _create_column_pointer(raw, col_start, col_end)
                    pointer_text = Text(pointer_line, style="cyan")
                    table.add_row("│", " " * ln_width, pointer_text)

                    # Create centered message below the arrow
                    centered_message = _create_centered_message(msg, col_start, len(raw))
                    msg_text = Text(centered_message, style=_get_severity_style(severity))
                    table.add_row("│", " " * ln_width, msg_text)
                else:
                    # Simple string annotation without column positioning
                    msg_text = Text(annotation, style=_get_severity_style(severity))
                    table.add_row("│", " " * ln_width, msg_text)

    group = Group(table)
    console.print(Panel(group, title=title, border_style="dim"))


# Example usage and test function
def test_render_snippet():
    """Test function to demonstrate the new annotation features."""
    sample_code = """def hello_world():
    print("Hello, world!")
    if True:
        return "success"
    else:
        return "failure\""""

    # Test with mixed annotation types
    annotations = {
        1: [("Missing docstring", 1)],  # Point to beginning of function
        2: ["This line looks good"],  # Simple message without column
        3: [("Consider simplifying", 8)],  # Point to 'True'
        5: [
            ("Unreachable code", 9),  # Point to 'return'
            "This else branch never executes",  # Simple message
        ],
    }

    render_snippet(
        sample_code,
        language="python",
        start_line=10,
        highlight_lines=[1, 3, 5],
        severity=Severity.ERROR,
        annotations=annotations,
        title="Sample Code with Annotations",
    )


if __name__ == "__main__":
    test_render_snippet()
