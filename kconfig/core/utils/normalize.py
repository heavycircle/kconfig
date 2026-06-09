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

KERNEL_TYPE_ALIASES = {
    "Elf_Sym": "Elf64_Sym",  # Assuming a 64-bit target module
    "u8": "unsigned char",
    "u16": "unsigned short",
    "u32": "unsigned int",
    "u64": "unsigned long long",
    "s8": "signed char",
    "s16": "short",
    "s32": "int",
    "s64": "long long",
    "size_t": "unsigned long",
    "ssize_t": "long",
}
"""Type aliases to use during comparison."""


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
    """Normalize C types for comparison.

    Args:
        c_type (str): Type to compare.

    Returns:
        str: Normalized type.

    """
    tokens = c_type.split()
    normal_tokens = [KERNEL_TYPE_ALIASES.get(token, token) for token in tokens]
    return " ".join(normal_tokens)


def sanitize_kernel_macros(code: bytes) -> bytes:
    """Sanitize kernel macros that break the tree-sitter parser.

    Args:
        code (bytes): Code to sanitize.

    Returns:
        bytes: Sanitized code.

    """
    text = code.decode(errors="ignore")
    return KERNEL_MACRO_PATTERN.sub("", text).encode()
