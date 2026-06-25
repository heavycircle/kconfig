from __future__ import annotations

from typing import TYPE_CHECKING

import sympy

from kconfig.exceptions import KconfigASTAnomalyError, KconfigInvalidArgumentError

if TYPE_CHECKING:
    from tree_sitter import Node


def _parse_preproc_defined(node: Node) -> sympy.Expr:
    """Parse a ``preproc_defined`` node.

    Args:
        node (Node): The tree-sitter node to process.

    Raises:
        KconfigASTAnomalyError: Node is missing an argument.

    Returns:
        sympy.Expr: The expression representing this condition.

    """
    if not node.named_children:
        raise KconfigASTAnomalyError(node.type, "No arguments!")

    argument = node.named_children[0]
    if not argument.text:
        raise KconfigASTAnomalyError(node.type, "No arguments!")

    return sympy.Symbol(argument.text.decode())


def _parse_call_expression(node: Node) -> sympy.Expr:
    """Parse a ``call_expression`` node.

    This method only supports call expressions ``defined`` and ``IS_ENABLED``.

    Args:
        node (Node): The tree-sitter node to process.

    Raises:
        KconfigASTAnomalyError: Node is missing a ``function`` field.
        KconfigASTAnomalyError: Node is missing an ``arguments`` field.
        KconfigASTAnomalyError: Function has no arguments.
        KconfigInvalidArgumentError: Unsupported call expression.

    Returns:
        sympy.Expr: The expression representing this condition.

    """
    func_name = node.child_by_field_name("function")
    if not func_name or not func_name.text:
        raise KconfigASTAnomalyError(node.type, "Missing 'function' field")
    if func_name.text.decode() not in ("defined", "IS_ENABLED"):
        raise KconfigInvalidArgumentError(func_name.text.decode(), "Unsupported call_expression")

    # Get arguments to this function.
    func_args = node.child_by_field_name("arguments")
    if not func_args or not func_args.named_children:
        raise KconfigASTAnomalyError(node.type, "Missing 'arguments' field")

    # Our supported functions have one argument.
    arg_name = func_args.named_children[0]
    if not arg_name or not arg_name.text:
        raise KconfigASTAnomalyError(func_args.type, "No arguments!")

    return sympy.Symbol(arg_name.text.decode())


def _parse_binary_expression(node: Node) -> sympy.Expr | None:
    """Parse a ``binary_expression`` node.

    This method only supports binary expressions ``&&`` and ``||``.

    Args:
        node (Node): The tree-sitter node to process.

    Raises:
        KconfigASTAnomalyError: Node is missing an ``operator`` field.
        KconfigASTAnomalyError: Node is missing a ``left`` field.
        KconfigASTAnomalyError: Node is missing a ``right`` field.

    Returns:
        sympy.Expr | None: The expression representing this condition, or None
            if the expression could not be parsed.

    """
    op = node.child_by_field_name("operator")
    if not op or not op.text:
        raise KconfigASTAnomalyError(node.type, "Missing 'operator' field")

    left = node.child_by_field_name("left")
    right = node.child_by_field_name("right")
    if not (left and right):
        raise KconfigASTAnomalyError(node.type, "Missing 'left' and 'right' fields")

    if op.text.decode() == "&&":
        return sympy.And(parse_condition_node(left), parse_condition_node(right))
    if op.text.decode() == "||":
        return sympy.Or(parse_condition_node(left), parse_condition_node(right))

    return None


def _parse_unary_expression(node: Node) -> sympy.Expr | None:
    """Parse a ``unary_expression`` node.

    This method only supports unary expression ``!``.

    Args:
        node (Node): The tree-sitter node to process.

    Raises:
        KconfigASTAnomalyError: Node is missing an ``operator`` field.
        KconfigASTAnomalyError: Node is missing an ``argument`` field.

    Returns:
        sympy.Expr | None: The expression representing this condition, or None
            if the expression could not be parsed.

    """
    op = node.child_by_field_name("operator")
    if not op or not op.text:
        raise KconfigASTAnomalyError(node.type, "Missing 'operator' field")

    argument = node.child_by_field_name("argument")
    if not argument:
        raise KconfigASTAnomalyError(node.type, "Missing 'argument' field")

    if op.text.decode() == "!":
        return sympy.Not(parse_condition_node(argument))

    return None


def parse_condition_node(node: Node) -> sympy.Expr:
    """Parse a condition node and yield an equivalent sympy expression.

    This method recursively parses sub-expressions until a complete sympy.Expr
    is found. If at any point something cannot be processed or is not supported,
    it is turned into a unique sympy.Symbol. This allows us to continue parsing
    the structure, accepting unsupported conditions, where the end-user can
    determine what the config means.

    Args:
        node (Node): The tree-sitter node to process.

    Raises:
        KconfigASTAnomalyError: Node is missing a body.

    Returns:
        sympy.Expr: The expression representing this condition.

    """
    if not node.text:
        raise KconfigASTAnomalyError(node.type, "Missing a body")

    match node.type:
        case "preproc_defined":
            expr = _parse_preproc_defined(node)
        case "call_expression":
            expr = _parse_call_expression(node)
        case "binary_expression":
            expr = _parse_binary_expression(node)
        case "unary_expression":
            expr = _parse_unary_expression(node)
        case "parenthesized_expression":
            if not node.named_children:
                raise KconfigASTAnomalyError(node.type, "Missing body")
            expr = parse_condition_node(node.named_children[0])
        case _:
            # Fallback for weird macros or unrecognized patterns.
            expr = sympy.Symbol(node.text.decode())

    return expr
