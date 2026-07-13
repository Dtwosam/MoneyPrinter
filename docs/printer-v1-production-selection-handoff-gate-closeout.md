# Printer V1 Production Selection Handoff Gate Closeout

Status: `UNASSISTED_SAFE_STOP_COMPOSITION_BLOCKED`

Date: 2026-07-13

Base commit: `8ddb7ad Prove unassisted discovery and selection`

## Audit Finding

The production discovery command previously composed and reported a classifier
quota view after selecting candidates, but it persisted every accepted active
candidate into tracking and pending scheduler work even when quota failed. It
also did not call the existing token/pair cross-batch cooldown helpers or persist
an auditable selection batch. Rotation state therefore was not connected to the
production front door.

The existing classifiers, quota thresholds, Source Governor, cooldown helpers,
selection-batch schema, and rotation persistence were already sufficient. The
repair required only wiring and ordering.

## Repair

The production order is now:

1. governed source execution and normalization;
2. within-response and cross-response dedup/STNP filtering;
3. existing discovery eligibility and audit-only separation;
4. token and pair selection cooldown gates;
5. classifier-derived bounded quota composition;
6. auditable selection-batch persistence;
7. active tracking/scheduler handoff only when quota passes;
8. rotation update only for active selected items in a valid assembled batch.

Quota failure persists a `REJECTED` selection batch and rejected item rows, but
creates no tracking queue or scheduler rows. Governed active discovery evidence
is retained without active handoff so later exact prior/current A4 evidence is
not lost. Audit-only WATCH_ONLY/D1 candidates remain outside token, pair,
tracking, scheduler, and rotation persistence.

No quota, threshold, A3/A4 classifier, scoring, ranking, or financial behavior
was changed. No migration was added.

## Deterministic Proofs

Focused tests proved:

- a classifier-generated `{A1, A3, B1, B2, B3, D1}` composition passes;
- five active candidates receive tracking and rotation, while audit-only D1
  satisfies quota without active or rotation work;
- an A1-only quota failure creates one rejected selection batch and zero active
  handoffs or rotation rows;
- a preexisting token/pair selection is rejected by cooldown before quota;
- the remaining valid composition can still pass and hand off;
- single A1/A3/A4 evidence remains auditable without bypassing quota;
- A3 T3 and A4 prior/current provenance remain intact;
- controlled discovery, audit-only, cooldown, and core selection regressions
  remain passing.

Test results:

- production handoff/group quota: 6 passed;
- core selection batch: 120 passed;
- cooldown/rotation: 80 passed;
- audit-only handoff: 91 passed, 4 skipped;
- controlled discovery plus A3/A4: 22 passed.

## Single Unassisted Live Run

Exactly one production discovery run used a fresh isolated schema-only DB:

`data/printer_v1_unassisted_handoff_8ddb7ad.sqlite3`

Bounds:

- operator approved;
- Solana only;
- GeckoTerminal only;
- `geckoterminal_new_pool_discovery` plus
  `geckoterminal_trending_pool_reference`;
- max candidates 10;
- max source requests 2;
- five-second source timeout;
- no mint list, fixture, manual candidate choice, enrichment, retry, scheduler
  execution, or post-start code change.

The command completed in 4.05 seconds. Source Governor recorded two requests,
two `COMPLETE / CLEAN_DATA` responses, and zero failures. Each channel returned
20 candidates, for 40 normalized candidates total.

## Live Candidate And Integrity Results

- candidates seen/normalized: 40;
- active candidates reaching cooldown: 10;
- cooldown eligible: 10;
- cooldown rejected: 0;
- WATCH_ONLY audit-only pool: 6;
- D1 audit-only candidates: 0;
- unresolved within-response STNP rejections: 7;
- additional pre-persistence rejections, including WATCH_ONLY and cap: 23;
- governed discovery-evidence rows persisted without active handoff: 10.

No prior rotation rows existed in the fresh DB, so all ten token/pair cooldown
checks passed. The proof demonstrates that the gates ran; it does not claim a
live cooldown rejection.

## Full Proposed Composition

The bounded composer could fill only eight of ten requested positions:

`{A1: 2, B5: 2, C1: 2, C2: 2}`

| Mint | Pair | Channel | Bucket | Proposed role/result |
|---|---|---|---|---|
| `9wh2UMzu8FfvVukER2bcbifqh8q7veCgL4LhwU3Ypump` | `CzoUTzEf9FnyFU64KvqumdvRko4fEBfUjmbHC37dka6w` | new pool | B5 | WATCH_ONLY quota support; rejected with batch |
| `2De4LJ92ETjx3pFYbtfcnBsnKW3N87aJ6wEkZ5XsHBc7` | `84n2s1Z1UcQDDq1w7FKL1uBU7Mm9g6RGpHT37JZXgKH4` | new pool | B5 | active proposal; rejected with batch |
| `AZeQxpyRbMprTYkjwARtZZ968pSUDtwYbMjsrvBqmrHa` | `ETFidpvpvELk1idAzy3geUJ9MDJC241EYhfsGQUojhuR` | new pool | A1 | active proposal; rejected with batch |
| `6SPUEBJRYqXfSUXTrMgv6tbLfjxT5GdZQzwvj4yHpump` | `7semSfgEhatYjDYvQEBeZtNeSSvQhAyF34naxkLzvpUR` | new pool | C2 | active proposal; rejected with batch |
| `AqR23MfUjVLD5YNGxkgr1W4fR4942LhXFrcmMXrriSNa` | `5PyuqhaQxVdhnwH9PS7urvssE3raxAUrG2qQGiRfd4eb` | new pool | C1 | active proposal; rejected with batch |
| `EF1khfP7sa8GFoTvNEEa6bpfPLmKt227XDQX9QeUpump` | `FT47jRzhpBdyFt9dywryv8ZvWWJtBx9TgCHRi9o4pfTP` | new pool | C1 | active proposal; rejected with batch |
| `FCCajB8h3mMejbiYCW1yM49StP6uEJuf6mdaho7opump` | `4uiu3yHaXKkq7pWmHDsPcUEE51cHkC7zxo9jqnjyqzFt` | new pool | C2 | active proposal; rejected with batch |
| `B6Y39ov8wxYEuymcwuET5yLTejzAczutDgid3ktZGu8Q` | `DtZbtQCoZEF3cdna27EmmSSrAcoZjK9jZHQ4yXQXhThy` | new pool | A1 | active proposal; rejected with batch |

Three additional A1 candidates were rejected by the winner/composition cap:

- `82R7EVyeq9u9XEofejubBvMvTRQcKpwtx6JjExpmCjqs` / `8domNDEMBuNuyLxEvnVctN2LXw4d4GFASrmegZnfSNDw`;
- `4ko5tSr5o3H4v1sFtjTSd9MPUW7yx5AFCpkNPoL6pump` / `68nVMrVPyxGJGbGH2P92E93SYhJcbe6QociZrqoqdjcB`;
- `9cRCn9rGT8V2imeM2BaKs13yhMEais3ruM3rPvTGpump` / `6e7V9eegCHw997T72MxgwwJipZ6GJyZF8NvjkzT1rvpN`.

Five further WATCH_ONLY candidates were rejected by the bounded composition.
All retained source request/response identity in selection-batch audit rows.

## Quota Result

Quota hard gate: failed.

Violations:

- `GROUP_A_PRESENT_BUT_NO_TRAP_FAILURE_BUCKET`;
- `MISSING_D1_DEAD_TOKEN_REQUIRED_FOR_6PLUS_BATCH`;
- `GROUP_B_SHARE_BELOW_MIN_30_PERCENT`;
- `MISSING_GROUP_B_DECAY_REQUIRED_FOR_6PLUS_BATCH`;
- `SELECTION_TARGET_NOT_FILLED`.

Auditable result:

- batch ID: `5cef16c0-3bd1-4629-8a6e-dd55d73f9a07`;
- batch status: `REJECTED`;
- candidate pool: 16;
- selected items: 0;
- rejected items: 16;
- active handoffs: 0;
- audit-only active handoffs: 0;
- rotation updates: 0.

## Proof DB Deltas

| Table | Delta |
|---|---:|
| source requests / responses / failures | +2 / +2 / 0 |
| tokens / pairs / discovery evidence | +10 / +10 / +10 |
| selection batches / items | +1 / +16 |
| tracking queue / scheduler jobs | 0 / 0 |
| selection rotation state | 0 |
| snapshots / memory windows / fingerprints | 0 / 0 / 0 |
| retrieval queries / matches | 0 / 0 |
| paper decisions / positions | 0 / 0 |
| trade events / paper audits / paper audit reports | 0 / 0 / 0 |
| PnL | no PnL table; no financial rows created |

No scheduler job was created or executed. The persistent DB SHA-256 remained:

`97DB9A15CC464D86137CBBB0DD0A4EF1880E9F4E231FB41E8B22CA09FB177FBB`

## Verdict

`UNASSISTED_SAFE_STOP_COMPOSITION_BLOCKED`

The production front door now enforces cooldown before quota, records a failed
selection audibly, blocks all active handoffs on quota failure, and leaves
rotation unchanged. The live market sample lacked a valid composition, and
Printer stopped safely without intervention or retry.

This proves the repaired handoff safety boundary. It does not authorize V2-3,
memory, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits,
PnL, wallets, keys, paid APIs, scoring, ranking, confidence, or weighted logic.
