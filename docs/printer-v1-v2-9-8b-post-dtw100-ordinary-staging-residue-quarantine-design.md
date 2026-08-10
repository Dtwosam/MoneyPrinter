# Printer V1 V2-9.8B — Ordinary Staging Residue Quarantine Repair Design

Date: 2026-08-10

Design verdict: `V2_9_8B_POST_DTW100_ORDINARY_STAGING_RESIDUE_QUARANTINE_DESIGN_PASS`

## Goal

Remove only the seven audited historical entries from the live ordinary wrapper `.staging` namespace without deleting or altering their forensic bytes.

## Canonical repair

Use one host-local Python helper with an exact seven-name allowlist and exact expected per-entry shape/hash where a manifest exists. The helper must:

1. verify exact repair branch/HEAD and clean tracked tree;
2. verify zero active Printer processes, zero DB open handles, zero campaign lease locks, and no stale wrapper environment;
3. fingerprint the authoritative DB before mutation and require the post-DTW100 trust anchor;
4. enumerate `.staging` and require its names to equal the seven-name allowlist exactly;
5. require each entry to be a real directory, never a symlink;
6. require each directory to contain exactly the audited contents:
   - three empty directories: the 2026-08-02 authorization staging, `index-restoration-premarker`, `sim-preauth`;
   - four manifest-bearing authorization staging directories with exact audited SHA-256 values;
7. create one new quarantine root outside both ordinary and standard wrapper application roots;
8. move each exact staging directory into that quarantine root using same-filesystem `os.rename` only;
9. never overwrite an existing quarantine target;
10. verify all seven moved directories preserve their exact pre-move contents/hashes;
11. verify live `.staging` is empty;
12. verify authoritative DB fingerprint is byte-for-byte unchanged and host quiescence remains clean;
13. emit one JSON repair report.

Quarantine root:

`~/PrinterOperations/v2-9-8/historical-wrapper-staging-quarantine/post-dtw100-ordinary-staging-residue`

The quarantine root is historical evidence only. It is not a wrapper application root and must never be treated as current authorization/application evidence.

## Exact allowlist

- `V2_9_8B_WINDOW_15M_AUTH_20260802T112358Z-8c6effa328cd4a6fa05b5e2e016a273d` — empty
- `V2_9_8B_WINDOW_15M_AUTH_20260803T204800Z-bae5318756834afa8218bc1874e712fd` — `git-provenance-manifest.json` SHA-256 `d1705ced3a8629ad87a2745a78ec0940b77494e0a6177b0e8192fe7659e098b1`
- `V2_9_8B_WINDOW_15M_AUTH_20260804T214901Z-c1b4d8360ddb485dbbeadfb0f5773c46` — `git-provenance-manifest.json` SHA-256 `76beaa565e716c82fd3cf4bf5a4e96206246bfc905029b5cf5d63196ffa84e90`
- `V2_9_8B_WINDOW_15M_AUTH_20260806T005252Z-3778d27807ff40edac6e9ac961b78ea9` — `git-provenance-manifest.json` SHA-256 `d010dc1b2e7f8d220cb81aefd2f8474d7b35de1cc4618f8daa2675ee8ff1d9a1`
- `V2_9_8B_WINDOW_15M_AUTH_20260806T005252Z-f47145e2df5b41bea6e44475c8c464ba` — `git-provenance-manifest.json` SHA-256 `47d76219c47e4dbe77d2901f089b3fc4604c6cd3835841188cfb479ca82ead04`
- `index-restoration-premarker` — empty
- `sim-preauth` — empty

## Failure semantics

Before the first rename, any mismatch blocks with zero filesystem mutations.

After the first rename, an unexpected rename failure is a repair interruption. The helper must not attempt recursive rollback or deletion. It must report exactly which names moved and which remain so a separate read-only recovery audit can decide the next action.

## Explicitly forbidden

- `rm`, `shutil.rmtree`, recursive delete, unlink of manifest bytes;
- canonical application mutation;
- application-marker mutation;
- authorization-package mutation;
- DB write/open for mutation;
- source fetching;
- Scheduler runtime;
- Printer runtime;
- authorization creation/consumption;
- 4h runtime;
- 12h/24h/retrieval/decision/trading capability changes.

## Verification

Minimum sufficient proof:

- `py_compile`;
- AST/static lock proving no delete/unlink/rmtree, no wrapper apply/run functions, no sqlite mutation API, no network client;
- exact allowlist and expected hashes asserted;
- exact implementation-file-only diff;
- host execution only after static proof;
- host post-repair rereadiness rerun.

## Money-usefulness contribution

This is operational hygiene, not strategy logic: it removes stale launch-boundary noise so the real 4h memory pipeline can be tested under trustworthy one-use authorization semantics.

## What improves

The live ordinary staging namespace becomes clean while all historical residue survives in a non-live quarantine location.

## Still locked

No authorization/runtime/retrieval/decision/position/trading capability is unlocked by this design or repair.

## Functionality Risks / Setbacks / Efficiency Blockers

- cross-filesystem moves would break atomicity; quarantine must remain under the same `~/PrinterOperations/v2-9-8` filesystem tree;
- any unexpected staging entry or changed manifest hash blocks the repair;
- partial rename failure requires a new read-only audit rather than improvisational cleanup;
- quarantine is permanent historical evidence unless a later explicit retention lane decides otherwise.
