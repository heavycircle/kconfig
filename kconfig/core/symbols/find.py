from __future__ import annotations

from typing import TYPE_CHECKING

from kconfig.core import parser, utils
from kconfig.styling_api import ui
from kconfig.utils import KconfigSignature, KconfigSymbolNotFoundError, state


if TYPE_CHECKING:
    from pathlib import Path


def get_function_signature(kernel_root: Path, symbol_name: str) -> KconfigSignature:
    """Enumerate a function's signature for custom config values.

    Args:
        kernel_root (Path): Root of the kernel source tree.
        symbol_name (str): Symbol name to find.

    Returns:
        KconfigSignature: Signature representing this symbol.

    """
    for file in utils.find_candidate_function_files(kernel_root, symbol_name):
        contents = file.read_bytes()
        for _, captures in parser.run_query("signature-find", contents):
            if "func.name" not in captures:
                continue

            found_name = captures["func.name"][0].text.decode()
            if found_name != symbol_name:
                continue

            is_macro = False

            if "func.def" in captures:
                node = captures["func.def"][0]
                body = node.child_by_field_name("body")
                signature = contents[node.start_byte : body.start_byte] if body else utils.get_node_text(node)

            elif "macro.func.def" in captures:
                node = captures["macro.func.def"][0]
                signature = utils.get_capture_text(captures, "macro.func.def")[0]
                is_macro = True

            elif "macro.obj.def" in captures:
                node = captures["macro.obj.def"][0]
                signature = utils.get_capture_text(captures, "macro.obj.def")[0]
                is_macro = True

            else:
                continue

            ui.out_debug(f"Found {'macro' if is_macro else 'function'} {symbol_name} in {file} ...")
            signature_layout = KconfigSignature(
                symbol_name, signature.decode().strip(), is_macro=is_macro, file=file.relative_to(state.kernel_dir)
            )
            signature_layout.members = parser.get_custom_members(node)
            return signature_layout

    raise KconfigSymbolNotFoundError(symbol_name, kernel_root)
