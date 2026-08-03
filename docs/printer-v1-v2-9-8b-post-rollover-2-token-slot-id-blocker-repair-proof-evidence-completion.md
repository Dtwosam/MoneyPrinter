# Printer V1 V2-9.8B Post-Rollover-2 `token_slot_id` Repair Proof-Evidence Completion

Date: 2026-08-03

Linear: `DTW-23`

Lane:
`V2-9.8B Post-Rollover-2 Authoritative WINDOW_15M token_slot_id Blocker Repair Proof-Evidence Completion`

Starting closeout commit:
`ed3b89b734820101c9470161ff0ac9f440825d8a`

Accepted implementation HEAD:
`089eb38651874d9b3ec4a4ce04600d45ea401b05`

Proof-test HEAD:
`d5199d77256fdd13cb73b1b92dca07241528e2f8`

Consumed authorization:
`V2_9_8B_WINDOW_15M_AUTH_20260802T210122Z`

The consumed authorization remains permanently non-reusable.

## 1. Verdict

`V2_9_8B_POST_ROLLOVER_2_WINDOW_15M_TOKEN_SLOT_ID_BLOCKER_REPAIR_PROOF_EVIDENCE_COMPLETION_PASS`

The proof-evidence gaps identified by the independent closeout are closed:

1. one focused offline test executes the exact public coordinator ->
   authoritative owner -> real origin driver -> real one-command `WINDOW_15M`
   factory composition;
2. the test preserves structured DB, identity, Scheduler, residue, integrity,
   replay, no-contact, protected-capability, and no-longer-window evidence;
3. the original five blocker-focused proofs and the new exact-composition proof
   pass together;
4. the directly affected regression set passes;
5. syntax compilation and `git diff --check` pass.

This PASS proves the repaired durable `token_slot_id` handoff across the exact
public offline composition. It does not prove clean memory, favorable campaign
acceptance, live readiness, or authorization readiness.

## 2. Scope

Added only:

- `tests/test_v2_9_8b_token_slot_id_exact_public_composition.py`;
- this proof-evidence report.

No production source, schema, migration, Source Governor owner, Central
Scheduler owner, wrapper, authorization law, operational command, memory
quality rule, retrieval rule, decision rule, or financial capability changed.

The accepted one-column production repair remains unchanged:

```sql
SELECT s.token_slot_id, s.slot_ordinal, s.token_row_id, s.pair_row_id,
       s.mint_identity, s.pair_identity, s.token_state,
       p.pair_address, t.token_status
```

The strict consumer remains a direct lookup of:

```python
slot["token_slot_id"]
```

No fallback, reconstruction, alternate identity, `.get()`, optional handling,
or silent validation skip was introduced.

## 3. Exact proof composition

The new focused test executes:

```text
public_command._run_operational_campaign
-> AuthoritativeLiveOperationalCampaignOwner.run_operational
-> OriginToLifecycleCampaignDriver.run
-> CombinedPumpfunCampaignExecutor.execute
-> real discovery-selection terminal stage observer
-> run_one_command_15m_factory
-> two terminal WINDOW_15M closes
-> public accounting/finalization/cleanup/report boundaries
-> deterministic report-only replay
```

The test uses:

- a disposable database migrated through canonical Migration 050;
- the repository's existing canonical-disposable-corpus proof seam;
- frozen Pump create-origin transport;
- frozen GeckoTerminal/DexScreener secondary transport;
- frozen DexScreener snapshot adapters;
- frozen context adapters;
- deterministic compressed test timing;
- real public coordinator, owner, driver, executor, factory, accounting,
  cleanup, and report/replay code;
- a network guard around `urllib.request.urlopen`.

The test does not invoke PowerShell, the one-shot wrapper, an external
operational authorization, the authoritative corpus, real providers, RPC,
WebSockets, retrieval, decisions, positions, trades, audits, PnL, or any longer
window.

## 4. Verification execution

Temporary no-secret CI was used only to execute the clean proof branch.

Temporary draft PR:

- PR: `#15`;
- state: closed;
- merged: false;
- base: proof branch at `d5199d77256fdd13cb73b1b92dca07241528e2f8`;
- head workflow commit: `f2452909bf695b09aa633c6c0a631769500f7d1a`;
- CI merge commit: `e457eadf2196618577c6d7a38d223a0c831953fa`.

Workflow:

- run ID: `30819270514`;
- job ID: `91704741269`;
- conclusion: `success`;
- runner: Ubuntu 24.04;
- Python: 3.11.15;
- permissions: repository contents read-only;
- no repository or environment secrets were supplied to the proof.

The temporary workflow was not merged into the proof branch.

### Compilation

Command:

```bash
python -m py_compile \
  src/printer_v1/operator_cli/origin_lifecycle_campaign.py \
  tests/test_v2_9_8b_token_slot_id_projection_repair.py \
  tests/test_v2_9_8b_token_slot_id_exact_public_composition.py
```

Result: `PASS`, exit `0`.

### Blocker-specific proofs

Command:

```bash
python -m pytest -q -s \
  tests/test_v2_9_8b_token_slot_id_projection_repair.py \
  tests/test_v2_9_8b_token_slot_id_exact_public_composition.py
```

Result:

```text
6 passed in 15.45s
```

This contains:

- the original five projection/driver/public-observer/fail-closed/offline-path
  proofs;
- the new exact public coordinator/owner/driver/factory composition proof.

### Directly affected regressions

Command:

```bash
python -m pytest -q \
  tests/test_v2_9_7e_8_origin_to_lifecycle_integration.py \
  tests/test_v2_9_8b_operational_factory_active_path_restoration.py \
  tests/test_v2_9_8b_post_handoff_terminal_compensation.py \
  tests/test_v2_9_8b_full_run_wiring_integration.py \
  tests/test_v2_9_8b_full_run_accounting_semantics_correction.py \
  tests/test_v2_9_8b_full_run_accounting_terminal_evidence.py \
  tests/test_v2_9_8b_terminal_safety_accounting_finalization.py \
  tests/test_v2_9_8a_public_operational_command.py \
  tests/test_v2_9_8b_window_15m_one_shot_wrapper.py
```

Result:

```text
142 passed, 13 skipped, 6 subtests passed in 103.02s
```

The skips were preserved existing platform/fixture skips; no failure was hidden
or absorbed into this lane.

### Diff check

Command:

```bash
git diff --check
```

Result: `PASS`, exit `0`.

## 5. Durable proof-log identity

GitHub Actions artifact:

- name: `dtw-23-proof-logs`;
- artifact ID: `8858167233`;
- ZIP SHA-256:
  `7e301347760113c07ab3515f4874f926566476b726dabc42e175646bd590a4fa`;
- size: `1589` bytes.

The artifact contains the focused and directly affected pytest transcripts.
The structured evidence below was also emitted directly into the successful
workflow log.

## 6. Structured identity evidence

Schema:

`DTW23_TOKEN_SLOT_ID_EXACT_PUBLIC_COMPOSITION_V1`

Campaign identity:

`20260803T134351Z-f0fd31906f2d-campaign`

Factory-run identity:

`363be14c-13f7-41ea-8505-13630e256427`

Exact durable campaign token-slot IDs:

```text
slot-20260803T134351Z-f0fd31906f2d-cycle-1
slot-20260803T134351Z-f0fd31906f2d-cycle-2
```

The following four identity sets were exactly equal and ordered 1,2:

1. `printer_memory_factory_campaign_token_slots.token_slot_id`;
2. `printer_discovery_selected_item_links.token_slot_id`;
3. the exact `DISCOVERY_SELECTION_TERMINAL` callback slot dictionaries;
4. the two `SELECTION_HANDOFF_VALIDATED` accounting subjects.

Validation ordinals:

```text
1
2
```

This closes the precise composition gap that consumed the prior authorization.
No slot identity was generated, reconstructed, substituted, or made optional at
the consumer boundary.

## 7. Database and lifecycle evidence

Migration identity:

```text
migration_count=50
migration_head=050_campaign_scheduler_ownership_scope.sql
```

Disposable database path for the successful ephemeral run:

`/tmp/tmpm08h2gk9/dtw23-migration-050.sqlite3`

The temporary path is an execution identity only; the disposable DB was not
committed.

Database SHA-256 before exact public run:

`a6d0807e807f45cccd5470ec5942b7ccc71fd5871d6d463a25cecfc4ce36f867`

Database SHA-256 after exact public run:

`143672f17ed51841e517fe5e5533fdc7034603dc234e2976fb739c918e1e0819`

Database SHA-256 before report-only replay:

`143672f17ed51841e517fe5e5533fdc7034603dc234e2976fb739c918e1e0819`

Database SHA-256 after two report-only replays:

`143672f17ed51841e517fe5e5533fdc7034603dc234e2976fb739c918e1e0819`

Lifecycle result:

- runtime status: `COMPLETED`;
- terminal `WINDOW_15M` closes: `2`;
- window kinds present: `WINDOW_15M` only;
- `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, and `WINDOW_24H`: absent;
- report-only replay new source calls: `0`;
- report-only replay new evidence rows: `0`;
- replay database mutation: `0`;
- SQLite sidecars after close: none.

Integrity:

```text
PRAGMA integrity_check = ok
PRAGMA foreign_key_check = []
```

## 8. Scheduler and residue evidence

Scheduler totals after terminal cleanup:

```text
total=30
active=0
locked=0
```

Active-residue matrix after terminal cleanup:

```text
campaigns=0
campaign_runs=0
campaign_supervision=0
discovery_work=0
factory_run_steps=0
scheduler_jobs=0
locked_scheduler_jobs=0
proof_supervision=0
```

The campaign created no retry, rerun, resume, restart, or successor.

```text
automatic_retries=0
reruns=0
resumes=0
restarts=0
successors=0
```

## 9. Source-contact evidence

The test exercised frozen transport objects while guarding the real network
entry point.

External network calls:

```text
0
```

Frozen Pump transport operations:

- signature-history calls: `1`;
- transaction lookups: `liveSigA`, `liveSigB`.

Frozen secondary transport recorded three fixture URLs:

- GeckoTerminal trending pools;
- one exact GeckoTerminal active-pool lookup;
- DexScreener latest token profiles.

These strings are frozen fixture-call identities, not real HTTP operations.
`urllib.request.urlopen` was asserted not called.

Frozen snapshot adapter calls:

- total: `18`;
- exact two token mints alternated through the bounded lifecycle.

Authoritative corpus access or mutation:

```text
0
```

Wrapper invocations:

```text
0
```

External authorization creation or application:

```text
0
```

## 10. Protected-capability evidence

All protected tables remained at zero:

```text
printer_memory_retrieval_matches=0
printer_memory_retrieval_queries=0
printer_paper_audit_reports=0
printer_paper_decisions=0
printer_paper_positions=0
printer_paper_trade_audits=0
printer_paper_trade_events=0
```

No retrieval, decision, BUY/SELL/HOLD, position, trade, paper audit, or PnL
capability was activated.

No wallet, private key, signing, real-fund, live-execution, paid-API, scoring,
ranking, confidence, weighted, embedding, or vector capability changed.

`WINDOW_5M_MICRO_EVENT` remains support-only.

## 11. Runtime completion versus campaign acceptance

The exact public runtime completed and produced two terminal 15-minute closes.
The campaign acceptance axis remained conservative:

```text
campaign_pass=false
campaign_acceptance_verdict=BLOCKED_UNSAFE
```

This does not invalidate the `token_slot_id` proof.

The approved design explicitly requires runtime terminal status, campaign
acceptance, and memory quality to remain separate axes. This lane proves exact
identity transport, lifecycle reachability, terminal closeout, cleanup, and
replay. It does not force clean memory or favorable campaign acceptance.

The `BLOCKED_UNSAFE` acceptance remains factual evidence for a later fresh
readiness review. It must not be rewritten as PASS, used to claim a clean
memory, or bypassed when considering a future authorization.

## 12. Resolution of the previous closeout blockers

### Exact integrated P5 composition

Resolved.

The new test enters through the real public coordinator and retains the real
owner, origin driver, combined executor, public observer, one-command factory,
accounting, terminal cleanup, and replay path in one run.

### Durable concrete evidence

Resolved.

The successful workflow preserved:

- exact commands and exit results;
- focused and affected totals;
- disposable DB identity;
- DB hashes before/after run and replay;
- durable/link/callback/validation identity equality;
- validation ordinals;
- two 15-minute closes;
- Scheduler totals;
- active-residue totals;
- integrity and foreign-key results;
- no-network and no-authoritative-corpus evidence;
- protected-capability zeros;
- no longer windows;
- no retry/rerun/resume/restart/successor;
- no wrapper or authorization activity.

## 13. Money-usefulness contribution

This lane creates no authoritative memory, decision, position, trade, PnL, or
profit claim.

Its contribution is operational reliability and resource protection:

- it proves a future bounded authorization will not fail at the repaired
  `token_slot_id` handoff boundary;
- it preserves exact per-slot attribution needed for trustworthy memory
  ownership and later comparisons;
- it prevents substituted or missing identity from being accepted silently;
- it protects future source budget and single-use authorization capacity from
  the known deterministic failure.

## 14. What this lane improves

- Closes the missing exact public-composition proof.
- Converts summary-only evidence into structured durable evidence.
- Proves the strict consumer receives two exact durable slot IDs.
- Proves the ordinary public path reaches two terminal 15-minute closes offline.
- Proves cleanup, integrity, replay, and protected locks remain intact.
- Preserves campaign acceptance as a separate conservative axis.

## 15. What remains locked

This PASS does not unlock:

- fresh readiness PASS;
- final authorization;
- PowerShell wrapper execution;
- operational source/provider contact;
- authoritative DB mutation;
- authoritative memory generation;
- clean-memory claims;
- `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, or `WINDOW_24H`;
- retrieval;
- paper decisions;
- BUY, SELL, or HOLD;
- paper positions;
- trade events;
- paper-trade audits;
- PnL;
- wallet, private keys, signing, real funds, or live execution;
- paid APIs;
- scoring, ranking, confidence, weighted logic, embeddings, or vectors.

The prior authorization remains consumed and must never be reused.

## 16. Functionality Risks / Setbacks / Efficiency Blockers

### Functionality Risks

- Campaign acceptance remained `BLOCKED_UNSAFE`; the next readiness review must
  inspect that result rather than treating runtime completion as readiness.
- Frozen evidence proves composition and identity, not current provider
  availability or live evidence quality.
- Future changes to the public coordinator, owner, reader, or observer could
  reopen the composition gap if this focused test leaves the regression set.

### Setbacks

- The prior one-shot authorization produced no memory and remains consumed.
- This proof required a separate CI-only workflow because the closeout
  environment could not execute the repository locally.
- No authoritative clean memory has yet been produced by the repaired path.

### Efficiency Blockers

- Temporary CI setup must remain outside the final branch; no permanent workflow
  is adopted by this lane.
- The next independent closeout must verify this report and exact final branch
  scope before readiness work begins.
- A future readiness lane may still block on evidence quality, provider state,
  campaign acceptance, or authoritative corpus state independent of this repair.

## 17. Exact next lane

`V2-9.8B Post-Rollover-2 Authoritative WINDOW_15M token_slot_id Blocker Repair Independent Closeout Re-Review`

That lane is read-only and documentation-only. It may verify this exact proof
commit, successful CI evidence, final two-file scope, and prior closeout blocker
resolution.

It may not contact providers, mutate the authoritative DB, run PowerShell,
create or apply an authorization, generate authoritative memory, activate a
longer window, enable retrieval or decisions, or create any financial
capability.

Final status:

`PROOF_EVIDENCE_COMPLETE_INDEPENDENT_CLOSEOUT_REVIEW_REQUIRED_RUNTIME_LOCKED`
