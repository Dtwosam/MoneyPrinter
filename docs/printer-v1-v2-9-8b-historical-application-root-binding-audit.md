# Printer V1 V2-9.8B — Historical Application-Root Binding Audit

## Verdict

`V2_9_8B_HISTORICAL_APPLICATION_ROOT_BINDING_PASS`

## Baseline

- Repair design: `4c1706b057a1cff93f6fd8a7bc52de4c299d00e0`
- Historical execution: `20260814T172224Z-490856f405bf`
- Authoritative DB SHA before/after audit: `5e830af41d58325d3f9e521f1b95f697b8151113cb783cf05a2a776e204639bc`
- Historical lease SHA before/after audit: `71389ed839964c1892751ff1ca323f24fa7c1523bd9b39dcbdee18d03370f8a4`

The audit was read-only. No reconciliation, source fetching, Scheduler/runtime execution, memory generation, artifact copying/moving/deletion/symlinking, DB mutation, or lease mutation occurred.

## Exact consumed application root

The audit SHA-scanned all of `~/PrinterOperations`. Eighteen roots contained all five application filenames, but exactly one root matched all five pinned SHA-256 identities:

`/Users/Dtwo1/PrinterOperations/v2-9-8/four-token-proof-one-shot-applications/V2_9_8B_FOUR_TOKEN_PROOF_AUTH_20260814T171249Z_0022b4dc`

The path was resolved with `pwd -P`; no symlink indirection exists.

Pinned application artifacts:

- `application-marker.json` — `1e0038b4515156244dad586d6d90692857dc53ab12f7df67d4b03a981ea4665c`
- `git-provenance-manifest.json` — `ee76043850f7569fe21d05f2770e51ac64e5de36f39362c962f09f7b7ae73f18`
- `wrapper-terminal.json` — `36312b244b335fa951e3ed9aa6799ce2e3cb15a8a2c46a6e127409e40108ccc3`
- `child-terminal.json` — `5b96652d5473120d28f1e1730c1843715fa27888af85640a774a00b0d2acd0fd`
- `child-stderr.txt` — `eab9a9236a3735658915db3a8e5bff934ae65a46d8b81caf61f6176fc4b7f504`

The historical execution root remains:

`/Users/Dtwo1/PrinterOperations/v2-9-8/20260814T172224Z-490856f405bf`

and owns:

- `terminal-summary.json` — `21d0e6fe4046e69b15a3239caea26703c280a8303302dc85c3bd63ec3a41d7c1`
- canonical `campaign.lease.lock`
- pre-campaign backup / restore-rehearsal evidence
- reports directory

This proves the two-root topology that the current one-root validator cannot represent.

## Inventory preservation

Application root remained byte-for-byte/inventory-identical before and after inspection. It contained six entries: the five pinned application artifacts plus empty `child-stdout.txt`; all were read-only and unchanged in size, ownership, permissions, and timestamps.

Historical execution root remained byte-for-byte/inventory-identical before and after inspection, containing the canonical lease, pre-campaign backup, restore rehearsal, reports directory, and terminal summary.

## Runtime/process note

An initial broad process-string count self-detected the operator's own parent shell because its argv contained Printer text. Isolated inspection found zero operational Printer processes, and the canonical process probe returned `()`. No runtime was started. This is operator-measurement contamination only and does not justify weakening the production process guard.

## Design gate

The exact root-binding prerequisite from the dual-artifact-root repair design is satisfied. Implementation may proceed with the already-approved narrow interface:

- execution `artifact_root` remains canonical lease/execution evidence owner;
- explicit read-only `application_artifact_root` owns the five application artifacts;
- existing six SHA pins remain mandatory;
- no generic artifact map/resolver;
- no evidence reconstruction;
- no capability unlock.

## Money-usefulness contribution

This removes ambiguity about the real consumed evidence topology while preserving original evidence unchanged, improving confidence in bounded historical cleanup without adding trading capability.

## What remains locked

Authoritative reconciliation, fresh campaigns, source fetching, Scheduler/runtime execution, memory generation, longer-window activation, retrieval, paper decisions, BUY/SELL/HOLD, positions, trade events/audits, PnL, live wallet/private keys/real funds, paid APIs, scoring/ranking/confidence/weighted logic, embeddings, and vectors remain locked.