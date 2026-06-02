from __future__ import annotations

import re

from .defines import KERNEL_ALIASES, KERNEL_MACRO_PATTERN


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

  text = re.sub(r"/\*.*?\*/", text, flags=re.DOTALL)  # Remove block comments
  text = re.sub(r"//.*", "", text)  # Remove inline comments
  text = re.sub(r"\s+", " ", text)  # Collapse whitespace
  text = re.sub(r'\s*([\{\}\[\]\(\);\*\,])\s*', r'\1', text)  # Clean up structure spacing
  text = re.sub(r'(?<=[a-zA-Z0-9_])(\*+)', r' \1', text)  # Inspect spaces before asterisks

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
  normal_tokens = [KERNEL_ALIASES.get(token, token) for token in tokens]
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
