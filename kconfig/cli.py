from __future__ import annotations

from pathlib import Path

from .parser import find_struct, find_struct_configs
from .utils import KconfigError


def action(file: str, name: str) -> None:
    """Do the action."""
    c_file = Path(f"linux-3.2.63/include/{file}").resolve()

    struct = find_struct(c_file, name)
    configs = find_struct_configs(struct.body)

    print(f"Found {len(configs)} inside '{struct.name}'!")
    for config in configs:
        print(" >> config:", config.name)
        for field in config.fields:
            print("\t >> field:", field)


def main() -> None:
    """Program entrypoint."""
    try:
        action("linux/module.h", "module")
    except KconfigError as e:
        print(f"Kconfig Error: {e}")
        raise
    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f"Unknown Error: {e}")
        raise
