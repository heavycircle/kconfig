# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/2.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[unreleased]: https://github.com/heavycircle/kconfig/compare/v1.1.3...HEAD
[1.1.3]: https://github.com/heavycircle/kconfig/compare/v1.1.2...v1.1.3
[1.1.2]: https://github.com/heavycircle/kconfig/compare/v1.1.1...v1.1.2
[1.1.1]: https://github.com/heavycircle/kconfig/compare/v1.1.0...v1.1.1
[1.1.0]: https://github.com/heavycircle/kconfig/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/heavycircle/kconfig/compare/v0.1.0...v1.0.0
[0.1.0]: https://github.com/heavycircle/kconfig/releases/tag/v0.1.0
[SemVer]: https://semver.org
[@heavycircle]: https://github.com/heavycircle
