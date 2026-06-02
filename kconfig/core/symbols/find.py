from __future__ import annotations

from typing import TYPE_CHECKING

from kconfig.core import parser, utils
from kconfig.utils import KconfigFileNoMatchError, KconfigQueryImpossibleError, KconfigSignature, ui


if TYPE_CHECKING:
    from pathlib import Path


def get_function_signature(kernel_root: Path, symbol_name: str) -> KconfigSignature:
    """Get a function's signature.

    Args:
        kernel_root (Path): The kernel root to search for.
        symbol_name (str): The symbol to find.

    Raises:
        KconfigQueryImpossibleError: Resolved function has no body.

    Returns:
        KconfigSignature: Signature of the function.

    """
    query = parser.get_query("signature-find").replace("__SYMBOL_NAME__", symbol_name)
    for file in utils.find_candidate_source_files(kernel_root, symbol_name):
        contents = file.read_bytes()
        result = parser.run_query(contents, query)
        if not result:
            continue

        is_macro = False

        if "func.def" in result:
            node = utils.get_single_node(result, "func.def")
            if not node.text:
                raise KconfigQueryImpossibleError(f"Impossible: Missing node body: {symbol_name}")

            body = node.child_by_field_name("body")
            if body:
                signature = contents[node.start_byte : body.start_byte].decode("utf-8").strip()
            else:
                signature = node.text.decode("utf-8").strip()

        elif "macro.func.def" in result:
            signature = utils.get_single_node_text(result, "macro.func.def").decode()
            is_macro = True

        elif "macro.obj.def" in result:
            signature = utils.get_single_node_text(result, "macro.obj.def").decode()
            is_macro = True

        else:
            continue

        ui.out_debug(f"Found {'macro' if is_macro else 'function'} {symbol_name} in {file} ...")
        return KconfigSignature(name=symbol_name, signature=signature, is_macro=is_macro, file=file)
    raise KconfigFileNoMatchError(f"Cannot find a file defining: {symbol_name}")


def get_symbol(kernel_root: Path, symbol_name: str) -> KconfigSignature:
    """Parser the provided kernel for a symbol.

    Args:
        kernel_root (Path): Root of the kernel source tree.
        symbol_name (str): Symbol name to find.

    Returns:
        KconfigSignature: Signature representing this symbol.

    """
    signature = get_function_signature(kernel_root, symbol_name)

    snippet = f"{signature.signature} {{}}".encode()
    result = parser.run_query(snippet, parser.get_query("signature-match"))

    structs = set(utils.get_nodes(result, "struct.name"))
    signature.structs = [s.text.decode() for s in structs if s.text]
    unions = set(utils.get_nodes(result, "union.name"))
    signature.unions = [s.text.decode() for s in unions if s.text]
    typedefs = set(utils.get_nodes(result, "typedef.name"))
    typedefs = typedefs - structs - unions
    signature.typedefs = [s.text.decode() for s in typedefs if s.text]

    return signature
