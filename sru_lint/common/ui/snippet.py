# pip install rich
from typing import Dict, List, Iterable, Optional
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()

def render_snippet(
    code: str,
    *,
    language: str = "python",
    start_line: int = 1,
    highlight_lines: Optional[Iterable[int]] = None,
    annotations: Optional[Dict[int, List[str]]] = None,
    title: Optional[str] = None,
):
    """
    Render a code snippet with a gutter, line numbers, optional highlighted lines,
    and inline annotation lines placed *under* the referenced code line.

    - highlight_lines: set/list of line numbers (1-based within snippet) to emphasize.
    - annotations: dict of {line_number: [messages...]} to render under that line.
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
        annos = annotations.get(i - start_line + 1) or annotations.get(i)  # support local or absolute
        if annos:
            for msg in annos:
                msg_text = Text(msg, style="bold red")
                # empty line-number cell to visually nest the note under the code line
                table.add_row("│", " " * ln_width, msg_text)

    group = Group(table)
    console.print(Panel(group, title=title, border_style="dim"))

# # --- Example usage ---
# snippet = """\
# def process_file(path):
#     with open(path) as f:
#         for line_no, line in enumerate(f, 1):
#             header = parse_header(line)
#             header.line_number = line_no
#             headers.append(header)
# """

# render_snippet(
#     snippet,
#     start_line=34,
#     highlight_lines=[37],  # visually emphasize line 37
#     annotations={
#         37: ["AttributeError: 'Header' object has no attribute 'line_number'"],
#         35: ["parse_header may return None here?"],
#     },
#     title="/home/dgd/devel/sru-lint/sru_lint/plugins/changelog_entry.py",
# )
