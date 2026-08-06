# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/2.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.2.0] - 2026-08-06

### Added

- `-a`/`--arch` option for `struct find`/`struct analyze`, to disambiguate
  structs defined once per architecture (`arch/*/include/asm/*.h`) instead of
  silently picking whichever one happens to tiebreak first.

### Fixed

- `_rank_file` picked an arbitrary, frequently wrong architecture's struct
  definition (e.g. `arch/parisc/.../thread_info.h` for an x86_64 vmlinux) by
  tiebreaking on line number alone, with no architecture awareness at all --
  a real, previously-undiscovered cause of false "Impossible layout" results.
- `find_struct_declaration` (module-side) referenced the kernel source
  directory instead of the module directory in its "cannot find" error.
- Anonymous structs no longer trigger (and then catch) a doomed module
  lookup by name -- they're skipped up front instead of via a misleading
  "Cannot find definition for ''" warning.
- `gather_struct_evidence` no longer aborts recursion into a struct's nested
  fields just because that struct's own evidence couldn't be determined
  (anonymous, or missing from the module) -- a named struct reachable behind
  such a struct was previously silently dropped entirely.
- True anonymous C11 members (no variable name at all) no longer trigger an
  "Uncontrollable field missing" warning for their synthetic placeholder
  name, which could never match a real module field by construction --
  this also kept leaking into `--output json`'s stdout ahead of the document.

## [1.1.4] - 2026-08-06

### Added

- search-debian and search-ubuntu to search for ABIs across codenames.
- Output JSON for analysis.

## [1.1.3] - 2026-08-06

### Added

- fetch-debian and fetch-ubuntu APIs for downloading Ubuntu/Debian patches.
- list-debian and list-ubuntu to get specific ABI versions for downloading.

## [1.1.2] - 2026-08-06

### Added

- Added Pytest and Coverage checking.

## [1.1.1] - 2026-08-04

### Changed

- Fixed all Ruff issues.
- Updated gather_struct_evidence to split across many functions.

## [1.1.0] - 2026-08-04

### Added

- A dispatching agent for processing node types.
- Removing unused code and TODOs.

### Changed

- Changed code tree to make it make more sense.
- Made the state singleton a global variable to pass around.

## [1.0.0] - 2026-05-16

### Added

- Open-sourced a base working version of this project.
- Defined a CLI that can print structures, find signatures and their custom
  structures, find type definitions, and analyze structures against known
  kernel modules.
- This project is mostly tested on Linux 3.3 and Linux 5.15. Other versions
  require testing to uncover issues in parsing the kernel.

### Changed

- Start following [SemVer] properly.

## [0.1.0] - 2026-06-15

### Added

- Created a base Python project for running tree-sitter queries on the Linux
  kernel source.

[unreleased]: https://github.com/heavycircle/kconfig/compare/v1.2.0...HEAD
[1.2.0]: https://github.com/heavycircle/kconfig/compare/v1.1.4...v1.2.0
[1.1.4]: https://github.com/heavycircle/kconfig/compare/v1.1.3...v1.1.4
[1.1.3]: https://github.com/heavycircle/kconfig/compare/v1.1.2...v1.1.3
[1.1.2]: https://github.com/heavycircle/kconfig/compare/v1.1.1...v1.1.2
[1.1.1]: https://github.com/heavycircle/kconfig/compare/v1.1.0...v1.1.1
[1.1.0]: https://github.com/heavycircle/kconfig/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/heavycircle/kconfig/compare/v0.1.0...v1.0.0
[0.1.0]: https://github.com/heavycircle/kconfig/releases/tag/v0.1.0
[SemVer]: https://semver.org
[@heavycircle]: https://github.com/heavycircle
