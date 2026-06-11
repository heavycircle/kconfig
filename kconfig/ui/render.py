from __future__ import annotations

from typing import TYPE_CHECKING, ParamSpec, TypeVar

from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text
from rich.tree import Tree

from kconfig.core import analysis

from .logging import ui


if TYPE_CHECKING:
    from collections.abc import Callable

    from kconfig.types import KconfigSignature, KconfigStruct

P = ParamSpec("P")
T = TypeVar("T")


def render_call(func: Callable[P, T], message: str, *args: P.args, **kwargs: P.kwargs) -> T:
    """Wrap a function call with a rich status spinner.

    Args:
        func (Callable[P, T]): Function to call.
        message (str): Status message displayed in the spinner while the function runs.
        *args (P.args): Positional arguments forwarded to ``func``.
        **kwargs (P.kwargs): Keyword arguments forwarded to ``func``. A ``status`` key is
            injected automatically with the active ``Status`` object.

    Returns:
        T: The return value of ``func``.

    """
    with ui.raw.status(message) as status:
        kwargs["status"] = status
        return func(*args, **kwargs)


def render_struct(struct: KconfigStruct, parent: Tree | None = None) -> RenderableType:
    """Print a structure tree to the console.

    Recursively renders nested structs as sub-branches. When ``parent`` is
    provided the struct is added as a child branch instead of a new root tree.

    Args:
        struct (KconfigStruct): Struct to render.
        parent (Tree | None): Existing Rich ``Tree`` node to attach to as a
            child. If ``None`` a new root tree is created and printed.

    """
    title = f"[bold cyan]{struct.original_name}[/]"
    if struct.resolved_name != struct.original_name:
        title += f" [dim italic] -> {struct.resolved_name}[/]"
    title += f" [dim]({struct.file})[/]"

    tree = parent.add(title) if parent else Tree(f"Layout: {title}")

    for field in struct.fields:
        field_text = f"[green]{field.field_type.original_type}[/] [white]{field.field_name}[/]"
        if field.depends:
            field_text += (
                f"[dim italic yellow] (Requires: {analysis.simplify_config_expression(str(field.depends))})[/]"
            )

        if field.field_type.layout:
            field_node = tree.add(field_text)
            render_struct(field.field_type.layout, parent=field_node)
        else:
            tree.add(field_text)

    return tree


def render_signature(sig: KconfigSignature) -> None:
    """Print a function or macro signature inside a Rich panel.

    Displays the C source signature with syntax highlighting and, when present,
    a list of detected type dependencies (structs, unions, typedefs).

    Args:
        sig (KconfigSignature): Signature object to render.

    """
    syntax_block = Syntax(sig.signature, "c", theme="ansi_dark", background_color="default")
    renderables: list[RenderableType] = [syntax_block]

    if not sig.members.is_empty:
        renderables.append(Text("\n--- Detected Type Dependencies ---", style="dim"))

        if sig.members.structs:
            struct_str = ", ".join(sig.members.structs)
            renderables.append(Text.from_markup(f"[cyan]Structs:[/cyan]  {struct_str}"))
        if sig.members.unions:
            union_str = ", ".join(sig.members.unions)
            renderables.append(Text.from_markup(f"[magenta]Unions:[/magenta]   {union_str}"))
        if sig.members.typedefs:
            typedef_str = ", ".join(sig.members.typedefs)
            renderables.append(Text.from_markup(f"[green]Typedefs:[/green] {typedef_str}"))

    type_label = "Macro" if sig.is_macro else "Function"
    panel = Panel(
        Group(*renderables),
        title=f"[bold cyan]{type_label}: {sig.name}[/]",
        subtitle=f"[dim]Source: {sig.file!s}[/]",
        border_style="cyan",
    )
    ui.raw.print(panel)
