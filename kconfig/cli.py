from __future__ import annotations

from pathlib import Path

from .parser import find_struct


def main() -> None:
    """Program entrypoint."""
    c_file = Path("linux-3.2.63/include/linux/sched.h").resolve()
    struct = find_struct(c_file, "sched_rt_entity")
    print(struct)
