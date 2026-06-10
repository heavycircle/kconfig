from __future__ import annotations

from typing import TYPE_CHECKING

from kconfig.exceptions import KconfigASTAnomalyError, KconfigInvalidArgumentError, KconfigUnsupportedArgumentError
from kconfig.types import KconfigFieldGuard


if TYPE_CHECKING:
    from tree_sitter import Node


def negate_guard(guard: KconfigFieldGuard) -> KconfigFieldGuard:
    guard.is_enabled = False
    return guard


def parse_unary_expression(expr_node: Node) -> KconfigFieldGuard:
    """Parse a unary_expression node to get the CONFIG underneath."""
    if expr_node.type != "unary_expression":
        raise KconfigInvalidArgumentError(expr_node.type, "Not a unary_expression")

    operator, argument = expr_node.children
    if operator.type != "!":
        raise KconfigUnsupportedArgumentError(operator.type)

    if argument.type == "preproc_defined":
        return negate_guard(parse_preproc_defined(argument))
    if argument.type == "identifier":
        return negate_guard(KconfigFieldGuard(name=argument.text.decode()))
    raise KconfigUnsupportedArgumentError(argument.type)


def parse_binary_expression(expr_node: Node) -> KconfigFieldGuard:
    """Parse a binary_expression node.

    This method may recursively call itself if there are sub-expressions.
    """
    if expr_node.type != "binary_expression":
        raise KconfigInvalidArgumentError(expr_node.type, "Not a binary_expression")

    left, operator, right = expr_node.children
    if operator.type not in ("||", "&&", "==", ">", "<"):
        raise KconfigUnsupportedArgumentError(operator.type)

    configs: list[KconfigFieldGuard] = []
    for side in (left, right):
        if side.type == "binary_expression":
            configs.append(parse_binary_expression(side))
        elif side.type == "unary_expression":
            configs.append(parse_unary_expression(side))
        elif side.type == "preproc_defined":
            configs.append(parse_preproc_defined(side))
        elif side.type in ("identifier", "number_literal"):
            configs.append(KconfigFieldGuard(name=side.text.decode(), is_enabled=True))
        else:
            raise KconfigUnsupportedArgumentError(side.type)

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

    if condition_node.type == "binary_expression":
        guard = parse_binary_expression(condition_node)
    elif condition_node.type == "unary_expression":
        guard = parse_unary_expression(condition_node)
    elif condition_node.type == "preproc_defined":
        guard = parse_preproc_defined(condition_node)
    elif condition_node.type == "identifier":
        guard = KconfigFieldGuard(name=condition_node.text.decode(), is_enabled=True)
    else:
        raise KconfigUnsupportedArgumentError(condition_node.type)

    if preproc_node.type == "preproc_elif":
        # Find the parent if/elif nodes.
        current = preproc_node.parent
        to_check: list[Node] = []
        while current and not current.type.startswith("preproc_if"):
            to_check.insert(0, current)
            current = current.parent
        if current:
            to_check.insert(0, current)

        # Get the configs and negate them.
        above = KconfigFieldGuard(operand="&&")
        for node in to_check:
            above.expression.append(negate_guard(parse_preproc(node)))

        # Add negated guards to this expression.
        guard = KconfigFieldGuard(operand="&&", expression=[above, guard])

    return guard


def parse_preproc_else(preproc_node: Node) -> KconfigFieldGuard:
    """Parse a preproc_else node."""
    if preproc_node.type != "preproc_else":
        raise KconfigInvalidArgumentError(preproc_node.type, "Not a preproc_else")

    # TODO: Make a parse_above_if function with this.
    current = preproc_node.parent
    to_check: list[Node] = []
    while current and not current.type.startswith("preproc_if"):
        to_check.insert(0, current)
        current = current.parent
    if current:
        to_check.insert(0, current)

    guard = KconfigFieldGuard(operand="&&")
    for node in to_check:
        guard.expression.append(negate_guard(parse_preproc(node)))
    return guard


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
