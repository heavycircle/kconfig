# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/2.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.6.1] - 2026-08-28

### Fixed

- `kconfig module info`'s four tiers (`full`/`split-btf`/`vermagic-only`/
  `none`) were nowhere documented for a user -- not in `--help`, not in the
  table output itself, only in a source-level docstring. Now explained in
  both: the command's `--help` text, and a caption under the rendered table.

## [1.6.0] - 2026-08-28

### Added

- New `kconfig module info -m <modules>` command reporting each compiled
  module/vmlinux file's BTF/DWARF/vermagic introspection capabilities
  (`full`, `split-btf`, `vermagic-only`, or `none`) -- the first piece of
  supporting modules that lack BTF/DWARF debug info entirely.
- `pahole` invocation now retries with `--btf_base <vmlinux>` when a bare
  attempt fails, recovering modules built with `CONFIG_DEBUG_INFO_BTF_MODULES`
  (distilled BTF deltas against the vmlinux they shipped with) that previously
  looked indistinguishable from having no BTF at all.
- The `.modinfo` ELF section (vermagic, license, retpoline, ...) is now
  parsed directly via `readelf -p .modinfo`, with no dependency on the
  `modinfo` kmod tool.

### Fixed

- `cache_module_structs` no longer aborts the entire module cache build the
  first time one `.ko`/`vmlinux` file has no usable struct layout -- it's
  skipped with a warning and every other file still gets cached. Previously
  a single BTF/DWARF-less module in a directory would silently take down
  `struct analyze`/`signature analyze` for every other module alongside it.

## [1.5.0] - 2026-08-27

### Added

- `kconfig kernel fetch` gained `--allow-http`: falls back to plain HTTP for
  the kernel.org tarball if HTTPS fails to connect (e.g. sandbox mirrors that
  only serve HTTP). Off by default -- HTTPS is always tried first, and a
  failed HTTPS connection without the flag now reports a friendly error
  suggesting it instead of a raw `ConnectionError`.

## [1.4.0] - 2026-08-15

### Added

- New `kconfig signature` command group for analyzing a function/macro
  signature's CONFIG dependencies -- the workflow implied by a modversions
  CRC mismatch ("invalid version for `<function>`"): the signature itself
  didn't change, but a struct/union it references did, so the fix is to
  analyze *that*, not the function.
  - `signature find` -- identical to `symbol find` (finds the signature,
    reports its custom struct/union/typedef members); kept as its own
    top-level command since it's the natural first step of this workflow.
  - `signature configs` -- resolves each of a signature's custom struct/union
    members and reports every CONFIG guard found on their fields (recursively
    with `-r`), tagged with which member it was reached from. New
    `gather_struct_guards` (`core/analysis/structs.py`) -- unlike
    `gather_struct_evidence`, this is purely structural (reads `#ifdef`
    nesting straight off the parsed struct), so it works without a module
    directory at all.
  - `signature analyze` -- the module-comparison counterpart: resolves every
    custom member and analyzes them together against compiled module
    binaries, reusing the exact same evidence/constraint-solving pipeline as
    `struct analyze`. `analyze_struct_tree` was generalized into
    `analyze_structs(roots: dict[str, KconfigStruct], ...)`, which
    `analyze_struct_tree` now calls as a single-root special case (zero
    behavior change for `struct analyze`) -- a struct reached through more
    than one of a signature's members (directly, or nested under another
    member) is still only counted once.
  - New `get_signature_structs` (`core/structs/kernel.py`) resolves a list of
    member names into structs, skipping (with a warning) any that can't be
    found rather than aborting the whole batch -- shared by `configs` and
    `analyze`.
  - Verified for real: built and compiled a throwaway out-of-tree kernel
    module (`pahole`/`gcc`/`make` against this host's own kernel headers) with
    a `struct net_device` field guarded by `#ifdef CONFIG_NET_POLL_CONTROLLER`
    in the paired fake source tree, but omitted at compile time. `signature
    configs` correctly reported the guard tagged by member; `signature
    analyze` (both table and `--output json`) correctly inferred
    `CONFIG_NET_POLL_CONTROLLER: false` from the real compiled module, exactly
    matching real `pahole -C net_device` output. Also verified the
    multiple-custom-member case (`inet_select_addr(struct net_device *,
    struct sk_buff *, int)`) reports both members' guards independently.
- 4 new tests (`tests/test_signatures.py`) plus one in `tests/test_analysis.py`
  (cross-root evidence dedup in `analyze_structs`); 87 -> 97 tests passing (a
  couple of pre-existing tests picked up incidental coverage from the shared
  helpers). Ruff and mypy clean (same 32 pre-existing sympy findings, plus one
  new instance of the same already-accepted `Expr`/`BooleanTrue` identity-check
  pattern in the new `gather_struct_guards`, at parity with two existing
  instances in the same file).

## [1.3.0] - 2026-08-12

### Added

- `kconfig kernel fetch <version> --variant {debian,ubuntu}` -- fetches a
  distro's patched build of an *upstream* kernel.org version (e.g. "the
  Debian variant of 3.2.78") without needing to already know which distro
  release/exact package version shipped it, unlike `fetch-debian`/
  `fetch-ubuntu` (kept as-is, for when the exact package version is already
  known). Backed by two new archive clients in `core/cache/distro_kernel.py`:
  `find_snapshot_package`/`download_snapshot_package` (snapshot.debian.org,
  which keeps every version of every Debian source package ever archived,
  addressed by content hash) and `find_launchpad_package`/
  `download_launchpad_package` (Launchpad's publishing history -- Ubuntu has
  no byte-identical equivalent of snapshot.debian.org, but Launchpad keeps
  every published version across every series/pocket and its per-file
  download links are permanent librarian storage, serving the same purpose).
  A shared `_upstream_matches` handles the version-matching gap between the
  two distros: Debian tracks kernel.org's exact patch level as its upstream
  version, but Ubuntu pins a whole point-release series to `X.Y.0` for its
  entire lifetime regardless of patch level actually tracked -- a
  kernel.org-style `X.Y.Z` request falls back to matching that pin.

### Fixed

- `download_launchpad_package` had no content-integrity verification at all
  (unlike every other download path in this module) -- found via a real
  fetch that silently produced a corrupted, wrong-sized file with no error
  from anywhere in the request. Root cause: a Launchpad file that's already
  gzip-compressed on disk (e.g. a `.diff.gz`) served with `Content-Encoding:
  gzip` on top, which `requests`/urllib3 transparently (and silently)
  decompresses -- and Launchpad's caching proxy kept serving that
  gzip-transport-encoded response regardless of the request's own
  `Accept-Encoding`, so it couldn't be avoided by asking the server not to
  encode it. Fixed on the read side instead: `_stream_download` now reads via
  `response.raw` with `decode_content = False` to get the exact wire bytes,
  and `download_launchpad_package` verifies every downloaded file against
  the SHA256 the `.dsc` itself declares (parsed from its PGP clearsign
  wrapper) after every file is fetched.
- Launchpad's own connection setup proved noticeably slower and less
  reliable than the plain archive mirrors used elsewhere in this module
  (confirmed for real: cold connects routinely exceeded 10s, and a
  dozens-of-requests history scan hit transient 5xx/429/timeout responses
  partway through more than once). `_launchpad_get` now retries transient
  status codes *and* connection/read timeouts with exponential backoff, and
  uses a longer connect timeout than the rest of the module.

## [1.2.3] - 2026-08-11

### Fixed

- `resolve_typedef`/`get_typedef_configs` inferred a field's CONFIG guard
  (e.g. inferring `CONFIG_64BIT` from `Elf_Sym` matching pahole's
  `Elf64_Sym`) by ORing together the guard from *every* file in the tree
  that defines a same-named typedef/macro, with no filtering at all. This
  pulled in host-only build tooling (`scripts/mod/modpost.h`,
  `scripts/sorttable.h`, `scripts/recordmcount.h`,
  `tools/perf/util/genelf.h`, ...) that redefines common typedef names for
  its own unrelated build-time purposes -- never compiled into the kernel or
  a module, and not even real `CONFIG_*` symbols in several cases
  (`SORTTABLE_64`, `RECORD_MCOUNT_64`) -- plus every other architecture's own
  definition, not just the target one. The resulting "raw guard" shown in
  `struct analyze`'s evidence table could end up several terms larger than
  what's actually in the relevant kernel header. Fixed by excluding
  `scripts/`, `tools/`, `Documentation/`, `usr/` from the typedef-location
  cache, and filtering `arch/<other-arch>/` paths dynamically (against
  `kconfig_state.arch`) at lookup time -- mirrors the existing
  `_rank_file`/`wrong_arch` check used for struct location resolution.
  Verified for real: `Elf_Sym`'s candidate files against the cached
  `6.8.0-137.137` tree dropped from 8 (mixing in five irrelevant/host-only
  files) to 2 real kernel headers.

## [1.2.2] - 2026-08-06

### Fixed

- Kernel field declarations using a postfix attribute-like macro tree-sitter
  doesn't recognize (e.g. `atomic_long_t load_avg ____cacheline_aligned;`)
  had their real field name silently replaced by the macro token, since
  tree-sitter's C grammar recovers from the syntax error by wrapping the
  real name in an `ERROR` node and mistakenly treating the trailing macro as
  the declarator -- the field could then never match a real module field
  again. Also handles the same macro appearing *before* a proper declarator
  (e.g. `struct css_set __rcu *cgroups;`) without disturbing the correctly-
  parsed real declarator in that case.

## [1.2.1] - 2026-08-06

### Fixed

- A named nested struct's own fields incorrectly inherited the CONFIG guard
  active at the site that *referenced* it, even though the struct is
  independently defined (often in an unrelated file) and has no such guard
  in its own body -- e.g. `tty_port_operations` (genuinely unconditional)
  had every field falsely guarded by `CONFIG_SMP`, causing a false
  "Impossible layout" conflict. `_resolve_named_struct` no longer carries
  the referencing context's guard stack into the resolved struct's own
  parse.

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

[unreleased]: https://github.com/heavycircle/kconfig/compare/v1.2.2...HEAD
[1.2.2]: https://github.com/heavycircle/kconfig/compare/v1.2.1...v1.2.2
[1.2.1]: https://github.com/heavycircle/kconfig/compare/v1.2.0...v1.2.1
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
