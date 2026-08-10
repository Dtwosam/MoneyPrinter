# Printer V1 V2-9.8B — Post-DTW100 Ordinary Staging Residue Audit

Date: 2026-08-10

Verdict: `V2_9_8B_POST_DTW100_ORDINARY_STAGING_RESIDUE_AUDIT_PASS_REPAIR_REQUIRED`

## Scope

Read-only follow-up to the standard-four-hour operational rereadiness blocker. No source fetching, Scheduler runtime, DB mutation, authorization creation, Printer runtime, memory generation, retrieval, paper decision, position, trade event, audit, PnL, or 12h/24h capability was allowed.

## Evidence

The host audit at `57c3da1dc7c9adc94533cc69c14817bff1b6a1c1` found:

- tracked tree clean;
- zero active Printer process matches;
- zero authoritative DB open handles;
- zero authoritative DB writes;
- zero source calls;
- zero Scheduler runtime calls;
- no authorization created;
- seven historical entries under `~/PrinterOperations/v2-9-8/window-15m-one-shot-applications/.staging`.

Observed staging entries:

1. `V2_9_8B_WINDOW_15M_AUTH_20260802T112358Z-8c6effa328cd4a6fa05b5e2e016a273d` — empty, recognized authorization staging; matching canonical application exists with immutable application marker.
2. `V2_9_8B_WINDOW_15M_AUTH_20260803T204800Z-bae5318756834afa8218bc1874e712fd` — one `git-provenance-manifest.json`; recognized authorization staging; no canonical application; retained authorization package exists.
3. `V2_9_8B_WINDOW_15M_AUTH_20260804T214901Z-c1b4d8360ddb485dbbeadfb0f5773c46` — one `git-provenance-manifest.json`; matching canonical application exists with immutable application marker.
4. `V2_9_8B_WINDOW_15M_AUTH_20260806T005252Z-3778d27807ff40edac6e9ac961b78ea9` — one `git-provenance-manifest.json`; recognized authorization staging; no canonical application; retained local authorization package exists.
5. `V2_9_8B_WINDOW_15M_AUTH_20260806T005252Z-f47145e2df5b41bea6e44475c8c464ba` — one `git-provenance-manifest.json`; same recognized authorization identity; no canonical application.
6. `index-restoration-premarker` — empty non-authorization staging entry; no current tracked provenance reference found.
7. `sim-preauth` — empty non-authorization staging entry; no current tracked provenance reference found.

Every staging directory matched the wrapper cleanup *shape* (empty or only a regular `git-provenance-manifest.json`), but this audit does not authorize historical deletion and does not reinterpret old authorization consumption state.

The retained 2026-08-03 authorization is bound to old Git/DB state (migration 50 and an older DB fingerprint), so it cannot satisfy the current exact-state trust boundary. That fact is informative only; this lane does not mutate or reuse it.

## Decision

Do **not** delete the seven entries and do not weaken rereadiness to ignore them.

Use an exact allowlisted, fail-closed **atomic quarantine** repair that moves each observed staging directory outside the live `.staging` namespace while preserving its bytes and identity for forensic review. Canonical application directories, application markers, authorization packages, the authoritative DB, source/runtime state, and Scheduler state must remain untouched.

The repair must abort before mutation if any allowlisted entry has changed shape, if an unexpected staging entry appears, if the quarantine target already exists, or if any active Printer process/DB handle/lease lock is present.

## Money-usefulness contribution

Clearing stale wrapper staging safely removes a false operational-readiness blocker so the proven 15m→1h→4h memory path can eventually receive a bounded real proof without sacrificing historical evidence.

## What improves

- restores an unambiguous live wrapper staging namespace;
- preserves historical forensic artifacts instead of deleting them;
- keeps one-use authorization semantics fail-closed;
- enables a truthful rerun of standard-four-hour rereadiness after repair.

## Still locked

This audit unlocks nothing by itself. No standard-four-hour authorization or runtime is approved. WINDOW_12H/24H, retrieval, paper decisions, BUY/SELL/HOLD, positions, trade events, paper trade audits, PnL, wallets/private keys/real funds/live execution remain locked.

## Proof required before completion

1. static proof of exact allowlist and no DB/source/runtime/authorization mutation surface;
2. one bounded host quarantine execution with before/after fingerprints;
3. `.staging` becomes empty and quarantine contains exactly the seven preserved entries;
4. authoritative DB fingerprint unchanged, zero open handles/processes/locks;
5. standard-four-hour rereadiness rerun passes before any authorization preparation.

## Functionality Risks / Setbacks / Efficiency Blockers

- deleting manifest-bearing residue would destroy useful forensic evidence;
- broad recursive cleanup could touch canonical or future staging and is forbidden;
- ignoring `.staging` would weaken wrapper readiness semantics;
- unexplained new/changed residue must block rather than be swept into quarantine automatically;
- the repair requires one host-local filesystem mutation and therefore cannot be completed from GitHub alone.
