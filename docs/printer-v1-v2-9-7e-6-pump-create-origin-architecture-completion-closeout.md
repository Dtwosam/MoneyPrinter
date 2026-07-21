# V2-9.7E.6 Pump Create Origin Architecture Completion Closeout

**Status:** PASS
**Lane:** V2-9.7E.6 — Pump Create Contract Reconciliation and Origin Architecture Completion
**Date:** 2026-07-21
**Baseline HEAD:** `c2ecff6cb7c1b8c80dd520a907710cd50f76ed00`

## Final Verdict

`V2_9_7E_6_PUMP_CREATE_CONTRACT_AND_ORIGIN_ARCHITECTURE_PASS`

The Pump origin subsystem is complete. Two distinct supported finalized Pump
creates were captured live under the newly adopted `create_v2` contract,
persisted to the durable registry, and resolved by exact mint in a later
simulated discovery cycle with zero source calls.

## Todo / Checklist

- [x] Verify HEAD `c2ecff6…`.
- [x] Phase 1 — reconcile working tree against SHA-256 backup.
- [x] Phase 2 — separate the four unsupported outcomes; prove independently.
- [x] Phase 3 — one bounded live classification capture.
- [x] Classification gate — Option A satisfied.
- [x] Phase 4 — pin contract, adopt `create_v2`, restore architecture.
- [x] Phase 5 — offline proof; fresh external backup.
- [x] Phase 6 — one final bounded live proof.
- [x] Documentation, 5A correction, commit.

## 1. Working-tree and backup reconciliation

All 7 surviving untracked V2-9.7E.5 artifacts hash-matched the external backup
exactly. The 3 tracked files reverted by `c2ecff6` were restored from the
verified backup and re-proved (40 tests green). Backup self-check: 12/12 `OK`.
No stash, no preservation branch, no WIP commit. Detail in the design document.

A fresh hash-verified backup was created after offline proof and before the
final live proof at `~/Desktop/printer-v1-v2-9-7e-6-backup-20260721/`
(12 files + the pinned IDL bytes + manifest + SHA-256 + status + diff).

## 2. Live classification evidence

One bounded capture, `2026-07-21T20:21:46Z` → `20:21:57Z`, 13 operations,
0 retries, 0 rotations.

| Signal | Value |
|---|---:|
| Signature rows / finalized | 16 / 16 |
| Transactions inspected | 12 |
| Bodies returned / unavailable | 10 / 2 |
| Envelope `ACCEPTED` | **10** |
| Envelope rejected | **0** |
| `create_v2` `d6904cec5f8b31b4` | **10** |
| legacy `create` | 0 |
| unknown create layout | 0 |

This resolved the V2-9.7E.5A ambiguity: the transaction-version gate never
fired, and live create traffic is entirely `create_v2`.

## 3. Pinned contract revision and hash

`pump-fun/pump-public-docs` @ `9c82f61cb711b044a17f770ab8ce9f9bdf78f333`,
`idl/pump.json`, 169,632 bytes, SHA-256
`b90bc471327f671449271d5d1d42354d1fae6f5a06502f5834459a3108138e49` — **matches**
the hash already pinned in the repository's Solana Builder contract and in
`PUMP_IDL_SHA256`. Retrieved at the exact commit, never a moving `main`.

## 4. Final supported create layouts

| Layout | Discriminator | Accounts | Token program |
|---|---|---:|---|
| `PUMP_CREATE_V1` (legacy, preserved) | `181ec828051c0777` | 14 | SPL Token |
| `PUMP_CREATE_V2` (newly adopted) | `d6904cec5f8b31b4` | 16 | **Token-2022** |

Legacy assumptions were not copied: `create_v2` has no metadata or rent account,
different account ordering, mayhem PDAs, Token-2022-seeded ATA, and two extra
args including `OptionBool` (a one-byte single-field struct, not a standard
Option). Full table in the design document.

## 5. Restored architecture and retired paths

Restored unchanged from V2-9.7E.5: signature-anchored acquisition on the
create-index address, no `getSlot` cutoff, no whole-program polling, no
campaign-time archaeology, durable immutable registry, durable cursor,
registry-first origin resolution, retired-path guards, Governor/Scheduler
ownership, worst case 15 underlying operations.

Retired paths remain inaccessible: `run_fixture_cycle` and
`run_mint_origin_lookup` raise `RetiredPrimaryPathError` on a primary claim and
are not imported by `combined_executor` (asserted in the final proof preflight,
all 14 implementation checks true).

## 6. Migration and persistence

Migration 036 (uncommitted at lane start, so extended rather than duplicated)
now records `create_layout`, `create_discriminator_hex`, and `token_program`
alongside the existing immutable confirmed-origin columns. A confirmed origin
states exactly which adopted contract established it.

## 7. Files changed

| File | Change |
|---|---|
| `src/printer_v1/sources/pumpfun_direct.py` | four-outcome classification; pinned `create_v2` args, accounts, PDAs; layout dispatch and labelling |
| `src/printer_v1/sources/pumpfun_origin.py` | split counters; layout provenance in registry writes and lookups |
| `src/printer_v1/sources/registry.py` | restored V2-9.7E.5 request kinds |
| `src/printer_v1/discovery/combined_executor.py` | restored V2-9.7E.5 registry-first integration |
| `migrations/036_pumpfun_finalized_origin_registry.sql` | restored + layout provenance columns/index |
| `tests/test_v2_9_7e_6_pump_create_classification.py` | new — 21 classification and adoption proofs |
| `tests/test_v2_9_7e_5_pump_origin_acquisition_architecture.py` | restored; updated for split codes |
| `tests/test_v2_9_7d_7b_4a…`, `…4c…`, `…4g…` | split-code updates; two unrealistic non-create fixtures corrected |
| `docs/printer-v1-v2-9-7e-6-pump-create-contract-reconciliation-design.md` | new |
| `docs/printer-v1-v2-9-7e-6-pump-create-origin-architecture-completion-closeout.md` | new |
| `docs/printer-v1-v2-9-7e-5-…-reset-closeout.md` | dated correction appended only |
| `operator-runs/v2-9-7e-6-classification/`, `operator-runs/v2-9-7e-6-final-proof/` | harnesses + redacted results |

Not touched: gates, selection, cooldown, freshness, liquidity/activity,
two-or-none, memory windows, Tracker's 180-second contract, retrieval,
decisions, positions, trades, audits, PnL, wallet/signing.

## 8. Focused tests

| Suite | Result |
|---|---|
| `test_v2_9_7e_6_pump_create_classification` (new) | **21 passed** |
| `test_v2_9_7e_5_pump_origin_acquisition_architecture` | 40 passed |
| `test_v2_9_7d_7b_4a_direct_pump_adapter` | passed |
| `test_v2_9_7e_4c_direct_pump_create_capture_productivity` | passed |
| `test_v2_9_7e_4g_cutoff_historical_origin` | passed |
| `test_pumpfun_direct_create_contract_fixture` | passed |
| Combined decoder set | **98 passed** |
| Discovery/persistence/replay/Governor/cleanup set (7 suites) | **56 passed + 8 subtests** |
| Supervision/scheduler/gate set (3 suites) | 78 passed + 46 subtests, 1 pre-existing failure (§13) |

Coverage includes: both layouts decoded and labelled independently; Token-2022
vs SPL Token identity handling; exact account ordering; wrong fixed identity,
PDA, ATA, program, account-count, and trailing-byte rejection; unsupported
transaction version; unknown create layout; non-create traffic; failed and
unavailable transactions; finalized-only admission; duplicates and conflicting
duplicates; cursor restart and bounded backfill; registry persistence,
immutability, and layout provenance; exact-mint lookup in a later cycle;
provider labels cannot establish origin; retired paths inaccessible;
request/RPC ceilings; deterministic replay; terminal cleanup; Governor and
Scheduler bypass prevention.

Risk-based verification per AGENTS.md: no broad repository suite was run, as no
broad shared owner changed.

## 9. Final live proof

One live proof, `2026-07-21T20:49:42Z` → `20:49:47Z`.

| Requirement | Result |
|---|---|
| Capture attempts | **1** (HTTP 200, 0.6 s, 16 rows) |
| Signature rows / admitted | 16 / 15 |
| Decode attempts | 2 |
| **Distinct supported finalized creates** | **2** ✅ |
| **Create density** | **1.0** (2 decodes → 2 creates) |
| At least one under newly adopted layout | **yes** — both `PUMP_CREATE_V2` ✅ |
| Mint prefixes | `76z7GnWs…`, `Dt2aCSWK…` |
| Signature prefixes | `3VXvNg5P…`, `5Dra2hqC…` |
| Slots | 434375045, 434375058 |
| Program | `6EF8rrec…` (single) |
| Account identity validated by decoder | yes |
| Registry rows written | **2** |
| Later-cycle exact-mint resolution | **2/2**, with signature, slot, program, prospective-mode, and **layout** match |
| Zero-source replay | **true** |
| Deterministic `canonical()` | **stable** |
| Provider-label origin | **false** |
| Retired-path activation | **none** |
| Underlying operations | **3 / 15** |
| Duration | 4 s / 300 s |
| Storage | 2,183,168 B / 8 MiB |
| Retries / rotations / reconnects | 0 / 0 / 0 |
| Cleanup: jobs, leases, subscriptions, child processes | 0 / 0 / 0 / 0 |
| Preflight: migration 036, integrity, FK | applied, `ok`, 0 violations |

Create density of **1.0** independently confirms the create-index address is
create-exclusive — the assumption V2-9.7E.5A could only mark as *indicated*.

## 10. Money-usefulness contribution

* Restores Pump origin acquisition to working order: the subsystem now produces
  confirmed exact-mint finalized origins from live traffic, which is the
  precondition for two-slot activation and therefore for any memory growth.
* Cost fell to **3 underlying RPC operations** for two confirmed origins, versus
  a 45-operation worst case in the pre-reset architecture — freeing budget for
  memory-window work.
* Origins are permanent facts: each mint is verified at most once ever, and
  later cycles resolve them with zero source calls.
* Eliminates a class of silent evidence corruption: a mis-parsed `OptionBool` or
  a legacy-assumed Token program would have produced wrong or absent origins
  rather than an honest failure.
* Ends the 4A–4H → 5 → 5A blocker chain with measured evidence rather than
  another patch.

No origin was invented, no activation forced, no pilot claimed.

## 11. What remains locked

Full V2-9.7E pilot; V2-9.7F; V2-9.8; retrieval; paper decisions; BUY/SELL/HOLD;
positions; trades; audits; PnL; wallet, private keys, signing, real funds, live
execution; paid APIs; scoring, ranking, confidence, weighted logic; embeddings
and vectors; Source Governor and Central Scheduler bypass; freshness, liquidity,
activity, cooldown, and selection rules; two-or-none activation;
`WINDOW_5M_MICRO_EVENT` support-only status.

## 12. Exact remaining external limitations

1. Public-RPC retention still bounds how far any boundary walk can recover;
   deep gaps stay honestly `GAPPED`.
2. Free-tier throttling can return null transaction bodies
   (`UNAVAILABLE_HISTORY`); 2 of 12 did so in the classification capture. The
   zero-retry policy declines to re-request.
3. The pinned IDL may lag the deployed program — an upstream-reported risk. Both
   layouts are validated against pinned bytes; a future layout change surfaces
   as `UNSUPPORTED_PUMP_CREATE_LAYOUT`, not as a wrong origin.
4. Continuity remains `UNKNOWN` on cold start by design.
5. Mayhem-program PDAs are validated structurally; the mayhem program's own
   semantics are outside this contract.

## 13. Functionality Risks / Setbacks / Efficiency Blockers

1. **Pre-existing failure (documented, deferred):**
   `test_v2_9_4_durable_supervision::test_schema_and_launcher_contracts_are_canonical_and_locked`
   asserts `latest_migration == "030_v2_9_proof_run_supervision.sql"`. It fails
   at baseline `c2ecff6` **with migration 036 removed entirely** — the repository
   already carries migrations 031–035, so the assertion predates them. Confirmed
   against baseline and deferred per AGENTS.md; it is not a lane regression, but
   it will keep failing until that stale assertion is updated.
2. **Risk:** `create_v2` is now the sole observed live layout. Legacy `create`
   support is retained but is no longer exercised by live traffic, so its
   regression value is fixture-only.
3. **Risk:** `OptionBool` is encoded as one byte per the pinned IDL. If upstream
   ever changes it to a standard Option, decoding fails closed
   (`MALFORMED_TRANSACTION`) rather than silently mis-parsing — acceptable, but
   it would halt origin capture until re-adopted.
4. **Setback:** two fixtures in 4C/4G were unrealistic (non-create bodies that
   still referenced `mint_authority`) and had to be corrected. Their original
   assertions were preserved in intent; only the fixture shape changed.
5. **Efficiency note:** the final proof used 3 of 15 permitted operations
   because create density is 1.0. The 15-operation ceiling now carries
   substantial headroom and was not raised.
6. No defect was found that would justify weakening finalized origin, raising a
   ceiling, adding retries, or adopting paid infrastructure.

## 14. Readiness for one later V2-9.7E pilot rerun

**READY**, with one scope caveat.

Every precondition that blocked the pilot is now satisfied: supported finalized
creates are captured live, origins persist durably and immutably, exact-mint
resolution needs no historical rediscovery and no RPC, replay is deterministic,
and ownership and ceilings hold.

Caveat: this lane proved the **origin subsystem** end to end, not the full
memory-factory pilot. The pilot additionally exercises secondary enrichment,
the fixed eligibility gates, uniform selection, two-slot handoff, and the 15m
window — none of which this lane changed, and none of which it re-proved. A
pilot rerun is authorised to proceed on the strength of a working origin
subsystem, and remains subject to its own gates.

The full V2-9.7E pilot was **not** run in this lane and is **not** claimed to
have passed.

## 15. Stop boundary

V2-9.7E.6 ends PASS. No tag. V2-9.7F, V2-9.8, retrieval, paper decisions,
BUY/SELL/HOLD, positions, trades, audits, and PnL were not begun.
