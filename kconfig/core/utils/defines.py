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
"""Regex patten for matching kernel macros."""

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
