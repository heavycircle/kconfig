from typing import TYPE_CHECKING, ParamSpec, TypeVar

from .logging import ui

from rich.console import Group
from rich.panel import Panel
from rich.text import Text
from rich.tree import Tree
from rich.syntax import Syntax

if TYPE_CHECKING:
  from collections.abc import Callable
  from rich.console import RenderableType
  from kconfig.utils import KconfigSignature, KconfigStruct

P = ParamSpec("P")
T = TypeVar("T")

def render_call(func: Callable[P, T], message: str, *args: P.args, **kwargs: P.kwargs) -> T:
  """Wrap a function call with a rich status spinner."""
  with ui.raw.status(message) as status:
    kwargs['status'] = status
    return func(*args, **kwargs)

def render_struct(struct: KconfigStruct, parent: Tree | None = None) -> None:
  """Print a structure tree."""
  title = f"[bold cyan]struct {struct.name}[/] [dim]({struct.file})[/]"
  tree = parent.add(title) if parent else Tree(f"Layout: {title}")

  for field in struct.fields:
    text = f"[green]{field.field_type}[/] [white]{field.field_name}[/]"
    if field.depends:
      configs = " & ".join(field.depends)
      text += f"[dim italic yellow] (Requires: {configs})[/]"

    tree.add(text)

  for nested in struct.nested:
    render_struct(nested, tree)

  ui.raw.print(tree)

def render_signature(sig: KconfigSignature) -> None:
    """Print a signature."""
    syntax_block = Syntax(sig.signature, "c", theme="ansi_dark", background_color="default")
    renderables = [syntax_block]
    
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
        subtitle=f"[dim]Source: {str(sig.file)}[/]",
        border_style="cyan"
    )
    ui.raw.print(panel)
