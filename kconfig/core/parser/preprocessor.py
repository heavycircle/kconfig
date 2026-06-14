from __future__ import annotations

from typing import TYPE_CHECKING

from kconfig.exceptions import KconfigASTAnomalyError, KconfigInvalidArgumentError, KconfigUnsupportedArgumentError
from kconfig.types import KconfigFieldGuard
from kconfig.ui import ui


if TYPE_CHECKING:
    from tree_sitter import Node


def negate_guard(guard: KconfigFieldGuard) -> KconfigFieldGuard:
    """Negate the enabled status of a field guard.

    Args:
        guard (KconfigFieldGuard): The guard to negate.

    Returns:
        KconfigFieldGuard: The resulting negated guard.

    """
    guard.is_enabled = False
    return guard


def parse_expression(node: Node) -> KconfigFieldGuard:
    """Parse a generic expression node for all expression nodes."""
    if node.type == "binary_expression":
        return parse_binary_expression(node)
    if node.type == "unary_expression":
        return parse_unary_expression(node)
    if node.type == "preproc_defined":
        return parse_preproc_defined(node)
    if node.type == "call_expression":
        return parse_call_expression(node)
    if node.type in ("identifier", "number_literal"):
        return KconfigFieldGuard(name=node.text.decode())
    if node.type == "parenthesized_expression":
        inner_nodes = [c for c in node.children if c.is_named]
        if not inner_nodes:
            raise KconfigASTAnomalyError(node.type, "Empty parenthesized_expression")
        return parse_expression(inner_nodes[0])

    ui.out_debug(f"Unrecognized node: '{node.type}', treating as opaque ...")
    return KconfigFieldGuard(node.text.decode())


def get_previous_conditions(node: Node) -> KconfigFieldGuard:
    """Walk up the tree to gather and negate preceeding if/elif conditions."""
    current = node.parent

    to_check: list[Node] = []
    while current and not current.type.startswith("preproc_if"):
        to_check.insert(0, current)
        current = current.parent

    if current:
        to_check.insert(0, current)

    guard = KconfigFieldGuard(operand="&&")
    for prev_node in to_check:
        guard.expression.append(negate_guard(parse_preproc(prev_node)))
    return guard


def parse_call_expression(call_node: Node) -> KconfigFieldGuard:
    """Parse a call_expression node."""
    if call_node.type != "call_expression":
        raise KconfigInvalidArgumentError(call_node.type, "Not a call_expression")

    func, args = call_node.children
    func_name = func.text.decode()
    if func_name not in ("IS_ENABLED", "IS_BUILTIN", "IS_MODULE", "IS_REACHABLE"):
        # Return the function as an opaque variable
        return KconfigFieldGuard(call_node.text.decode())

    named_args = [child for child in args.children if child.is_named]
    if not named_args:
        raise KconfigASTAnomalyError(call_node.type, f"No arguments inside {func_name}()")
    return KconfigFieldGuard(named_args[0].text.decode())


def parse_unary_expression(expr_node: Node) -> KconfigFieldGuard:
    """Parse a unary_expression node to get the CONFIG underneath."""
    if expr_node.type != "unary_expression":
        raise KconfigInvalidArgumentError(expr_node.type, "Not a unary_expression")

    operator, argument = expr_node.children
    if operator.type != "!":
        raise KconfigUnsupportedArgumentError(operator.type)

    inner_guard = parse_expression(argument)
    return negate_guard(inner_guard)


def parse_binary_expression(expr_node: Node) -> KconfigFieldGuard:
    """Parse a binary_expression node.

    This method may recursively call itself if there are sub-expressions.
    """
    if expr_node.type != "binary_expression":
        raise KconfigInvalidArgumentError(expr_node.type, "Not a binary_expression")

    left, operator, right = expr_node.children

    valid_ops = ("||", "&&", "!=", "==", ">", "<", ">=", "<=", "&", "|", "^", "<<", ">>")
    if operator.type not in valid_ops:
        raise KconfigUnsupportedArgumentError(operator.type)

    configs = [parse_expression(left), parse_expression(right)]
    return KconfigFieldGuard(operand=operator.type, expression=configs)


def parse_preproc_defined(preproc_node: Node) -> KconfigFieldGuard:
    """Parse a preproc_defined node."""
    if preproc_node.type != "preproc_defined":
        raise KconfigInvalidArgumentError(preproc_node.type, "Not a preproc_defined")

    for child in preproc_node.children:
        if child.type == "identifier":
            return KconfigFieldGuard(child.text.decode(), is_enabled=True)

    raise KconfigASTAnomalyError(preproc_node.type, "Missing 'identifier' field")


def parse_preproc_ifdef(preproc_node: Node) -> KconfigFieldGuard:
    """Parse a preproc_ifdef node.

    Tree-sitter categorizes ifdefs and ifndefs under the same node. Therefore,
    we must check the node type to determine if it's enabled.
    """
    if preproc_node.type != "preproc_ifdef":
        raise KconfigInvalidArgumentError(preproc_node.type, "Not a preproc_ifdef")

    name_node = preproc_node.child_by_field_name("name")
    if not name_node:
        raise KconfigASTAnomalyError(preproc_node.type, "Missing 'name' field")

    preproc_name = name_node.text.decode()
    preproc_type = preproc_node.children[0].text.decode()
    return KconfigFieldGuard(name=preproc_name, is_enabled=preproc_type == "#ifdef")


def parse_preproc_if(preproc_node: Node) -> KconfigFieldGuard:
    """Parse a preproc_if or preproc_elif node."""
    if preproc_node.type not in ("preproc_if", "preproc_elif"):
        raise KconfigInvalidArgumentError(preproc_node.type, "Not a preproc_if or preproc_elif")

    condition_node = preproc_node.child_by_field_name("condition")
    if not condition_node:
        raise KconfigASTAnomalyError(preproc_node.type, "Missing 'condition' field")

    guard = parse_expression(condition_node)
    if preproc_node.type == "preproc_elif":
        above_guard = get_previous_conditions(preproc_node)
        guard = KconfigFieldGuard(operand="&&", expression=[above_guard, guard])

    return guard


def parse_preproc_else(preproc_node: Node) -> KconfigFieldGuard:
    """Parse a preproc_else node."""
    if preproc_node.type != "preproc_else":
        raise KconfigInvalidArgumentError(preproc_node.type, "Not a preproc_else")

    return get_previous_conditions(preproc_node)


def parse_preproc(preproc_node: Node) -> KconfigFieldGuard:
    """Parse a generic preproc node."""
    if not preproc_node.type.startswith("preproc_"):
        raise KconfigInvalidArgumentError(preproc_node.type, "Not a preprocessor node")

    match preproc_node.type:
        case "preproc_if" | "preproc_elif":
            return parse_preproc_if(preproc_node)
        case "preproc_ifdef":
            return parse_preproc_ifdef(preproc_node)
        case "preproc_else":
            return parse_preproc_else(preproc_node)
        case _:
            raise KconfigUnsupportedArgumentError(preproc_node.type)
