# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 Re-proof Readiness Decision

## Verdict

`V2_9_8B_WINDOW_15M_CHECKPOINT_8_REPROOF_PROPOSAL_READY_AWAITING_EXPLICIT_OPERATOR_AUTHORIZATION`

The blocked Checkpoint 8 proof has been audited, repaired offline, and closed out with focused GREEN evidence. A fresh bounded re-proof may now be **proposed** for operator authorization, but no new controlling proof is authorized by this document.

The historical controlling attempt remains permanently recorded as:

`V2_9_8B_WINDOW_15M_CHECKPOINT_8_CONTROLLING_PROOF_BLOCKED_NO_RERUN`

This readiness decision does not reinterpret, retry, resume, or erase that failed attempt.

## Governing source stack

This decision remains subordinate to:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-current-state-memory-growth-audit.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`

## Readiness lineage reviewed

Historical failed proof:

- approved proof HEAD: `e263f5f3c6539b983314f7e66ea720ed4ec2e935`
- proof ID: `C8_CONTROLLING_E263F5F3_20260807`
- Actions run: `31180769946`
- result: `HONEST_BLOCKED / SOURCE_AVAILABILITY_FAILURE`
- one-shot entitlement consumed; no rerun allowed

Blocker audit:

- commit: `0d3ad289d33f647d2ce24a96d9adc1611fb2e29a`
- verdict: `V2_9_8B_WINDOW_15M_CHECKPOINT_8_BLOCKER_AUDIT_CONFIRMED_THREE_PROOF_CONTRACT_DEFECTS`

Repair design:

- commit: `e443574a5b9c6fc971897d5ccbf34bb8ebc287e3`
- status: `V2_9_8B_WINDOW_15M_CHECKPOINT_8_BLOCKED_PROOF_REPAIR_DESIGN_APPROVED_FOR_OFFLINE_IMPLEMENTATION_ONLY`

Offline implementation:

- migration/terminal repair: `5bfcd7b51dcd311c5d1a1aebf4fb8b9e6f79f23a`
- real-consumer compatibility repair: `9feee2b102b31bb2ae095d3092956fee322036b4`

Repair closeout:

- commit: `4fe933751f4af24fb7c3ca31e3c87b5053969a67`
- verdict: `V2_9_8B_WINDOW_15M_CHECKPOINT_8_BLOCKED_PROOF_OFFLINE_REPAIR_PASS_NO_REPROOF_AUTHORIZATION`

## Verification reviewed

The final offline repair gate proved:

- blocked-repair tests: `4/4` GREEN;
- real-consumer compatibility tests: `2/2` GREEN;
- full focused Checkpoint 8 wildcard gate: `93/93` GREEN;
- proof harness `py_compile`: PASS;
- compatibility helper `py_compile`: PASS;
- offline static guard: PASS;
- `git diff --check`: PASS;
- zero external-network attempt under compatibility probes;
- all 20 canonical labels accepted through real consumer/normalizer/factory boundaries;
- zero generic READY placeholders;
- zero fixture-self returns accepted as evidence;
- no public campaign call during repair verification.

The final GREEN code state was `9feee2b102b31bb2ae095d3092956fee322036b4`. Commits through `93253162aaece974e0cc9d882d7eef68fe658beb` only removed five temporary CI workflow files. Commit `4fe933751f4af24fb7c3ca31e3c87b5053969a67` then added only the repair closeout document.

No temporary Checkpoint 8 repair workflow remains in the repair lineage.

## Re-proof proposal

A new proof is technically ready to be proposed, subject to explicit operator authorization.

Proposed proof identity:

`C8_REPROOF_AFTER_OFFLINE_REPAIR_20260807`

A future authorization must pin the exact authorization-time repository HEAD. It must descend from the repaired/closed-out lineage above and must contain no unreviewed runtime or source-owner change after the 93-test GREEN state.

Required fresh resources:

- fresh canonically migrated disposable SQLite DB;
- fresh disposable artifact root;
- fresh one-shot sentinel namespace specific to the new proof ID;
- exact canonical 20-label fixture composition;
- process-local network tripwire;
- no provider fallback;
- no retry/rerun/resume/restart/successor path.

## Proposed acceptance law

The future proof may be authorized only for ordinary `WINDOW_15M` and must prove all of the existing C8 acceptance requirements:

- exactly one public `run_operational_campaign()` call;
- exact one-shot sentinel consumed immediately before the public call;
- real Source Governor ownership;
- real Central Scheduler ownership;
- deterministic offline fixture transports only;
- zero external-network/provider attempts;
- exactly two distinct current-run terminal `WINDOW_15M` windows;
- both terminal memories `CLEAN_MEMORY`;
- both memory fingerprints present;
- `CAMPAIGN_PASS`;
- cleanup complete;
- lease released;
- zero active/orphan Scheduler/discovery residue;
- exactly one `report_only()` replay;
- replay source calls, Scheduler calls, and DB writes all zero;
- frozen-summary identity/hash parity;
- independent read-only inspection PASS;
- zero protected downstream capability deltas;
- no `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, or `WINDOW_24H` activation;
- no retry/rerun/resume/restart/successor.

`WINDOW_5M_MICRO_EVENT` remains support-only and cannot become a main memory outcome or unlock retrieval/decisions/trading.

## Operator-authorization boundary

This document does **not** authorize the proposed proof.

A future proof may start only after an operator explicitly authorizes a fresh Checkpoint 8 re-proof attempt. Generic instructions to continue work, automate the project, or handle remaining tasks are not sufficient to consume this authorization boundary.

The explicit authorization should state that a **fresh re-proof attempt** is approved after the offline repair and should identify or accept the proposed proof lane. Only then may an authorization commit/document pin the exact HEAD and permit one new attempt.

## Money-usefulness contribution

This readiness decision preserves the value of the original failure while making the repaired proof path ready for a deliberate second evidence-gathering attempt. It reduces the risk that automated `WINDOW_15M` memory growth is accepted on fixture-only semantics, while preventing repeated proof attempts from becoming an implicit search for a passing result.

## What this lane improves

- confirms the repair lineage is complete and focused;
- confirms the repaired code state is backed by 93 focused GREEN tests;
- confirms all 20 fixture routes are consumer-compatible offline;
- defines the exact safety and evidence law for a possible fresh re-proof;
- separates technical readiness from operator authorization.

## What remains locked

Until explicit operator authorization is recorded, the following remain locked:

- any second controlling proof;
- public campaign runtime;
- source fetching;
- memory generation outside offline tests;
- `WINDOW_1H+` activation;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- paper positions;
- trade events;
- trade audits;
- PnL;
- live wallet/private keys/real funds/live execution.

## Proof/test needed before completion

DTW-38 readiness is complete with this decision. A later operator-authorization lane must:

1. record explicit operator approval;
2. pin the exact approved HEAD;
3. create the fresh proof identity/resources without touching the historical sentinel;
4. perform a final minimum pre-execution integrity check;
5. authorize exactly one new bounded proof attempt.

No runtime is part of DTW-38 completion.

## Functionality Risks / Setbacks / Efficiency Blockers

- Offline compatibility cannot prove full campaign/lifecycle success; only a separately authorized bounded proof can do that.
- The original failed attempt remains historical evidence and must remain distinguishable from any later proof.
- A new proof without explicit operator authorization would violate the one-shot governance boundary.
- Any code/runtime change after the reviewed repair lineage requires a new readiness review before proof execution.
- The proof remains intentionally `WINDOW_15M` only; no longer-window evidence is being sought here.

## Stop condition

Readiness decision complete. Stop before runtime. Await explicit operator authorization for a fresh Checkpoint 8 re-proof attempt.
