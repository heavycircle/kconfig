from __future__ import annotations

from kconfig.core import parser
from kconfig.utils import KconfigFileNoMatchError, KconfigQueryImpossibleError, KconfigSignature, ui

from .utils import find_candidate_files


def get_function_signature(kernel_root: str, symbol_name: str) -> tuple[str, bool]:
    """Get a function's signature.

    Args:
        kernel_root (str): The kernel root to search for.
        symbol_name (str): The symbol to find.

    Raises:
        KconfigQueryImpossibleError: Resolved function has no body.

    Returns:
        tuple[str, bool]: Tuple containing signature and macro boolean.

    """
    query = parser.get_query("signature-find").replace("__SYMBOL_NAME__", symbol_name)
    for file in find_candidate_files(kernel_root, symbol_name):
        contents = file.read_bytes()
        result = parser.run_query(contents, query)

        if "func.def" in result:
            ui.out_debug(f"Found function {symbol_name} in {file} ...")
            node = parser.get_single_node(result, "func.def")
            if not node.text:
                raise KconfigQueryImpossibleError(f"Impossible: Missing node body: {symbol_name}")

            body = node.child_by_field_name("body")
            if body:
                signature = contents[node.start_byte : body.start_byte]
                return signature.decode("utf-8").strip(), False
            return node.text.decode("utf-8").strip(), False

        if "macro.func.def" in result:
            ui.out_debug(f"Found function {symbol_name} in {file} ...")
            return parser.get_single_node_text(result, "macro.func.def"), True

        if "macro.obj.def" in result:
            ui.out_debug(f"Found function {symbol_name} in {file} ...")
            return parser.get_single_node_text(result, "macro.obj.def"), True

    raise KconfigFileNoMatchError(f"Cannot find a file defining: {symbol_name}")


def get_symbol(kernel_root: str, symbol_name: str) -> KconfigSignature:
    """Parser the provided kernel for a symbol."""
    signature, is_macro = get_function_signature(kernel_root, symbol_name)

    snippet = f"{signature} {{}}".encode()
    result = parser.run_query(snippet, parser.get_query("signature-match"))

    structs = set(parser.get_nodes(result, "struct.name"))
    unions = set(parser.get_nodes(result, "union.name"))
    typedefs = set(parser.get_nodes(result, "typedef.name"))
    typedefs = typedefs - structs - unions

    return KconfigSignature(
        name=symbol_name,
        signature=signature,
        is_macro=is_macro,
        structs=[s.text.decode() for s in structs if s.text],
        unions=[s.text.decode() for s in unions if s.text],
        typedefs=[s.text.decode() for s in typedefs if s.text],
    )
