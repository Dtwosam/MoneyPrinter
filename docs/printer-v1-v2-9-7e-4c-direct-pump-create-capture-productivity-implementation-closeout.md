# V2-9.7E.4C Direct Pump Create-Capture Productivity Implementation Closeout

**Status:** PASS
**Lane:** V2-9.7E.4C — Direct Pump Create-Capture Productivity Implementation
**Design authority:** `docs/printer-v1-v2-9-7e-4b-direct-pump-create-capture-productivity-design.md`
**Date:** 2026-07-21
**Baseline HEAD:** `f3e8c37567982aaafa5ba53a5e5cce2cc97b18a9`

## Final Verdict

`V2_9_7E_4BC_DIRECT_PUMP_CREATE_CAPTURE_DESIGN_IMPLEMENTATION_PASS`

Both phases completed:

1. **4B design** — internally reviewed PASS; no contract/architecture blocker.
2. **4C implementation** — design-faithful synthetic fixture proof only.

Does **not** authorize live source proof, another pilot, V2-9.7F, or V2-9.8.

## Todo / Checklist

- [x] Verify HEAD `f3e8c37…`.
- [x] Read 4A audit, 7B.2/3A/4A contracts, governor registry, combined executor.
- [x] Write and PASS 4B design freeze.
- [x] Implement direct capture productivity + mint-scoped origin lookup.
- [x] Wire combined executor fixture origin lookup (no migration).
- [x] Synthetic proofs + focused regressions.
- [x] Both diff checks; commit lane files only.

---

## Files Changed

| File | Role |
|---|---|
| `docs/printer-v1-v2-9-7e-4b-direct-pump-create-capture-productivity-design.md` | Design freeze |
| `docs/printer-v1-v2-9-7e-4c-direct-pump-create-capture-productivity-implementation-closeout.md` | This closeout |
| `src/printer_v1/sources/pumpfun_direct.py` | Productivity + mint origin owner |
| `src/printer_v1/discovery/combined_executor.py` | Optional fixture origin-lookup wiring |
| `tests/test_v2_9_7e_4c_direct_pump_create_capture_productivity.py` | New focused proofs |

---

## Final Design (executed)

See 4B document. Freeze highlights:

- Immutable finalized cutoff before collection.
- Cold `UNKNOWN` vs trusted contiguous cursor rules unchanged in spirit.
- ≤2 signature pages / ≤32 enumerated / ≤16 decode attempts.
- Failed signatures filtered before `getTransaction`; counts retained; no continuity fault.
- Successful non-create → `NOT_SUPPORTED_CREATE`; no observation; no continuity fault.
- Early-create stop at **8** successful creates (`EARLY_CREATE_STOP`).
- Genuine gaps: missing finality, unavailable history, malformed, unsupported/`create_v2`, ceiling, disconnect, conflict, incomplete interval.
- Bounded mint origin: adopted `pumpfun_origin_signature_reference` + `pumpfun_origin_transaction_reference`.
- Zero retries / no endpoint rotation / no background reconnect.
- `create_v2` remains blocked.

---

## Implemented Sampling and Origin Flow

### Direct program capture (`run_fixture_cycle`)

1. Governed session: `getSlot` → immutable cutoff; live subscribe/unsubscribe.
2. Up to two governed `getSignaturesForAddress` pages (≤16 rows each).
3. Admit by exact signature; reject post-cutoff; conflict → gap.
4. Deterministic order `(slot, signature)`.
5. Pre-decode filter: failed → count only; non-finalized → `MISSING_FINALITY` + fault.
6. Decode-eligible capped at 16; overflow → `TRANSACTION_DECODE_CEILING` + fault.
7. Decode until `EARLY_CREATE_STOP` creates; remainder → `EARLY_CREATE_STOP` (no fault).
8. Continuity: `UNKNOWN` / `GAPPED` / `CONTIGUOUS` per design; cursor advances only on contiguous success.

New redacted counters on `DirectPumpCycleResult`:

- `failed_signature_count`
- `non_create_count`
- `decode_attempts`

### Mint-scoped origin (`run_mint_origin_lookup`)

1. One origin signature page for the **mint** address (≤16 rows).
2. Filter failed / non-finalized / post-cutoff.
3. Earliest successful finalized signature → at most one origin `getTransaction`.
4. `decode_finalized_create(..., expected_mint=…)` — exact mint required.
5. Fail closed on mismatch, `create_v2`, non-create, unavailable history.

### Combined executor

`CombinedDiscoveryFixtures` adds:

- `origin_lookup_operations: Mapping[mint, FixtureOperation…]`
- `origin_cutoff_slot: int | None`

Admitted secondaries without pre-baked `origin_proofs` may run mint lookup when ops + cutoff are planned. Gates, two-or-none, freshness, cooldown, Tracker unchanged.

---

## Ceilings and Ownership

| Kind | Ceiling | Work type |
|---|---:|---|
| `pumpfun_create_event_subscription` | 1 | `DISCOVERY_PUMPFUN_LATEST` |
| `pumpfun_create_signature_backfill` | 2 | `DISCOVERY_PUMPFUN_LATEST` |
| `pumpfun_create_transaction_reference` | 16 | `DISCOVERY_PUMPFUN_LATEST` |
| `pumpfun_origin_signature_reference` | 8 (1 per mint port) | `DISCOVERY_ORIGIN_VERIFICATION` |
| `pumpfun_origin_transaction_reference` | 8 (1 per mint port) | `DISCOVERY_ORIGIN_VERIFICATION` |

Underlying direct/origin ports enforce per-operation ceilings and the 45 underlying operation ceiling. Governor registry already admitted origin kinds; no new kinds.

---

## Continuity Behavior

| Class | Fault? | Implemented |
|---|---|---|
| `FAILED_TRANSACTION` | No | Yes |
| `NOT_SUPPORTED_CREATE` | No | Yes |
| `EARLY_CREATE_STOP` | No | Yes |
| `POST_CUTOFF` | No | Yes |
| `MISSING_FINALITY` | Yes | Yes |
| `UNAVAILABLE_HISTORY` | Yes | Yes |
| `UNSUPPORTED_VERSION` / `create_v2` | Yes | Yes |
| Ceiling / disconnect / conflict / incomplete interval | Yes | Yes |

Non-create traffic alone no longer forces `GAPPED`.

---

## Proof Results

| Suite | Result |
|---|---|
| `tests/test_v2_9_7e_4c_direct_pump_create_capture_productivity.py` | PASS |
| `tests/test_v2_9_7d_7b_4a_direct_pump_adapter.py` | PASS |
| `tests/test_pumpfun_direct_create_contract_fixture.py` | PASS |
| `tests/test_v2_9_7d_7b_4d_combined_discovery_executor.py` | PASS |
| `tests/test_v2_9_7d_7b_4c_discovery_persistence.py` | PASS |
| `tests/test_v2_9_7d_7b_5_isolated_combined_discovery_proof.py` | PASS |
| `tests/test_v2_9_7d_7b_4b_secondary_discovery_adapters.py` | PASS |
| Combined focused total (direct+4C+executor) | **36 passed** |
| Related persistence/secondary/isolated | **31 passed** (+3 subtests) |
| Network / pilot | **none** |

Proved:

- two-page enumeration + 16 decode ceiling + early-create stop
- failed signatures skip transaction budget
- deterministic admission independent of page order
- supported creates normalize; non-create yields no observation
- non-create alone is not a continuity emergency
- genuine unavailable / unsupported / cutoff gaps remain explicit
- mint-origin success, mint mismatch, failed-only history, `create_v2` block
- request/RPC accounting; deterministic replay
- Governor/Scheduler bypass prevention
- no eligibility/selection/retrieval/decision/position/trade/PnL changes

---

## Money-Usefulness Contribution

Direct capture now spends decode budget on **successful finalized** candidates, records failed/non-create market noise without false continuity emergencies, and can confirm secondary mints via **exact finalized Pump create** mint-scoped lookup when planned under adopted origin kinds. This raises the odds of honest origin-backed dual-slot pools without treating provider labels as origin.

---

## Remaining Unknowns

- Live free-RPC retention for mint history under origin lookup.
- Whether earliest successful mint transaction is usually Pump `create` in production.
- Whether full 2×16 + early stop yields ≥2 creates in live market windows (requires later authorized pilot).
- Live share of `create_v2` among real creates.

---

## What Remains Locked

- Live source proof / pilot / V2-9.7F / V2-9.8
- `create_v2` adoption
- Eligibility gate changes, two-or-none, freshness, cooldown, Tracker policy
- Retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, PnL
- Wallets, keys, live execution, paid APIs, scoring, embeddings
- Migrations / public commands

---

## Functionality Risks / Setbacks / Efficiency Blockers

1. One origin transaction per mint may miss create if the earliest successful mint-involving tx is not Pump `create`.
2. Early-create stop at 8 leaves later creates unread by design.
3. Free RPC history depth remains an operational risk for secondary origin.
4. Operator harnesses must adopt full ceilings (not ad-hoc `limit=4`) before the next pilot expects yield.
5. Continuity now treats failed/non-create as non-fault — operators must read classification counts, not only `GAPPED`.

---

## Diff Checks

- `git diff --check` on lane files (commit time)
- Focused test green set above

## Stop Boundary

Stop after commit. Do not run live source proof, another pilot, V2-9.7F, or V2-9.8.
