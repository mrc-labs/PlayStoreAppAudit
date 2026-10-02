# v2.2.0 final pre-release component freshness gate

Audit started **2026-10-02 CEST**, from exact main
`486ef062548cab2dee5960c38f02dbfbca226640` (PR #219 merge).
Before editing, the clean local checkout was synchronized by fast-forward;
local main, origin/main and live remote main all matched that SHA.
Starting Quality #628 / [36938816496](https://github.com/mrc-labs/PlayStoreAppAudit/actions/runs/36938816496)
was independently confirmed successful at that exact SHA. Work uses the new
`v2/final-freshness-2.2.0` branch, not the stale prep branch.

**Gate status: BLOCKED pending affected native diagnostics and final exact-head Quality.**
No release source SHA is frozen. Diagnostic packages cannot become final candidates.
The entry and preparation records remain historical evidence and are not substituted
for this new upstream audit. Issue #212 remains open; #147/#154/#209 are outside scope.

## Exact Python selection and checks

Python.org and the live official setup-python manifest independently select
**3.14.8**, the latest stable compatible 3.14 patch. Python 3.15 is still listed
as pre-release; no baseline migration is authorized. The 3.14.8 manifest has
standard Windows x64/ARM64, macOS x64/ARM64 and Ubuntu 24.04 x64/ARM64 builds,
plus the required same-patch Ubuntu 22.04 x64 archive. The compatibility helper
re-downloaded that official archive and checked release asset digest/size:
`python-3.14.8-linux-22.04-x64.tar.gz`, SHA-256
`3b6ca0860f3e23ca51901c78b7c945253ef35b9938dbc6529a5fea2183342363`.
Sources: [Python downloads](https://www.python.org/downloads/),
[3.14.8 release](https://www.python.org/downloads/release/python-3148/),
[manifest](https://github.com/actions/python-versions/blob/main/versions-manifest.json),
[official build](https://github.com/actions/python-versions/releases/tag/3.14.8-36806082737).

All **11 setup environments across nine workflows** now use full literals
(Quality's literal matrix entry is `3.14.8`). Every setup step is followed,
before its first Python consumer, by `platform.python_version()` equality to
`3.14.8`; PowerShell explicitly throws on nonzero exit and Bash uses
`set -euo pipefail`. Rolling `check-latest` was removed. Existing duplicated
build/Quality assertions were updated to full equality too.

| Location | Pinned environments / checks |
| --- | --- |
| `.github/workflows/quality.yml` | Literal matrix entry, immediate patch check and post-install Python/Qt check |
| `.github/workflows/build-windows-exe.yml` | Native x64/ARM64, immediate check, standard-GIL/architecture and post-install Python/Qt checks |
| `.github/workflows/build-linux.yml` | Both native 24.04 targets, immediate/pre-provisioning and post-install checks |
| `.github/workflows/build-macos.yml` | Both native macOS 26 targets, immediate and post-install checks |
| `.github/workflows/sign-windows.yml` | Ubuntu preflight, Windows signing environment and native verification environment (three setup steps); production signing is not dispatched |
| `.github/workflows/assemble-release.yml` | Production assembler environment; not dispatched |
| `.github/workflows/assemble-windows-engineering-release.yml` | Historical-profile engineering assembler environment; not dispatched |
| `.github/workflows/actions-retention.yml` | Maintenance environment, aligned for the release window |
| `.github/workflows/ui-style-audit.yml` | Manual audit environment, aligned for the release window |
| `.github/scripts/build_windows_standalone.ps1` | Full patch equality and existing 64-bit check |
| `.github/scripts/prepare_linux_x64_sysroot.sh` | Require resolved patch 3.14.8 before download, then verify the installed compatibility distribution equals it |

The generic official-distribution selector continues to accept a stable full
3.14 patch, but the release caller requires 3.14.8 and rejects another patch.
The controlled local assembly environment must also use and assert 3.14.8.
Regression coverage exercises the guard with 3.14.8, 3.14.7 and 3.14.9,
requiring success only for the selected patch, and inventories every setup step.

This is the deliberately small YAML-literal mechanism required by policy.
After v2.2 permanent closure, a focused development change must restore rolling
`3.14`/`check-latest: true` and the corresponding development assertions/tests
in these nine workflows and the two native helpers. Preserve the immutable
release source and this record. `requires-python >=3.14`, mypy's minor-language
target and the developer launcher stay language/development settings; they are
not final release runtime selectors. No new toolchain configuration system exists.

## Component inventory and ownership

The complete clean Python package inventory and OS/vendor/deprecation inventory
are recorded below as evidence is completed. Categories A/B/C/D follow
[RELEASE_COMPONENT_FRESHNESS.md](RELEASE_COMPONENT_FRESHNESS.md) exactly.
Freshness does not assert that a component is free of vulnerabilities.

Required controlled updates identified by fresh queries:

- Ruff **0.16.9 → 0.16.10** and mypy **2.3.1 → 2.4.0**, in `requirements-dev.txt`.
- Rust **1.98.1 → 1.99.0**, paired Cargo, in macOS Intel and Windows ARM64
  source-built cryptography paths. rustup 1.29.1 and OpenSSL selections remain current.
  Native Rust target and actual version checks are required; Intel's verified
  official rustup installer and deployment target are retained.

Stable Rust retains the required native targets and deployment compatibility:
[stable channel manifest](https://static.rust-lang.org/dist/channel-rust-stable.toml),
[macOS target support](https://doc.rust-lang.org/rustc/platform-support/apple-darwin.html),
[target matrix](https://doc.rust-lang.org/rustc/platform-support.html).
The macOS x86 target is tier 2; the required package diagnostic must validate it.

## Validation checkpoint

Clean local CPython **3.14.8 x64**, isolated environment/application data:

- Focused freshness/pinning/workflow/version/legal/ELF/retention checks: **41 passed**.
- Full pytest: **1652 passed, 9 skipped**, no warnings, normal exit.
- Compileall and canonical Quality Ruff scope on Ruff 0.16.10: PASS.
- Canonical Qt offscreen smoke, including status preservation: PASS.
- Guarded `main.py cli audit --help`, rejecting Qt/UI imports: PASS.
- Strict legal preflight with Nuitka 4.2.2 and source/license metadata: PASS.
- All nine workflow YAMLs, 17 Python helpers, 12 embedded Python blocks,
  Linux workflow Bash, sysroot/smoke Bash and PowerShell helper syntax: PASS.
- `git diff --check`: PASS.

Native diagnostics and final-head Quality remain required before PASS.
Local supporting snapshots/logs/archives are in ignored
`build/v2.2-final-freshness/`; durable conclusions belong in this document.
No tag, release, public asset, final assembly or production signing/notarization
operation is performed by this gate.
