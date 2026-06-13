from __future__ import annotations

import re


KERNEL_MACROS = [
    r"__percpu",
    r"__rcu",
    r"__user",
    r"__iomem",
    r"__kernel",
    r"__force",
    r"__nocast",
    r"__safe",
    r"__read_mostly",
    r"__write_mostly",
    r"__ro_after_init",
    r"__randomize_layout",
    r"__no_randomize_layout",
    r"____cacheline_aligned",
    r"____cacheline_aligned_in_smp",
    r"__init",
    r"__exit",
]
"""List of kernel macros to ignore."""

KERNEL_MACRO_PATTERN = re.compile(r"(?<![a-zA-Z0-9_])(?:" + "|".join(KERNEL_MACROS) + r")(?![a-zA-Z0-9_])")
"""Regex pattern for matching kernel macros."""


def normalize_field(field: str) -> str:
    """Normalize a field's whitespace.

    Args:
        field (str): Field to normalize.

    Returns:
        str: Normalized field.

    """
    return " ".join(field.split())


def normalize_struct(code: bytes) -> bytes:
    """Normalize the whitespace inside a structure.

    Args:
        code (bytes): Structure source code.

    Returns:
        bytes: Normalized code.

    """
    text = code.decode(errors="ignore")

    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)  # Remove block comments
    text = re.sub(r"//.*", "", text)  # Remove inline comments
    text = re.sub(r"[^\S\n]+", " ", text)  # Collapse horizontal whitespace, preserve newlines
    text = re.sub(r"\n{2,}", "\n", text)  # Collapse multiple blank lines
    # Use [^\S\n] so we don't consume newlines — preprocessor directives are line-oriented
    text = re.sub(r"[^\S\n]*([\{\}\[\]\(\);\*\,])[^\S\n]*", r"\1", text)  # Clean up structure spacing
    text = re.sub(r"(?<=[a-zA-Z0-9_])(\*+)", r" \1", text)  # Inspect spaces before asterisks

    # Inject single spaces for readability
    text = text.replace(";", "; ").replace(",", ", ").replace("{", "{ ").replace("}", "} ")
    return text.strip().encode()


def normalize_type(c_type: str) -> str:
    """Normalize a C type for comparison.

    This method works for normalizing both ``pahole`` and tree-sitter types.

    Args:
        c_type (str): C type to normalize.

    Returns:
        str: Normalized C type for comparison.

    """
    c_type = re.sub(r"\s+", "", c_type.strip())

    # Isolate pointers/arrays
    suffix_match = re.search(r"([\s\*\[\]0-9]+)$", c_type)
    suffix = suffix_match.group(1).replace(" ", "") if suffix_match else ""
    base_type = c_type[: len(suffix)] if suffix else c_type

    # Check for irregular types
    if base_type.startswith(("struct ", "union ", "enum ")):
        return f"{base_type}{suffix}"
    if base_type == "unsigned":
        base_type = "unsigned int"

    tokens = set(base_type.split())

    # Resolved sign-ness
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


def sanitize_kernel_macros(code: bytes) -> bytes:
    """Sanitize kernel macros that break the tree-sitter parser.

    Args:
        code (bytes): Code to sanitize.

    Returns:
        bytes: Sanitized code.

    """
    text = code.decode(errors="ignore")
    return KERNEL_MACRO_PATTERN.sub("", text).encode()
