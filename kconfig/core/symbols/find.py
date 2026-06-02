from __future__ import annotations

from typing import TYPE_CHECKING

from kconfig.core import parser, utils
from kconfig.utils import KconfigFileNoMatchError, KconfigSignature, ui


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
        for _, captures in parser.run_query(contents, query):
            is_macro = False
            signature = b""

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
            return KconfigSignature(
                name=symbol_name, signature=signature.decode().strip(), is_macro=is_macro, file=file
            )

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

    structs, unions, typedefs = set[bytes](), set[bytes](), set[bytes]()
    for _, captures in parser.run_query(snippet, parser.get_query("signature-match")):
        structs.update(utils.get_node_text(n) for n in captures.get("struct.name", []))
        unions.update(utils.get_node_text(n) for n in captures.get("union.name", []))
        typedefs.update(utils.get_node_text(n) for n in captures.get("typedef.name", []))

    signature.structs = [s.decode() for s in structs]
    signature.unions = [u.decode() for u in unions]
    signature.typedefs = [t.decode() for t in typedefs - structs - unions]
    return signature
