# V2-9.7E.6 Pump Create Contract Reconciliation Design

**Status:** ADOPTED
**Lane:** V2-9.7E.6 — Pump Create Contract Reconciliation and Origin Architecture Completion
**Boundary:** classification separation + contract adoption; no cutoff, pagination, historical-depth, or public-RPC architecture change
**Date:** 2026-07-21
**Baseline HEAD:** `c2ecff6cb7c1b8c80dd520a907710cd50f76ed00`

## 1. Working-tree reconciliation

`c2ecff6` committed only the V2-9.7E.5 architecture and blocker closeout, and
reverted the three tracked production files. Seven untracked lane artifacts
survived.

Every surviving file was hash-compared against the external SHA-256 backup
`~/Desktop/printer-v1-v2-9-7e-5-backup-20260721/`:

| File | Result |
|---|---|
| `migrations/036_pumpfun_finalized_origin_registry.sql` | MATCH |
| `src/printer_v1/sources/pumpfun_origin.py` | MATCH |
| `tests/test_v2_9_7e_5_pump_origin_acquisition_architecture.py` | MATCH |
| `operator-runs/v2-9-7e-5-live-proof/*` (2) | MATCH |
| `operator-runs/v2-9-7e-5a-decisive-reproof/*` (2) | MATCH |

Backup self-check: all 12 entries `OK`.

Tracked files reverted by `c2ecff6` (`combined_executor.py`,
`pumpfun_direct.py`, `registry.py`) correctly differed from the backup and were
restored from it, then re-verified: **40 offline tests green**, confirming the
restored implementation is the same one V2-9.7E.5 proved.

Reconciliation is exact and safe. No preservation branch or WIP commit was made.

## 2. Root cause carried forward from V2-9.7E.5A

V2-9.7E.5A proved the acquisition architecture works live (16/16 finalized rows
admitted, zero `POST_CUTOFF`, 0.5 s query) but produced zero supported creates:
10 decodes failed as `UNSUPPORTED_VERSION`.

That code was raised from **two** unrelated branches —
`pumpfun_direct.py:544` (transaction envelope version) and `:593`
(`create_v2` discriminator) — so the evidence could not identify the cause. The
lane could not distinguish "Solana returned a transaction shape we reject" from
"Pump changed its create instruction".

**This ambiguity, not RPC viability, was the unresolved blocker.**

## 3. Phase 2 — outcome separation

`UNSUPPORTED_VERSION` is replaced by four fail-closed outcomes:

| Outcome | Meaning | Raised at |
|---|---|---|
| `UNSUPPORTED_TRANSACTION_VERSION` | Solana envelope `version` not `legacy`/`0` | envelope gate, before any Pump parsing |
| `UNSUPPORTED_PUMP_CREATE_V2` | `create_v2` discriminator, pre-adoption | after envelope accepted |
| `UNSUPPORTED_PUMP_CREATE_LAYOUT` | Pump instruction touching the create-exclusive mint authority with an unrecognised discriminator | after envelope accepted |
| `NOT_SUPPORTED_CREATE` | no Pump create-family instruction (ordinary buy/sell) | after envelope accepted |

**Ordering rule:** transaction-envelope validation is strictly prior to and
independent of Pump instruction classification. A rejected envelope can never be
reported as a layout problem, and vice versa.

`UNSUPPORTED_PUMP_CREATE_LAYOUT` is distinguished from `NOT_SUPPORTED_CREATE` by
whether the instruction references `mint_authority`
(`TSLvdd1pWpHVjahSpsvCXUbgwsL3JAcvokwaKt1eokM`), which is create-exclusive.

Counters were split accordingly: `create_v2_count`,
`unsupported_transaction_version_count`, `unsupported_create_layout_count`,
`non_create_count`. No outcome is conflated in any report.

### 3.1 Two pre-existing fixtures corrected

`test_v2_9_7e_4c` and `test_v2_9_7e_4g` built their "non-create" fixture by
swapping only the discriminator on a full create transaction, leaving the
14-account create list — including `mint_authority` — intact. Real buy/sell
traffic never references `mint_authority`, so those fixtures were unrealistic
and the new classifier correctly reported them as unknown create layouts. The
**fixtures** were corrected (account index 1 dropped); the classifier was not
weakened.

## 4. Phase 3 — live classification evidence

One bounded capture, `2026-07-21T20:21:46Z` → `20:21:57Z`, 13 underlying
operations, 0 retries.

| Signal | Value |
|---|---|
| Signature rows | 16 |
| Transactions inspected | 12 |
| Bodies returned / unavailable | 10 / 2 |
| Envelope `ACCEPTED` | **10** |
| Envelope `UNSUPPORTED_TRANSACTION_VERSION` | **0** |
| `create_v2` discriminator `d6904cec5f8b31b4` | **10** |
| legacy `create` | **0** |
| unknown create layout touching mint authority | **0** |

**Conclusion.** The transaction-version gate never fired. Every accepted
transaction on the create-index address contained a Pump `create_v2`
instruction. Live Pump create traffic is `create_v2`, and the index address is
confirmed create-exclusive.

Other observed Pump discriminators (`66063d1201daebea` ×6 and four singletons)
never touched `mint_authority` and are correctly ordinary traffic.

## 5. Classification gate — Option A satisfied

| Requirement | Evidence |
|---|---|
| Accepted Solana transaction envelope | 10 `ACCEPTED`, 0 rejected |
| `create_v2` discriminator observed | 10 occurrences |
| Exact official pinned `create_v2` contract available and verifiable | see §6 |

## 6. Pinned contract revision

| Field | Value |
|---|---|
| Repository | `https://github.com/pump-fun/pump-public-docs` |
| Commit | `9c82f61cb711b044a17f770ab8ce9f9bdf78f333` |
| Path | `idl/pump.json` |
| Bytes | 169,632 |
| SHA-256 | `b90bc471327f671449271d5d1d42354d1fae6f5a06502f5834459a3108138e49` |
| Verification | **matches** the hash already pinned in `pump-fun-direct-creation-discovery-contract.md` and in `PUMP_IDL_SHA256` |

Retrieved at the exact pinned commit, not a moving `main`. The adopted layout is
read from these verified bytes only.

## 7. Adopted `create_v2` layout

Discriminator `[214, 144, 76, 236, 95, 139, 49, 180]` = `d6904cec5f8b31b4`.

**16 accounts** (legacy `create` has 14):

| # | Account | Constraint |
|---:|---|---|
| 0 | `mint` | signer, writable |
| 1 | `mint_authority` | PDA `["mint-authority"]` → `TSLvdd1p…` |
| 2 | `bonding_curve` | PDA `["bonding-curve", mint]` |
| 3 | `associated_bonding_curve` | ATA PDA `[bonding_curve, token_program, mint]` — **token program is Token-2022** |
| 4 | `global` | PDA `["global"]` → `4wTV1Ymi…` |
| 5 | `user` | signer, writable |
| 6 | `system_program` | `11111111111111111111111111111111` |
| 7 | `token_program` | **`TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb` (Token-2022)** |
| 8 | `associated_token_program` | `ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL` |
| 9 | `mayhem_program_id` | `MAyhSmzXzV1pTf7LsNkrNwkWKTo4ougAJ1PPg47MD4e` |
| 10 | `global_params` | PDA `["global-params"]` under mayhem program |
| 11 | `sol_vault` | PDA `["sol-vault"]` under mayhem program |
| 12 | `mayhem_state` | PDA `["mayhem-state", mint]` under mayhem program |
| 13 | `mayhem_token_vault` | writable |
| 14 | `event_authority` | PDA `["__event_authority"]` → `Ce6TQqeH…` |
| 15 | `program` | `6EF8rrec…` |

Args (Borsh): `name`, `symbol`, `uri`, `creator: pubkey`,
`is_mayhem_mode: bool`, `is_cashback_enabled: OptionBool`.

`OptionBool` is a **single-field struct over `bool`** in the pinned IDL — one
byte, not an Option tag plus payload. Encoding it as a standard Option would
mis-parse every create_v2.

### 7.1 Legacy assumptions explicitly NOT carried over

| Legacy `create` | `create_v2` |
|---|---|
| SPL Token `TokenkegQ…` | **Token-2022 `TokenzQd…`** |
| `mpl_token_metadata` account (5) | **absent** |
| `metadata` PDA (6) | **absent** |
| `rent` sysvar (11) | **absent** |
| `user` at index 7 | **index 5** |
| `event_authority` at 12, `program` at 13 | **14, 15** |
| ATA seeds use SPL Token | **ATA seeds use Token-2022** |
| no mayhem accounts | 4 mayhem accounts/PDAs |

Each was verified against the pinned IDL rather than assumed. All three fixed
PDAs (`mint-authority`, `global`, `__event_authority`) were derived locally and
matched the constants already pinned in the decoder.

**`mint_authority` is identical across both layouts**, so the create-index
address indexes `create` and `create_v2` alike — the V2-9.7E.5 acquisition
architecture needs no change.

## 8. Persistence

Migration 036 (still uncommitted, so extended rather than duplicated) gains:

* `create_layout` — `PUMP_CREATE_V1` | `PUMP_CREATE_V2`, CHECK-constrained;
* `create_discriminator_hex` — 16 hex chars;
* `token_program` — the layout's token program.

A confirmed origin therefore records exactly which adopted contract established
it. Immutability, batch-independence, and confirmed-only semantics are unchanged.

## 9. Unchanged

Acquisition architecture, index address, request kinds, ceilings (worst case 15
underlying operations), registry immutability, cursor semantics, retired-path
guards, Governor/Scheduler ownership, gates, selection, two-or-none,
memory-window rules, and all financial locks.

`create_v2` adoption changes **what can be decoded**, not how it is acquired,
budgeted, persisted, or gated.
