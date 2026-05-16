from pathlib import Path

from .parser import run_query


def main() -> None:
    c_file = Path("linux-3.2.63/include/linux/sched.h").resolve()
    query_file = Path("./kconfig/queries/ifdef-struct.scm").resolve()
    run_query(c_file, query_file)
