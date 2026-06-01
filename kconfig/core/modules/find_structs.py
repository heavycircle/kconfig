from __future__ import annotations

from typing import TYPE_CHECKING

from elftools.elf.elffile import ELFFile

from kconfig.utils import KconfigError, KconfigFileError


if TYPE_CHECKING:
    from pathlib import Path

ELF_TAGS = {
    "struct": "structure_type",
    "enum": "enumeration_type",
    "union": "union_type",
    "typedef": "typedef",
}


def find_items(module: Path, category: str) -> list[str]:
    """Find items inside a kernel module.

    Args:
        module (Path): Path to the kernel module to search.
        category (str): Category to search for.

    Returns:
        list[str]: List of structs inside the module.

    """
    if category not in ELF_TAGS:
        raise KconfigError(f"Invalid Argument ({__name__.rsplit('.', maxsplit=1)[1]}): {category}")
    if not (module.exists() and module.is_file()):
        raise KconfigFileError(f"No such file: {module.name}")

    names: list[str] = []
    with module.open("rb") as f:
        elf = ELFFile(f)
        if not elf.has_dwarf_info():
            return names

        dwarf = elf.get_dwarf_info()
        for cu in dwarf.iter_CUs():
            for die in cu.iter_DIEs():
                if die.tag != "DW_TAG_structure_type":
                    continue

                attr = die.attributes.get("DW_AT_name")
                if attr:
                    names.append(attr.value.decode("utf-8"))

    return names
