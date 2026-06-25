from __future__ import annotations

from dataclasses import dataclass, field

import sympy

from kconfig.exceptions import KconfigASTAnomalyError

from .structs import KconfigStructField


@dataclass
class KconfigParserState:
    """The current state of parsing a struct."""

    configs: list[sympy.Expr] = field(default_factory=list)
    fields: list[KconfigStructField] = field(default_factory=list)

    def push_config(self, expr: sympy.Expr) -> None:
        """Add a config to the stack."""
        self.configs.append(expr)

    def pop_config(self) -> sympy.Expr | None:
        """Remove the latest config from the stack."""
        if self.configs:
            return self.configs.pop()
        return None

    def negate_last_config(self, node_type: str) -> None:
        """Negate the last config."""
        if not self.configs:
            return

        last_config = self.pop_config()
        if not last_config:
            raise KconfigASTAnomalyError(node_type, "Missing last config!")

        self.push_config(sympy.Not(last_config))

    def record_field(self, field_name: str, field_type: str) -> None:
        """Add a field to this structure."""
        if not self.configs:
            guard = sympy.true
        elif len(self.configs) == 1:
            guard = sympy.simplify(self.configs[0])
        else:
            guard = sympy.simplify(sympy.And(*self.configs))

        self.fields.append(KconfigStructField(field_name, field_type, guard))

