# V2-9.7E.5 Pump Origin Acquisition Architecture Reset Closeout

**Status:** BLOCKED
**Lane:** V2-9.7E.5 — Pump Origin Acquisition Architecture Reset
**Boundary:** architecture reset + implementation + offline proof + exactly one bounded live proof; no pilot; no rerun
**Date:** 2026-07-21
**Baseline HEAD:** `3396dfc6833c15f96e2dd45aa0a405858e1cb290`

## Final Verdict

`V2_9_7E_5_BLOCKED_IMPLEMENTATION_OR_PROOF`

**Block reason:** the single authorized bounded live proof terminated on a
transport `URLError` at its **first** RPC call, before any signature data was
returned. Zero creates were observed, so the PASS bar (≥2 distinct finalized
supported creates) was not met.

**This is explicitly not an architecture-level block.** The proof produced no
measurement of the new architecture's create yield, because it never received a
response. See §7.2 for why `BLOCKED_NO_VIABLE_FREE_PUBLIC_RPC_ARCHITECTURE`
would be an unsupported claim.

**No commit.** Per the lane's commit policy, `BLOCKED_IMPLEMENTATION_OR_PROOF`
forbids committing. All architecture, implementation, migration, tests, and this
closeout remain uncommitted in the working tree.

Uncommitted V2-9.7E.4D and 4H artifacts were preserved read-only and were not
rewritten as current results.

## Todo / Checklist

- [x] Verify HEAD `3396dfc…`.
- [x] Phase 1 — whole-path root-cause audit.
- [x] Phase 2 — architecture decision (Option A selected).
- [x] Phase 3 — specification freeze.
- [x] Phase 4 — implementation.
- [x] Phase 5 — synthetic and integration proof (40 new + 140 regression, green).
- [x] Phase 6 — exactly one bounded live proof (**BLOCKED at transport**).
- [x] Phase 7 — this closeout.
- [ ] Commit — **skipped** (BLOCKED).

---

## 1. Complete root-cause statement

The empty-origin blocker was never a pagination, ceiling, or depth problem.
Three independent architecture defects sat on the critical path.

**RC-1 — the admission anchor was incoherent (architecture defect).**
`run_fixture_cycle` froze one `getSlot(commitment=finalized)` value and rejected
every signature row with `slot > cutoff` as `POST_CUTOFF`.
`api.mainnet-beta.solana.com` is a multi-backend pool: the node answering
`getSlot` and the node answering `getSignaturesForAddress` hold independent
finalized views, so a genuinely finalized row can legitimately exceed the
cutoff. The cutoff added **no** safety the row did not already carry —
`getSignaturesForAddress` at finalized commitment returns only finalized rows,
each with its own `confirmationStatus` and `slot`.

This explains 4D (32/32 `POST_CUTOFF`, 0 decodes) and, decisively, 4H: after the
4G pagination repair added a second older page, the result was **identical**
(32/32, 0 decodes). The 4G repair could not have worked, because depth was never
the defect.

**RC-2 — the index address had ~1% create density (architecture defect).**
Polling `getSignaturesForAddress(PUMP_PROGRAM_ID)` returns all Pump activity;
buys and sells outnumber creates by roughly two orders of magnitude, and the
signature list carries no discriminator, so separating them costs one
`getTransaction` each. With 2 pages × 16 rows and 16 decodes, the expected
create yield of a *perfect* cycle is below one. Even with RC-1 fixed, this
address cannot reach two creates inside the 45-operation budget.

**RC-3 — origin evidence was batch-scoped (architecture defect).**
`printer_discovery_origin_verifications` is `NOT NULL` FK'd to
`printer_discovery_batches` and uniquely keyed
`(discovery_batch_id, merged_candidate_id)`. A confirmed origin is an artifact
of one batch; a later cycle cannot read it. Eligibility for an aged mint
therefore required rediscovering its creation transaction at campaign time.

**RC-4 — that rediscovery is unbounded (historical-retention + request-budget).**
For a trending mint the create sits behind thousands of buys/sells; 4G's 3×16
newest signatures cannot reach it. 4H additionally hit HTTP 429 on 4 of 7 mints
under fan-out, correctly declining to retry.

**RC-5 — the seven pilot mints were an unrepresentative PASS dependency
(market-yield limitation of the test design).** They were hours old and loaded
from a prior blocked pilot DB — the hardest possible origin target, and not what
a healthy prospective pipeline consumes.

**RC-6 — `logsSubscribe` primary capture is not viable (RPC capability limit).**
No usable free public WebSocket, `processed` commitment only (so a finalized
confirmation is still required, giving no request saving), and an unbounded
reconnect loop that AGENTS.md forbids outside Scheduler ownership.

**RC-7 — no bypass exists (no defect; preserved).** Secondary providers set
`PUMPFUN_ORIGIN_UNVERIFIED`; the `PUMPFUN_ORIGIN` gate requires
`origin_state == "CONFIRMED"`; provider labels never establish origin.

## 2. Architecture options and decision

Full comparison table in
`docs/printer-v1-v2-9-7e-5-pump-origin-acquisition-architecture.md` §2.2.

**Selected: Option A — signature-anchored finalized polling**, anchored on the
create-exclusive Pump `mint_authority` index address
`TSLvdd1pWpHVjahSpsvCXUbgwsL3JAcvokwaKt1eokM`.

The pinned create contract fixes `mint_authority` as create account[1], already
enforced by `_validate_account_identities`. It signs the initial supply mint
during `create` and is not an account of `buy`/`sell` — so it indexes creates
and essentially nothing else, at identical RPC cost.

* **Option B rejected** on RC-6.
* **Option C rejected as specified** — its primary leg is B's live capture, and
  it deliberately retains two competing primary acquisition paths.

Option C's *persistence* contribution is adopted independently: the durable
exact-mint origin registry. A registry is storage, not acquisition; there
remains exactly one way to establish an origin.

## 3. Retired paths

| Retired | Replacement | Enforcement |
|---|---|---|
| `getSlot` cutoff as admission anchor | the finalized signature row itself | no `getSlot` in adopted operations; a `getSlot` op is rejected |
| whole-program signature polling | create-exclusive index address | new request kinds only |
| `logsSubscribe`/`logsUnsubscribe` session | none | no session request kind exists in the new owner |
| `run_fixture_cycle` as primary | `run_acquisition_cycle` | raises `RetiredPrimaryPathError` on `primary_path=True`; not imported by `combined_executor` (test-asserted) |
| `run_mint_origin_lookup` on the activation path | durable registry lookup | same guard + `allow_support_only_history` opt-in the executor never sets |
| aged pilot mints as PASS dependency | prospective capture of fresh creates | live proof does not load the pilot DB |

Both retired functions are kept (not deleted) so the 4A–4H evidence set stays
reproducible; their regression suites remain green.

## 4. Final data and ownership model

Acquisition is Scheduler-owned (`DISCOVERY_REFRESH` /
`DISCOVERY_PUMPFUN_LATEST`) and Governor-owned (`solana_rpc`, two new request
kinds). Every observed value enters through `FixtureOperation`; the port
validates Governor kind and Scheduler work-type **before** consumption. No
transport, loop, retry, or reconnect exists in the owner — asserted structurally
via AST (no networking import, no `while True`, no sleep).

Origin resolution order in `_origin_and_pumpswap`:

1. direct confirmed create this cycle → `CONFIRMED`;
2. **registry hit on exact mint** → `CONFIRMED`, `admission_state=NOT_REQUIRED`,
   `evidence_detail.source="durable_origin_registry"` — **zero RPC**;
3. miss → `FAILED` with `ORIGIN_NOT_IN_REGISTRY`.

Step 3 is where archaeology used to live; it is now a terminal miss.

## 5. Migration

One migration, `036_pumpfun_finalized_origin_registry.sql`:

* `printer_pumpfun_finalized_origin_registry` — mint-keyed, batch-independent,
  confirmed-only, immutable (`BEFORE UPDATE`/`BEFORE DELETE` → `RAISE(ABORT)`),
  storing decoded facts plus a sha256 evidence hash and never a raw payload;
* `printer_pumpfun_origin_cursor` — one high-water mark per index address.

Required by RC-3: no existing table can retain a cross-cycle origin.

## 6. Files changed

| File | Change |
|---|---|
| `docs/printer-v1-v2-9-7e-5-pump-origin-acquisition-architecture.md` | new — audit, decision, frozen spec |
| `docs/printer-v1-v2-9-7e-5-pump-origin-acquisition-reset-closeout.md` | new — this closeout |
| `migrations/036_pumpfun_finalized_origin_registry.sql` | new — durable registry + cursor |
| `src/printer_v1/sources/pumpfun_origin.py` | new — primary acquisition owner + registry API |
| `src/printer_v1/sources/pumpfun_direct.py` | retirement markers, `RetiredPrimaryPathError` guards |
| `src/printer_v1/sources/registry.py` | two new adopted request kinds |
| `src/printer_v1/discovery/combined_executor.py` | primary path swapped; registry-first origin resolution; archaeology removed |
| `tests/test_v2_9_7e_5_pump_origin_acquisition_architecture.py` | new — 40 synthetic/integration proofs |
| `operator-runs/v2-9-7e-5-live-proof/` | live proof harness + redacted result |

Not touched: freshness, liquidity/activity gates, cooldown, uniform seeded
selection, two-or-none activation, Tracker's 180-second contract, memory-window
rules, `GATE_ORDER`, retrieval, decisions, positions, trades, audits, PnL,
wallet/signing.

## 7. Ceilings and accounting

| Item | Retired path | New path |
|---|---:|---:|
| Signature pages | 2 (+16 origin) | 3 |
| Decodes | 16 (+8 origin) | 12 |
| Session ops | 3 | 0 |
| **Worst-case underlying** | **45** | **15** |
| Underlying ceiling | 45 | 45 (unchanged) |

**No ceiling was increased.** Worst-case consumption falls from 45 to 15,
releasing 30 operations back to memory-window work. `INTAKE_UNDERLYING_RPC` and
`INTAKE_SOURCE_CALLS` are unchanged at 45.

Live proof session ceilings (predeclared): 15 underlying operations, 300 s,
5 failures, 8 MiB storage, 0 retries, 0 rotations.

## 8. Synthetic and integration proof

`tests/test_v2_9_7e_5_pump_origin_acquisition_architecture.py` — **40 passed**.

Covered: cold start; two distinct finalized supported creates; a finalized row
far newer than any external slot still admitted (the exact 4D/4H failure);
`POST_CUTOFF` structurally unreachable; `getSlot` not adoptable; restart with
bounded backfill reaching the boundary; boundary unreachable within the page
ceiling → `GAPPED`; short page → `GAPPED`; duplicates admitted once; fork /
conflicting duplicate dropped and `GAPPED`; non-finalized never admitted; failed
transactions as noise not faults; non-create counted; `create_v2` blocked and
counted; empty page → `UNAVAILABLE`; stale page does not rewind the cursor;
finite decode ceiling; deterministic replay; finite request/operation
accounting; Governor and Scheduler bypass rejected; unplanned operation
rejected; no transport/subscription/loop surface (AST-asserted); registry
persistence, cross-connection durability, exact-mint lookup, mint-mismatch miss,
idempotent re-confirmation, fail-closed conflict, row immutability, no raw
payload, cursor round-trip; end-to-end acquisition → registry → later-cycle
lookup; and all four retirement guards.

**Regressions (all green):**
`test_v2_9_7d_7b_4a_direct_pump_adapter`,
`test_v2_9_7e_4c_direct_pump_create_capture_productivity`,
`test_v2_9_7e_4g_cutoff_historical_origin`,
`test_pumpfun_direct_create_contract_fixture` (39);
`test_v2_9_7d_7b_4d_combined_discovery_executor`,
`test_v2_9_7d_7b_5_isolated_combined_discovery_proof`,
`test_v2_9_7d_7b_4d_1_atomic_two_slot_handoff`,
`test_v2_9_7d_7b_4c_discovery_persistence`,
`test_v2_9_7d_6b_7_zero_source_read_only_replay`,
`test_phase2_source_registry_governor` (54 + 8 subtests);
`test_v2_9_7e_1_insufficient_pool_terminal_cleanup`,
`test_v2_2v_discovery_persistence_gate_reform` (47 + 42 subtests);
plus `test_v2_2c_selection_batch`, `test_v2_2s_selection_cooldown`,
`test_v2_9_4_durable_supervision`, `test_phase3_scheduler_resource_governor`
(exit 0).

The harness itself was validated offline against synthetic RPC responses before
the live run: it correctly produced PASS on two synthetic creates and BLOCKED
when a ceiling was breached.

## 9. Live-proof results

Exactly one live run. Evidence:
`operator-runs/v2-9-7e-5-live-proof/V2_9_7E_5_LIVE_PROOF_RESULT.json`.

| Field | Value |
|---|---|
| Started / finished UTC | `2026-07-21T19:22:32Z` / `2026-07-21T19:22:45Z` |
| RPC | `https://api.mainnet-beta.solana.com` (free public only) |
| Index address | `TSLvdd1pWpHVjahSpsvCXUbgwsL3JAcvokwaKt1eokM` |
| Governor admitted both new kinds | yes |
| `getSignaturesForAddress` calls | 1 |
| Outcome of that call | **transport `URLError`** after ~13 s |
| Signature rows returned | **0** |
| Decode attempts | 0 |
| Distinct confirmed creates | **0** (bar: ≥2) |
| Continuity | `UNAVAILABLE` (honest — no data received) |
| Underlying operations | 1 / 15 |
| Retries / rotations / reconnects | 0 / 0 / 0 |
| Failures | 1 |
| Duration | 13 s / 300 s |
| Provider-label origin | false |
| Terminal cleanup | complete — no subscription, lease, or child process |

Owner, persistence, and replay machinery executed without error on the empty
result: `canonical_stable = true`, `zero_source = true`, cursor honestly
`UNAVAILABLE`, zero rows written. **No rerun was performed.**

### 9.1 Post-proof diagnosis (not a second proof)

To classify the blocker correctly, one non-capture reachability check was made
to the same host: `getHealth` returned HTTP 200 `"ok"`. The endpoint was
therefore reachable, and the proof's `URLError` was a connection-level failure
on that specific call — not an unreachable service.

This check deliberately issued **no** `getSignaturesForAddress` on the index
address, so it does not constitute a second capture attempt and produced no
PASS-bearing evidence.

### 9.2 Why the architecture-level verdict is not claimed

`V2_9_7E_5_BLOCKED_NO_VIABLE_FREE_PUBLIC_RPC_ARCHITECTURE` would assert that the
selected architecture cannot work on free public RPC. **The proof produced no
evidence for that claim.** The call failed before returning any rows, so:

* create density on the index address is **unmeasured**;
* whether the public RPC serves `getSignaturesForAddress` for this
  high-cardinality account is **unknown**;
* the 4D/4H `POST_CUTOFF` failure mode was **not** reproduced or refuted live.

Two hypotheses remain open and are not distinguished by the evidence:

1. a transient connection failure unrelated to the query;
2. the public RPC dropping or refusing an expensive signature query on a
   very-high-cardinality account — which *would* be architecture-relevant.

Reporting either as settled would be a fabricated finding. The honest verdict is
`BLOCKED_IMPLEMENTATION_OR_PROOF`: the proof did not complete.

## 10. Money-usefulness contribution

Even while BLOCKED, this lane converts a recurring blocker into a closed design
question and reduces cost:

* identifies the true cause of the 4D/4H empty-origin failure and shows why the
  4G repair could not have fixed it — ending the patch cycle the lane was
  convened to stop;
* removes campaign-time historical archaeology from the critical activation
  path, so eligibility no longer depends on retention luck or 429 timing;
* makes confirmed origins permanent facts, so each mint is verified at most once
  ever instead of once per cycle;
* cuts worst-case origin RPC from 45 to 15 operations, returning 30 to
  memory-window work — the work that actually grows clean memory.

It invents no origin, forces no activation, and claims no pilot pass.

## 11. What this lane improves

One primary acquisition architecture with a coherent anchor; a create-exclusive
index address; durable prospective origin evidence; deterministic replay;
honest `UNKNOWN`/`GAPPED`/`UNAVAILABLE` states; retirement guards that prevent
silent reactivation; and a strictly lower request budget.

## 12. What remains locked

Second live run, pilot, V2-9.7F, V2-9.8; production activation of the new path
(uncommitted); eligibility, freshness, cooldown, two-or-none, selection, and
Tracker contracts; `create_v2` adoption; retrieval, decisions, BUY/SELL/HOLD,
positions, trades, audits, PnL, wallet/signing/real funds.

## 13. Exact remaining external limitations

1. **Create density on the mint-authority index address is unverified live.**
   The architecture's central quantitative assumption rests on the pinned IDL
   account list, not on measurement.
2. **Public-RPC behaviour for `getSignaturesForAddress` on a very-high-cardinality
   account is unknown** — it may be slow, throttled, or dropped.
3. Free-tier 429s remain possible under any fan-out, with zero-retry policy.
4. Public RPC retention bounds how far any boundary walk can recover; deep gaps
   stay honestly `GAPPED`.
5. Future live `create_v2` share is unknown; those creates are counted, blocked,
   and not adopted.

## 14. Functionality Risks / Setbacks / Efficiency Blockers

1. **Setback:** the one authorized live proof did not clear the ≥2-create bar; it
   failed at transport with zero data.
2. **Risk (highest):** the create-exclusivity of `mint_authority` is derived from
   the pinned contract, not measured. If buys/sells touch it, yield degrades
   toward the whole-program case and Option A's advantage disappears.
3. **Risk:** a very-high-cardinality index account may be exactly the query a
   free public RPC declines to serve — the same class of limit that produced
   4H's 429s. If hypothesis (2) in §9.2 holds, this becomes an architecture-level
   blocker.
4. **Efficiency blocker:** one transport failure consumed the entire live-proof
   authorization, yielding no measurement — the proof has no tolerance for a
   single connection blip. A future authorization should permit a bounded
   transport-failure allowance *before* first data, distinct from a retry.
5. **Risk:** the implementation is complete and green offline but uncommitted, so
   it is not protected against working-tree loss.
6. No production defect was found that would justify weakening finalized origin
   or raising any ceiling.

## 15. Readiness for one later V2-9.7E pilot rerun

**NOT READY.**

The pilot must not be rerun from this closeout. The new architecture has never
successfully captured a create from live RPC, so its central assumption is
unverified. A pilot now would test an unmeasured path.

Minimum to reach readiness — **one re-authorized bounded live proof** of
V2-9.7E.5, unchanged in scope, with:

* a small predeclared transport-failure allowance before first data (not a
  retry of a *returned* result);
* explicit recording of observed create density on the index address.

If that proof confirms ≥2 distinct finalized supported creates, the lane becomes
PASS-eligible and the implementation may be committed. If it instead shows the
public RPC will not serve the index-address query, the correct verdict is
`V2_9_7E_5_BLOCKED_NO_VIABLE_FREE_PUBLIC_RPC_ARCHITECTURE` — and the architecture,
not another patch, must be revisited.

---

# 5A Decisive Re-proof — 2026-07-21

**Lane:** V2-9.7E.5A — Decisive Live Pump-Origin Architecture Re-proof
**Status:** BLOCKED
**Verdict:** `V2_9_7E_5A_BLOCKED_NO_VIABLE_FREE_PUBLIC_RPC_ARCHITECTURE`
**Baseline HEAD:** `3396dfc6833c15f96e2dd45aa0a405858e1cb290` (unchanged)

Sections 1–16 above record the V2-9.7E.5 lane and remain intact. Nothing in the
prior blocked-proof evidence was rewritten.

## 5A.1 Preservation and preflight

No implementation change was made. The frozen contract was asserted
programmatically before any live call — all 14 checks true: index address equals
the pinned `mint_authority`, page ceiling 3, page size 16, decode ceiling 12,
exactly two adopted request kinds, both Governor-allowed, retired role
`SUPPORT_ONLY`, both retired-path guards still raising, `combined_executor`
importing neither retired owner, migration 036 present.

External safety backup created outside the repository before any live call at
`~/Desktop/printer-v1-v2-9-7e-5-backup-20260721/`: 10 lane files, `MANIFEST.txt`,
`SHA256SUMS.txt`, `HEAD.txt`, `git-status.txt`, `unstaged.diff`, `staged.diff`.
No stash, no WIP commit. Only the three expected tracked files were modified;
nothing was staged.

Offline proof re-run green: **40 passed**.

Disposable database preflight: 36 migrations applied, `036` applied,
`integrity_check = ok`, 0 foreign-key violations, registry and cursor tables
present, 0 active Scheduler jobs. Safety: free public RPC only, no auth header,
no API-key env, no wallet/signing, no paid dependency.

## 5A.2 Exact UTC run window

| Field | Value |
|---|---|
| Started UTC | `2026-07-21T19:41:48Z` |
| Finished UTC | `2026-07-21T19:42:01Z` |
| Duration | 13 s / 300 s |
| RPC | `https://api.mainnet-beta.solana.com` |
| Index address | `TSLvdd1pWpHVjahSpsvCXUbgwsL3JAcvokwaKt1eokM` |

Evidence: `operator-runs/v2-9-7e-5a-decisive-reproof/V2_9_7E_5A_DECISIVE_REPROOF_RESULT.json`

## 5A.3 Health check (not proof evidence)

`getHealth` → HTTP 200, `result = "ok"`, 2.8 s. Not counted in RPC accounting
and not used as proof evidence.

## 5A.4 Capture-query result — the decisive finding

| Field | Value |
|---|---|
| Capture attempts | **1** (no retry, no rotation, no fallback) |
| HTTP status | **200** |
| Latency | **0.5 s** |
| Rows returned | **16** |
| Usable | **yes** |

**The index-address capture query succeeded cleanly.** This settles the open
question from §9.2 above: the V2-9.7E.5 failure was hypothesis (1), a transient
connection blip. Hypothesis (2) — that free public RPC would refuse or drop an
expensive signature query on a very-high-cardinality account — is **refuted**.
The query is cheap and fast.

## 5A.5 Signature, decode, create, and density counts

| Metric | Value |
|---|---:|
| Signature rows | 16 |
| Admitted rows (finalized, successful, deduplicated) | **16 / 16** |
| `POST_CUTOFF` rejections | **0** |
| `MISSING_FINALITY` rejections | 0 |
| Decode attempts | 12 (decode ceiling) |
| `NOT_SUPPORTED_CREATE` (non-create) | **0** |
| `UNSUPPORTED_VERSION` | **10** |
| `UNAVAILABLE_HISTORY` (null transaction body) | 2 |
| **Supported finalized creates confirmed** | **0** (bar: ≥2) |
| Supported-create density | **0.0** |

**RC-1 is validated live.** All 16 finalized rows were admitted and zero were
rejected as `POST_CUTOFF`. The cross-backend cutoff race that emptied 4D and 4H
(32/32 rejected) is gone. The signature-anchored anchor works.

**The blocker moved.** Acquisition, admission, finality, ordering, and budget
all behaved exactly as designed. Every decode failed at the pinned decoder's
supported-instruction contract.

### 5A.5.1 Ambiguity in `UNSUPPORTED_VERSION` — stated honestly

`decode_finalized_create` raises `UNSUPPORTED_VERSION` from **two** distinct
branches:

* `pumpfun_direct.py:544` — transaction `version` not in `("legacy", 0)`;
* `pumpfun_direct.py:593` — a `create_v2` discriminator on the Pump program.

The owner's `create_v2_count` increments on the code alone and therefore
**conflates the two**. The harness stores no raw payloads by design, so this run
cannot distinguish them, and no further live call was permitted.

**Most probable reading:** the capture passed
`maxSupportedTransactionVersion: 0`, under which the RPC returns only `legacy`
or `0` transactions and always populates `version`. The version gate should
therefore not have fired, leaving `create_v2` as the overwhelmingly likely
cause — i.e. Pump.fun's live create traffic is now `create_v2`, which this lane
explicitly blocks and does not adopt.

**What this means for create-exclusivity:** if the failures were at the
`create_v2` branch, then all 10 parsed transactions were Pump creates and the
index address is confirmed create-exclusive with ~100% density — RC-2's fix
validated. If instead they were at the version gate, instruction scanning never
ran and create-exclusivity remains unmeasured. The evidence strongly indicates
the former but **does not prove it**. It is recorded as indicated, not
established.

## 5A.6 RPC-operation accounting

| Method | Calls |
|---|---:|
| `getSignaturesForAddress` | 1 |
| `getTransaction` | 12 |
| **Underlying total** | **13** (≤ 15) |

Governed requests: `pumpfun_create_index_signature_page` 1,
`pumpfun_create_index_transaction` 12. Capture attempts 1. Retries **0**.
Endpoint rotations **0**. Reconnects **0**. Duration 13 s ≤ 300 s. Storage
2,174,976 B ≤ 8 MiB (schema baseline; zero evidence rows). All ceilings
respected; no ceiling raised.

## 5A.7 Registry and replay results

| Item | Result |
|---|---|
| Registry rows written | 0 (nothing confirmed to write) |
| Registry error | none |
| Cursor persisted | yes, honestly `UNKNOWN` |
| Later-cycle exact-mint resolution | not exercised — no confirmed origins |
| Zero-source replay | **true** (0 additional RPC) |
| Deterministic replay `canonical()` | **stable** |
| Provider-label origin | **false** |
| Retired-path activation | **none** |

The persistence, later-cycle, and replay machinery executed without error on the
empty result. Their correctness on a populated result remains proven only
offline (§8), not live.

## 5A.8 Cleanup

No active subscriptions, leases, child processes, or Scheduler work. Proof
database disposable and excluded from commit. Terminal cleanup complete.

## 5A.9 Decisive architecture verdict

`V2_9_7E_5A_BLOCKED_NO_VIABLE_FREE_PUBLIC_RPC_ARCHITECTURE`

Matching §7 criterion: *"the query returns data but cannot produce two distinct
supported finalized creates within the adopted ceiling."*

The verdict label is the only one available for this outcome, and it must be
read precisely — **the free public RPC is not the blocker.** It answered in
0.5 s with a full, fully finalized page. Recorded accurately:

* **Acquisition architecture: validated.** Signature-anchored admission,
  coherent finality, deterministic ordering, bounded budget, zero retries — all
  confirmed live. RC-1 is fixed.
* **Index address: works, and is indicated (not proven) create-exclusive.**
* **Blocker: the pinned decoder's supported-instruction contract.** Live Pump
  create traffic is not the legacy `create` this decoder accepts.

Adopting `create_v2` would change the frozen decoder contract, which this lane
forbids. Per instruction, **no further repair is proposed here.**

## 5A.10 Money-usefulness effect

* Converts the central unverified assumption of V2-9.7E.5 into measured
  evidence: the index-address query is cheap, fast, and fully finalized.
* Refutes the RPC-refusal hypothesis, removing a whole branch of speculative
  future work.
* Localises the remaining blocker to exactly one contract decision
  (`create_v2` support), replacing an open architecture question with a single
  scoped one.
* Proves live that the 4D/4H `POST_CUTOFF` failure mode is eliminated — the
  defect that consumed lanes 4A–4H is closed.
* Costs 13 RPC operations and 13 seconds.

No origin was invented, no activation forced, no pilot claimed.

## 5A.11 Remaining locks

Second live run; full V2-9.7E pilot; V2-9.7F; V2-9.8; `create_v2` adoption;
decoder contract changes; ceiling increases; retries; endpoint rotation;
WebSocket/live-session capture; historical mint archaeology; retrieval;
decisions; BUY/SELL/HOLD; positions; trades; audits; PnL; wallet, signing, and
real funds. Production implementation is **not** committed.

## 5A.12 Functionality Risks / Setbacks / Efficiency Blockers

1. **Setback:** the PASS bar (≥2 supported finalized creates) was not met;
   supported-create density measured **0.0**.
2. **Decisive finding:** the blocker is no longer acquisition. It is the
   decoder's `create_v2` block meeting live traffic that appears to be entirely
   `create_v2`.
3. **Evidence-granularity defect:** `create_v2_count` conflates the
   transaction-version gate with the `create_v2` gate, so this run cannot prove
   which fired. Recorded, not repaired — any future lane touching this should
   separate the two codes before spending another live proof.
4. **Risk:** because of (3), create-exclusivity of the index address is
   *indicated but unproven*. The architecture's density claim still rests
   partly on the pinned IDL rather than measurement.
5. **Risk:** 2 of 12 `getTransaction` calls returned null bodies
   (`UNAVAILABLE_HISTORY`), possibly free-tier throttling after 10 rapid calls.
   Zero-retry policy correctly declined to re-request.
6. **Setback:** per commit policy the production implementation is discarded
   from the commit; it survives only in the external backup.
7. No defect was found that would justify weakening finalized origin, raising a
   ceiling, adding retries, or adopting paid infrastructure.

## 5A.13 Readiness for one later V2-9.7E pilot rerun

**NOT READY**, and the reason has changed from §15.

The acquisition architecture is now live-validated, so the earlier readiness
condition (prove the index-address query works) is **met**. But zero supported
creates can be captured while `create_v2` is unsupported, so the durable
registry cannot populate and two-slot activation cannot occur.

The next decision is an explicit, operator-authorised scope question — whether
Printer adopts `create_v2` into the pinned decoder contract — not another repair
of this lane.

---

# Correction — 2026-07-21 (added by V2-9.7E.6)

This correction is appended, not substituted. The historical 5 and 5A results
above are preserved exactly as recorded and were not rewritten.

**1. Free public RPC viability was demonstrated, not refuted.**
The 5A capture returned HTTP 200 in 0.5 s with a full 16-row finalized page from
the create-index address, and V2-9.7E.6 reproduced this twice more. The free
public endpoint serves this query cheaply and reliably. Nothing in either lane
showed a public-RPC capability limit.

**2. The verdict label was constrained by the available choices.**
`V2_9_7E_5A_BLOCKED_NO_VIABLE_FREE_PUBLIC_RPC_ARCHITECTURE` was the only one of
the four permitted verdicts matching "returned data but could not produce two
supported creates". Read literally it overstates an RPC problem that the
evidence did not support. §5A.9 already flagged this; this correction records it
against the verdict itself.

**3. The actual unresolved blocker was ambiguous Pump create-layout compatibility.**
`UNSUPPORTED_VERSION` was raised from two unrelated branches — the Solana
transaction-envelope gate and the `create_v2` block — so the 5A evidence could
not identify which fired. V2-9.7E.6 separated them and captured live evidence:
**10 of 10 accepted envelopes contained a Pump `create_v2` instruction; zero
envelopes were rejected.** The blocker was that Pump had moved to `create_v2`,
which the pinned decoder deliberately did not support.

**4. Two 5A statements are now settled.**
The create-exclusivity of the index address, recorded in §5A.5.1 as *indicated
but unproven*, is **confirmed**: V2-9.7E.6 measured a create density of 1.0.
The §5A.12 item 3 evidence-granularity defect is **fixed** by the four-outcome
split.

Resolution and completion: `docs/printer-v1-v2-9-7e-6-pump-create-contract-reconciliation-design.md`
and `docs/printer-v1-v2-9-7e-6-pump-create-origin-architecture-completion-closeout.md`.

## 16. Stop boundary

V2-9.7E.5 ends **BLOCKED**. No commit. No tag. No rerun under this
authorization. The full V2-9.7E memory-factory pilot was not run and did not
pass. V2-9.7F, V2-9.8, retrieval, paper decisions, BUY/SELL/HOLD, positions,
trades, audits, and PnL were not begun.
