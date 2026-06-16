from __future__ import annotations

import re


def strip_type_modifiers(type_name: str) -> tuple[str, str]:
    """Strip a type of its modifiers."""
    suffix_match = re.search(r"([\s\*\[\]0-9]+)$", type_name)
    if suffix_match:
        raw_suffix = suffix_match.group(1)
        base_type = type_name[: -len(raw_suffix)].strip()
        suffix = raw_suffix.replace(" ", "")
    else:
        base_type = type_name.strip()
        suffix = ""

    return base_type, suffix


def normalize_type(c_type: str) -> str:
    """Normalize a C type for comparison.

    This method works for normalizing both ``pahole`` and tree-sitter types.

    Args:
        c_type (str): C type to normalize.

    Returns:
        str: Normalized C type for comparison.

    """
    c_type = re.sub(r"\s+", " ", c_type.strip())
    base_type, suffix = strip_type_modifiers(c_type)

    if base_type.startswith(("struct ", "union ", "enum ")):
        return f"{base_type}{suffix}"

    if base_type == "unsigned":
        base_type = "unsigned int"

    tokens = set(base_type.split())

    # Resolve sign-ness
    is_unsigned = "unsigned" in tokens
    tokens.discard("signed")
    tokens.discard("unsigned")

    # Get sizes
    if "long" in tokens:
        base = "long long" if base_type.count("long") > 1 else "long"
    elif "short" in tokens:
        base = "short"
    elif "char" in tokens:
        base = "char"
    elif "int" in tokens:
        base = "int"
    else:
        return f"{base_type}{suffix}"

    # Prepend unsigned flag
    canonical_base = f"unsigned {base}" if is_unsigned else base
    return f"{canonical_base}{suffix}"
