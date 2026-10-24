# ADR-0022: Reactivate isolated source builds for Exodus

## Status

Accepted for the owner-directed local source and compile slice, 2026-10-24.

## Context

The previous engine archive and local-reference-only decision is retained
in ADR-0021. A registry export does not satisfy the owner's actual goal:
a source-built runtime that can be selected by Exodus for Mac and eventually
run an installed Xbox DirectX 12 game.

The parent relayed direct human direction to retire the outdated Calimocho
constitution, reuse the name, and reactivate the project. That instruction
is distinct from an earlier multiple-choice response whose human origin
was not established. The direct mandate authorizes source upgrades and
bounded isolated builds, not licence acceptance or security bypasses.

The old CodeWeavers 26.1.0 / Wine 11.0 build always applied a custom D3D11
shim and launcher environment. A clean WineHQ candidate must not silently
inherit that implementation. Neither a newer Wine version nor an existing
GPTK binary establishes compatibility between them.

## Decision

Permit isolated builds from verified WineHQ or CodeWeavers source. Preserve
the existing exporter work, but do not treat it as the completed runtime.
Keep historical engine scripts unchanged while probing a clean candidate.
Pin a Git source to its exact verified upstream commit and record its
tree identity; verify downloaded archive bytes with SHA-256 before use.

The initial diagnostic has a finite 30-minute configure and small-target
compile budget. Use installed compilers, parser tools, SDK and make.
Capture actual configure diagnostics before proposing dependency installs.
Missing Intel Homebrew is a constraint of the old script, not proof that
upstream Wine cannot compile.

COR-36 / REQ-69 subsequently authorizes continued bounded source builds,
including isolated source-built dependencies. WineHQ 11.20 is the current
upstream target (official tag rechecked on 2026-10-24). CodeWeavers 26.3
contains Wine 11.0, so use it only to establish a coherent integration
baseline before forward-porting the measured boundary.

REQ-70's primary-source inspection found a public x86_64 D3DMetal callback
table, Cocoa layer and client-surface integration, plus ntdll non-native
code-region and calling-convention support. Preserve those coupled seams
when adapting to WineHQ's newer driver types and surface lifecycle. Do not
copy an old whole driver over current upstream or infer compatibility
from three source files or matching structure sizes.

The retained CodeWeavers FreeType tree lacks its `dlg` submodule. Build the
complete, checksum-pinned official FreeType release instead, into an owned
x86_64 prefix. Do not link the installed arm64 Homebrew library into an
x86_64 runtime. Keep failed attempts and receipts.

The coherent CW build needs one explicit source fix: its Vulkan override
unconditionally references `SONAME_LIBVULKAN` when configure found no Vulkan
loader. Guard that absent macro, log the unavailable loader, and return.
This permits compilation; it neither supplies Vulkan nor substitutes for
D3DMetal. The patch and all transformed source identities belong in receipts.

Keep Direct3D 11 as a separate possible runtime record. Public DXMT source
describes Direct3D 10/11 translation and is pinned as a research reference
in `versions.json`; it is not a Direct3D 12 replacement and has not been
built or qualified. DX11 parity must not delay the current-Wine DX12 path.

No global packages, runtime installation, signing or quarantine changes,
Apple payload copying, terms acceptance, credentials, game launch, or
existing prefix/save mutation are authorized in this slice. There is no
public push, merge, release or CI operation. The parent owns GitHub archive
settings and runtime/game coordination. Future execution must use the
existing Ode engine adapter and preserve explicit route identity.

## Consequences

Compilation can now provide real source compatibility evidence instead of
only registry labels. Missing dependencies and ABI integration remain
explicit results, not grounds for silent fallback.

This is not a whole-engine qualification, Subnautica 2 success, an engine
switch/save-reload result, or distribution rights clearance. REQ-33/43
remain open and REQ-53 remains Program-owned. The program has one canonical
requirements document, `dragos-core projects/ode-to-x/SPEC.md`.

An eventual startup/self-check is part of REQ-69 acceptance, but this lane's
current execution hold still forbids launching Wine. REQ-71 route admission
and REQ-38 human consent are separate prerequisites to any game attempt.
