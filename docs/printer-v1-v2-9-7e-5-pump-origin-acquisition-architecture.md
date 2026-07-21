# V2-9.7E.5 Pump Origin Acquisition Architecture

**Status:** FROZEN (design)
**Lane:** V2-9.7E.5 — Pump Origin Acquisition Architecture Reset
**Boundary:** architecture decision + specification freeze; no eligibility, freshness, cooldown, selection, tracking, retrieval, or financial change
**Date:** 2026-07-21
**Baseline HEAD:** `3396dfc6833c15f96e2dd45aa0a405858e1cb290`

This document supersedes the acquisition halves of V2-9.7D.7B.3A/4A, V2-9.7E.4B,
and V2-9.7E.4F. It does not supersede the Pump `create` **decoder** contract,
which is retained unchanged.

---

## 1. Phase 1 — Whole-path root-cause audit

### 1.1 Path traced

```
Pump creation occurs
  -> RPC/source observation        getSignaturesForAddress(PUMP_PROGRAM_ID)
  -> finality confirmation         getSlot(finalized) frozen as immutable cutoff
  -> decoding                      getTransaction -> decode_finalized_create
  -> continuity/cursor             FinalizedCursor(boundary, CONTIGUOUS|GAPPED|UNKNOWN)
  -> durable origin persistence    printer_discovery_origin_verifications
  -> discovery merge               CombinedPumpfunCampaignExecutor._merge
  -> exact-mint origin verification run_mint_origin_lookup (historical archaeology)
  -> eligibility gate              GATE_ORDER "PUMPFUN_ORIGIN"
  -> two-slot selection            _select / _persist_selection_and_handoff
```

Owners read: `src/printer_v1/sources/pumpfun_direct.py`,
`src/printer_v1/discovery/combined_executor.py`,
`src/printer_v1/discovery/persistence.py`,
`src/printer_v1/sources/registry.py`, `src/printer_v1/sources/governor.py`,
`migrations/034_discovery_persistence_reconciliation.sql`.

Evidence read: V2-9.7C design, V2-9.7D bounded implementation closeout, both
V2-9.7E blocked pilot closeouts, V2-9.7E.3 eligibility-funnel audit,
V2-9.7E.4A–4H audit/design/repair/blocked-proof set.

### 1.2 Findings

#### RC-1 — The immutable `getSlot` cutoff is an incoherent anchor (ARCHITECTURE DEFECT)

`run_fixture_cycle` freezes one `getSlot(commitment=finalized)` value and rejects
every signature row with `slot > cutoff` as `POST_CUTOFF`.

`api.mainnet-beta.solana.com` is a **multi-backend pool**. The node answering
`getSlot` and the node answering `getSignaturesForAddress` are different
machines with independent finalized views. A signature row can therefore be
genuinely finalized and still carry `slot > cutoff`.

The cutoff adds **no** safety that the row does not already carry:
`getSignaturesForAddress` at `commitment=finalized` returns only finalized
signatures, and each row carries its own `confirmationStatus` and `slot`. The
cutoff is a redundant second opinion sampled from a different backend, and when
it loses the race it discards the entire usable sample.

4D: 32/32 rows `POST_CUTOFF`, 0 decodes. 4H (after the 4G pagination repair):
32/32 rows `POST_CUTOFF`, 0 decodes. **The 4G repair could not have worked** —
it added a second older page, but the defect is not pagination depth, it is that
the admission predicate is anchored to a value from an unrelated backend.

Class: **architecture defect.** Not a public-RPC capability limitation — the RPC
returned correct finalized data on both calls; the local contract discarded it.

#### RC-2 — Whole-program polling has ~1% create density (ARCHITECTURE DEFECT)

`getSignaturesForAddress(PUMP_PROGRAM_ID)` returns **all** Pump program activity.
Buys and sells outnumber creates by roughly two orders of magnitude. The
signature list carries no instruction discriminator, so create/non-create can be
separated only by spending one `getTransaction` per signature.

With `BACKFILL_PAGE_SIZE=16`, `BACKFILL_PAGE_CEILING=2` and
`TRANSACTION_DECODE_CEILING=16`, the expected create yield of a perfect cycle is
well below one. Even with RC-1 fixed, whole-program polling cannot reach the
two-create bar inside the 45-operation budget.

Class: **architecture defect** (wrong index address), compounded by a
**request-budget limitation** if the address is not changed.

#### RC-3 — Origin evidence is batch-scoped, so every cycle re-does archaeology (ARCHITECTURE DEFECT)

`printer_discovery_origin_verifications` is keyed
`UNIQUE (discovery_batch_id, merged_candidate_id)` with a `NOT NULL` FK to
`printer_discovery_batches`. A confirmed origin is therefore an artifact **of one
batch**. A later cycle creates a new batch and a new `merged_candidate_id`, and
has no supported way to read the earlier confirmation.

Consequence: eligibility for an aged mint depends on rediscovering its creation
transaction at campaign time — `run_mint_origin_lookup` walking mint history
backwards. That is the archaeology path, and it is on the critical activation
path today.

Class: **architecture defect** (no durable prospective registry).

#### RC-4 — Historical mint lookup is not bounded for aged candidates (RETENTION + BUDGET LIMITATION)

A Pump `create` includes the mint account, so it does appear in
`getSignaturesForAddress(mint)`. But for a *trending* mint the create sits behind
thousands of buys/sells. 4G raised the walk to 3 pages x 16 rows = 48 newest
signatures; the create for a hours-old trending mint is far older than that.

4H observed the compounding failure: 4 of 7 mints returned
`UNAVAILABLE_HISTORY` after HTTP 429 under mint fan-out, with zero-retry policy
correctly declining to retry.

Class: **historical-retention limitation** + **request-budget limitation**.
Unbounded in the general case. Cannot be the primary activation path.

#### RC-5 — The seven pilot mints are not a representative activation path (MARKET-YIELD LIMITATION)

The 4H mint set was loaded from a prior blocked pilot DB and was hours old at
proof time. Aged secondary-provider mints are the *hardest* possible origin
target and are not what a healthy prospective pipeline consumes. Binding the
PASS bar to them measures archaeology, not acquisition.

Class: **market-yield limitation** of the test design, not of the machine.

#### RC-6 — `logsSubscribe` primary capture is not viable on free public RPC (RPC CAPABILITY LIMITATION)

`run_fixture_cycle` models a `logsSubscribe`/`logsUnsubscribe` session.
`api.mainnet-beta.solana.com` does not offer a usable free WebSocket
subscription endpoint for sustained third-party use, and a subscription is a
long-lived loop — exactly what AGENTS.md forbids outside Scheduler ownership.
It also delivers *processed*-commitment logs, so every notification would still
need a finalized `getTransaction` confirmation, giving no request saving.

Class: **public-RPC capability limitation.**

#### RC-7 — No bypass path found (clean)

`_run_direct_lane` is the only caller of `run_fixture_cycle`;
`_origin_and_pumpswap` is the only caller of `run_mint_origin_lookup`. Both go
through `FixtureOperationPort`, which validates Governor kind and Scheduler
work-type before consumption. Secondary providers set
`pumpfun_origin_status = PUMPFUN_ORIGIN_UNVERIFIED` and the `PUMPFUN_ORIGIN`
gate requires `origin_state == "CONFIRMED"`; provider labels never establish
origin. No independent polling, retry, or reconnect loop exists.

Class: **no defect.** This property must be preserved, not repaired.

### 1.3 Classification summary

| # | Root cause | Class |
|---|---|---|
| RC-1 | Cross-backend `getSlot` cutoff as admission anchor | architecture defect |
| RC-2 | Whole-program address has ~1% create density | architecture defect |
| RC-3 | Origin evidence batch-scoped, not durable | architecture defect |
| RC-4 | Aged-mint history walk unbounded | historical-retention + request-budget |
| RC-5 | Seven aged pilot mints as PASS dependency | market-yield (test design) |
| RC-6 | `logsSubscribe` primary capture | public-RPC capability |
| RC-7 | Ownership / bypass | none — preserve |

**Nothing in RC-1..RC-3 is fixable by another pagination or ceiling patch.** The
admission anchor, the index address, and the persistence scope are all wrong.

---

## 2. Phase 2 — Architecture decision

### 2.1 The decisive observation

The pinned Pump `create` contract
(`tests/fixtures/pumpfun_direct_create_contract.json`, IDL sha256
`b90bc4…8e49`, repo commit `9c82f61…f333`) fixes the create account list:

```
0 mint   1 mint_authority   2 bonding_curve   3 associated_bonding_curve
4 global 5 mpl_token_metadata 6 metadata 7 user 8 system_program
9 token_program 10 associated_token_program 11 rent 12 event_authority 13 program
```

`mint_authority` = `TSLvdd1pWpHVjahSpsvCXUbgwsL3JAcvokwaKt1eokM` is already
enforced as a fixed identity by `_validate_account_identities`.

`mint_authority` is the PDA that signs the initial supply mint during `create`.
It is **not** an account of `buy` or `sell`, which operate on an already-minted
supply through the bonding curve. It is therefore a **create-exclusive index
address**: `getSignaturesForAddress(mint_authority)` enumerates Pump creates and
essentially nothing else.

This moves create density from roughly 1% to roughly 100% at **identical** RPC
cost, and it is the difference between an architecture that cannot reach two
creates inside 45 operations and one that reaches them in a handful.

### 2.2 Options compared

| Criterion | A — signature-anchored finalized polling | B — bounded prospective live capture | C — hybrid prospective registry |
|---|---|---|---|
| Coherent finality | **yes** — the finalized signature row is the anchor; single backend response | no — logs are `processed`; needs a second finalized call anyway | partial — inherits B's leg |
| Durable prospective evidence | yes, with the registry (§3.9) | yes | yes |
| Bounded recovery | **yes** — deterministic `before`/`until` cursor walk | no — reconnect/backfill is a loop with no natural bound | partial |
| Create productivity | **high** on the create-exclusive index address | high in principle, unobtainable in practice (RC-6) | high |
| RPC cost | **lowest** — 1 signature page + N confirmations | subscription + equal confirmations | highest — two acquisition legs |
| Deterministic replay | **yes** — pages and transactions are ordered values | no — notification arrival order is not reproducible | partial |
| No campaign-time archaeology | yes, via registry | yes, via registry | yes |
| Free-public-RPC viability | **yes** | **no** (RC-6) | no — depends on B's leg |
| Competing primary paths | one | one | **two** — forbidden by the lane |

### 2.3 Decision

> **Selected primary architecture: Option A — Signature-anchored finalized
> polling, anchored on the create-exclusive Pump mint-authority index address.**

**Option B is rejected** on RC-6: no viable free public WebSocket, `processed`
commitment, unbounded reconnect loop, and non-deterministic replay.

**Option C is rejected as specified** because its primary leg is B's live
capture, and because it deliberately retains two competing primary acquisition
paths — which this lane forbids.

Option C's **persistence** contribution is adopted independently: the durable
exact-mint finalized-origin registry (§3.9) is part of this specification. A
registry is *storage*, not *acquisition* — adopting it does not create a second
primary acquisition path. There remains exactly one way for an origin to be
established: a finalized supported Pump `create` decoded from a transaction
reached through the signature-anchored path.

Option A is prospective by construction: each cycle polls the newest creates and
writes them to the registry, so a mint's origin is captured **at creation time**,
long before any secondary provider surfaces it as a trending candidate. This is
what removes archaeology from the critical path.

### 2.4 Retired paths

| Retired | Replacement | Why no longer authoritative |
|---|---|---|
| `getSlot` immutable cutoff as admission anchor | the finalized signature row itself | RC-1 — cross-backend incoherence; adds no safety the row lacks |
| `POST_CUTOFF` rejection in the primary path | `MISSING_FINALITY` on `confirmationStatus != finalized` | RC-1 — rejects genuinely finalized evidence |
| `getSignaturesForAddress(PUMP_PROGRAM_ID)` as primary | `getSignaturesForAddress(mint_authority)` | RC-2 — ~1% create density cannot reach the bar in budget |
| `logsSubscribe` / `logsUnsubscribe` session | none | RC-6 — not viable on free public RPC |
| `run_mint_origin_lookup` on the critical activation path | registry lookup | RC-3/RC-4 — unbounded, retention-dependent |
| Aged pilot mints as PASS dependency | prospective capture of fresh creates | RC-5 — measures archaeology, not acquisition |

**Reactivation prevention.** `run_fixture_cycle` and `run_mint_origin_lookup` are
not deleted (4A–4H evidence must remain reproducible), but:

* `combined_executor` no longer calls either on the primary path;
* both raise `RetiredPrimaryPathError` if invoked with
  `primary_path=True`, and are annotated `SUPPORT_ONLY`;
* `run_mint_origin_lookup` is reachable only when the registry misses **and**
  the caller passes an explicit `allow_support_only_history=True`, which the
  campaign executor never sets;
* a test asserts `combined_executor` imports neither symbol on the primary path.

---

## 3. Phase 3 — Frozen specification

### 3.1 Index address and anchor model

```
PUMP_CREATE_INDEX_ADDRESS = "TSLvdd1pWpHVjahSpsvCXUbgwsL3JAcvokwaKt1eokM"
```

The **anchor** of one acquisition cycle is the newest admitted finalized
signature row, expressed as `CursorBoundary(slot, signature)`. There is no
independently sampled slot. Admission requires, from the row alone:

1. `confirmationStatus == "finalized"` — else `MISSING_FINALITY`;
2. `err is None` — else `FAILED_TRANSACTION` (non-fault; market noise);
3. `slot` is a non-negative int and `signature` a non-empty string.

Rows are ordered `(slot, signature)` ascending for deterministic decode order.

### 3.2 Cold start

`prior_cursor.boundary is None` → the cycle reads exactly one page from the tip,
admits what it finds, decodes up to the ceiling, and terminalizes with
`continuity = UNKNOWN`. The boundary **is** advanced on cold start (this differs
from the retired path, which refused to advance and so could never leave cold
start). `UNKNOWN` records that the interval before this page was never observed;
it does not invalidate the observations inside the page.

### 3.3 High-water mark and cursor

`FinalizedOriginCursor(boundary, continuity)` persists per index address.
`boundary` advances to the newest admitted row of the cycle whenever at least
one row was admitted. It never moves backwards: a page whose newest row is older
than the stored boundary leaves the boundary unchanged and is reported
`STALE_PAGE`.

### 3.4 Reconnect / backfill

There is no connection, therefore no reconnect. Continuity is recovered by
passing `until=<stored boundary signature>` on the next page request. Outcomes:

* page contains the boundary signature → `CONTIGUOUS`, interval closed;
* page is full (`len(rows) == PAGE_SIZE`) and does not contain the boundary →
  more history exists than one page; walk older with `before=<oldest row>` up to
  `PAGE_CEILING`; if still not closed → `GAPPED`;
* page is short and does not contain the boundary → `GAPPED` (boundary aged out
  of retention);
* page is empty → `UNAVAILABLE`, boundary unchanged.

`GAPPED` and `UNAVAILABLE` are honest states. They never fabricate `CONTIGUOUS`,
and they do not discard the observations actually captured.

### 3.5 Duplicates and forks

Same signature seen twice with identical `(slot, confirmationStatus, err)` →
counted in `duplicate_signatures`, admitted once. Same signature with a
**different** slot → both copies dropped, `CONFLICTING_DUPLICATE` recorded,
continuity forced `GAPPED`. A row that is not `finalized` is never admitted, so a
fork cannot enter the registry.

### 3.6 Finalized transaction confirmation

Every admitted signature is confirmed by exactly one `getTransaction` before it
can become an origin. Decoding is unchanged: `decode_finalized_create` from
V2-9.7D.7B.3A, with the pinned discriminator, the 14-account identity check, the
bonding-curve / ATA / metadata PDA derivations, and the `create_event`
cross-check.

`cutoff_slot` is passed as the row's own slot, so the retired `POST_CUTOFF`
branch is unreachable from the primary path by construction.

### 3.7 `create_v2`

`CREATE_V2_DISCRIMINATOR` remains **blocked**, surfacing `UNSUPPORTED_VERSION`.
Detected occurrences are counted and reported. Not adopted in this lane.

### 3.8 Confirmed-origin linkage

A confirmed origin carries exactly:

| Field | Source |
|---|---|
| `mint_identity` | create account[0], PDA-validated |
| `transaction_signature` | signature row, cross-checked against `transaction.signatures[0]` |
| `slot` | transaction, cross-checked against the row |
| `block_time` | transaction; missing → `UNAVAILABLE_HISTORY` |
| `program_id` | pinned `6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P` |
| `bonding_curve`, `associated_bonding_curve` | create accounts 2, 3, PDA-derived |
| `creator_address` | create args, `OBSERVED_EVIDENCE_ONLY` scope |
| `provenance` | `contract_version`, `idl_sha256`, `index_address`, `acquisition_mode` |

No raw RPC payload is stored — only a `sha256` of the canonical decoded payload.

### 3.9 Durable prospective origin registry

**One minimal migration** (`036`) — required because
`printer_discovery_origin_verifications` cannot retain a cross-cycle origin
(RC-3): it is `NOT NULL` FK'd to a batch and uniquely keyed by
`(discovery_batch_id, merged_candidate_id)`.

```sql
CREATE TABLE printer_pumpfun_finalized_origin_registry (
    mint_identity          TEXT PRIMARY KEY,
    transaction_signature  TEXT NOT NULL UNIQUE,
    slot                   INTEGER NOT NULL CHECK (slot >= 0),
    block_time             INTEGER NOT NULL,
    program_id             TEXT NOT NULL CHECK (program_id = '6EF8...F6P'),
    bonding_curve          TEXT NOT NULL,
    associated_bonding_curve TEXT NOT NULL,
    creator_address        TEXT NOT NULL,
    creator_evidence_scope TEXT NOT NULL CHECK (... = 'OBSERVED_EVIDENCE_ONLY'),
    origin_state           TEXT NOT NULL CHECK (origin_state = 'PUMPFUN_ORIGIN_CONFIRMED'),
    acquisition_mode       TEXT NOT NULL CHECK (
        acquisition_mode IN ('SIGNATURE_ANCHORED_PROSPECTIVE',
                             'SUPPORT_ONLY_HISTORICAL')),
    ...provenance, evidence_hash, first_confirmed_at
);
```

**Semantics:**

* **Immutable.** `BEFORE UPDATE` and `BEFORE DELETE` triggers `RAISE(ABORT)`.
  A confirmed origin is a permanent fact.
* **Batch-independent.** No FK to any batch, run, campaign, or cycle. It
  outlives every campaign.
* **Confirmed-only.** `origin_state` admits exactly one value. There are no
  `PENDING`/`FAILED` rows — an unconfirmed mint is simply absent.
* **Idempotent re-confirmation.** Re-inserting a byte-identical row is a no-op.
  Re-inserting a *different* signature/slot for a known mint raises
  `ORIGIN_REGISTRY_CONFLICT` and is fail-closed.
* A companion `printer_pumpfun_origin_cursor` table holds one row per index
  address: `boundary_slot`, `boundary_signature`, `continuity_state`.

**UNKNOWN / GAPPED / UNAVAILABLE** are cursor states, never registry states. A
gap means "there may be creates we never saw", not "these creates are doubtful".

### 3.10 Ceilings and accounting

New request kinds on `solana_rpc`:

| Request kind | Ceiling | RPC operation |
|---|---:|---|
| `pumpfun_create_index_signature_page` | 3 | `getSignaturesForAddress` |
| `pumpfun_create_index_transaction` | 12 | `getTransaction` |

```
CREATE_INDEX_PAGE_CEILING     = 3      # pages per cycle
CREATE_INDEX_PAGE_SIZE        = 16     # rows per page
CREATE_INDEX_DECODE_CEILING   = 12     # getTransaction per cycle
EARLY_CREATE_STOP             = 8      # stop after 8 confirmed creates
UNDERLYING_OPERATION_CEILING  = 45     # unchanged
```

**Budget derivation (minimum sufficient).** The bar is two distinct confirmed
creates. On a create-exclusive index address a full 16-row page is ~16 create
candidates; two confirmations therefore need ~2 decodes in the healthy case.
`12` decodes is 6x that margin, absorbing failed transactions, `create_v2`, and
`UNAVAILABLE_HISTORY`. `3` pages covers the boundary walk in §3.4.

Worst case: `3 + 12 = 15` underlying operations — **a reduction** from the
retired path's 3 (session) + 2 (program pages) + 16 (program decodes) +
16 (origin pages) + 8 (origin decodes) = 45.

> **No ceiling is increased by this lane.** The total underlying-operation
> ceiling stays 45; actual worst-case consumption falls from 45 to 15, releasing
> 30 operations back to memory-window work. The retired kinds keep their
> registered ceilings so 4A–4H evidence stays reproducible, but they are not
> consumed on the primary path.

`INTAKE_UNDERLYING_RPC = 45` and `INTAKE_SOURCE_CALLS = 45` in
`combined_executor` are unchanged.

### 3.11 Retries, rotation, replay

Zero ordinary retries. Zero endpoint rotation. A transport failure, HTTP 429, or
null body is recorded as `UNAVAILABLE_HISTORY` for that operation and the cycle
continues within its remaining budget or terminalizes.

Replay: `AcquisitionCycleResult.canonical()` is a pure tuple of anchor, ordered
observations, ordered rejections, cursor, and accounting — no wall clock, no
mutable state. Re-running the same fixture sequence yields an equal tuple.
Zero-source replay reads the registry and cursor only.

### 3.12 Evidence retention

Persist decoded factual fields plus a `sha256` of the canonical decoded payload.
Never persist raw RPC responses, headers, endpoint URLs, or secrets. The live
proof writes to a disposable path under `operator-runs/` and commits only
redacted counts.

### 3.13 Entry into combined discovery

`_run_direct_lane` calls the new acquisition owner, writes each confirmed create
to the registry, and emits observations with
`pumpfun_origin_status = PUMPFUN_ORIGIN_CONFIRMED`.

`_origin_and_pumpswap` resolves origin in exactly this order:

1. candidate already carries a direct confirmed create this cycle → `CONFIRMED`;
2. **registry hit on exact mint** → `CONFIRMED`, `admission_state = NOT_REQUIRED`,
   `evidence_detail.source = "durable_origin_registry"` — **zero RPC**;
3. registry miss → `FAILED` with `ORIGIN_NOT_IN_REGISTRY`.

Step 3 is where archaeology used to live. It is now a terminal miss. The mint is
simply not eligible this cycle; a later cycle may find it once prospective
capture has recorded it.

### 3.14 Secondary providers

DexScreener, GeckoTerminal, and Solana Tracker remain observation and enrichment
sources. They contribute market identity, pool, activity, and freshness. They
continue to set `PUMPFUN_ORIGIN_UNVERIFIED` and can never establish origin. The
registry is writable **only** by the acquisition owner.

### 3.15 Explicitly unchanged

Exact pair/market freshness, liquidity and activity gates, cooldown, uniform
seeded selection, two-or-none activation, Tracker's 180-second contract,
memory-window rules, `GATE_ORDER`, retrieval and financial locks. The
`PUMPFUN_ORIGIN` gate predicate is unchanged: `origin_state == "CONFIRMED"`.
Only *how* a candidate reaches `CONFIRMED` changes.

---

## 4. Internal architecture review

| Question | Finding |
|---|---|
| Does the anchor still guarantee finality? | Yes — stronger. Finality now comes from the row's own `confirmationStatus`, cross-checked against the transaction, instead of a different backend's slot. |
| Can a non-finalized or forked create enter the registry? | No — §3.1 admission, §3.5 conflict handling, §3.6 confirmation, and the registry's confirmed-only CHECK. |
| Can the retired path reactivate? | No — §2.4: not called, guarded by `RetiredPrimaryPathError`, and import-asserted by test. |
| Does any ceiling increase? | No — §3.10; worst case falls 45 → 15. |
| Is the migration minimal? | One table + one cursor table + immutability triggers. Required by RC-3; no existing table can hold a cross-cycle origin. |
| Does this touch gates, selection, or locks? | No — §3.15. |
| What if `mint_authority` is not create-exclusive? | Yield degrades toward the whole-program case. The bounded live proof (Phase 6) is exactly the test of this assumption; failure returns `BLOCKED_NO_VIABLE_FREE_PUBLIC_RPC_ARCHITECTURE`, not a patch. |

**Review verdict:** approved for implementation.
