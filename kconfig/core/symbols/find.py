from __future__ import annotations

from typing import TYPE_CHECKING

from kconfig.core import parser, utils
from kconfig.core.structs.utils import get_custom_struct_members
from kconfig.utils import KconfigSignature, KconfigSymbolNotFoundError, ui


if TYPE_CHECKING:
    from pathlib import Path


def get_function_signature_code(kernel_root: Path, symbol_name: str) -> KconfigSignature:
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
    for file in utils.find_candidate_function_files(kernel_root, symbol_name):
        contents = file.read_bytes()
        for _, captures in parser.run_query(contents, query):
            is_macro = False

            if "func.def" in captures:
                node = captures["func.def"][0]
                body = node.child_by_field_name("body")
                signature = contents[node.start_byte : body.start_byte] if body else utils.get_node_text(node)

            elif "macro.func.def" in captures:
                signature = utils.get_capture_text(captures, "macro.func.def")[0]
                is_macro = True

            elif "macro.obj.def" in captures:
                signature = utils.get_capture_text(captures, "macro.obj.def")[0]
                is_macro = True

            else:
                continue

            ui.out_debug(f"Found {'macro' if is_macro else 'function'} {symbol_name} in {file} ...")
            return KconfigSignature(symbol_name, signature.decode().strip(), is_macro=is_macro, file=file)

    raise KconfigSymbolNotFoundError(f"Cannot find a file defining: {symbol_name}")


def get_function_signature(kernel_root: Path, symbol_name: str) -> KconfigSignature:
    """Enumerate a function's signature for custom config values.

    Args:
        kernel_root (Path): Root of the kernel source tree.
        symbol_name (str): Symbol name to find.

    Returns:
        KconfigSignature: Signature representing this symbol.

    """
    signature = get_function_signature_code(kernel_root, symbol_name)
    signature.members = get_custom_struct_members(signature.signature.encode())
    return signature
