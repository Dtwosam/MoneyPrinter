# Printer V1 V2-9.7B.2 Timeframe-Aware Safety Label Closeout

## Verdict

V2_9_7B_2_TIMEFRAME_AWARE_SAFETY_LABEL_PASS

V2-9.7B.2 is complete. Current 15m, 1h, and 4h reporting now exposes a
canonical timeframe-neutral effective safety-context result while preserving
legacy source and stored labels as raw evidence.

The repair changes reporting only. It does not alter safety acceptance,
evidence collection, persistence schemas, historical rows, E2Q, Lane Q,
Lane K, or E2Z promotion policy.

## Preflight

- Required starting commit: d604926
- Observed starting HEAD: d604926
- Tracked tree at start: clean
- Active Python/runtime processes at start: 0
- Active V2-9 one-proof lock: absent
- Persistent corpus DB: data/printer_v1.sqlite3
- Persistent DB SHA-256 before work:
  97DB9A15CC464D86137CBBB0DD0A4EF1880E9F4E231FB41E8B22CA09FB177FBB
- Persistent DB size before work: 13,017,088 bytes
- Unrelated untracked artifacts: observed and left untouched

No source, discovery, runtime, proof-launcher, or memory-growth command ran.

## Static Inspection

The inspection covered all direct producers, consumers, persisted fields, and
tests for the contradictory labels.

### Producers

- safety/goplus_normalizer.py produces raw provider-derived safety evidence and
  the legacy SAFETY_ACCEPTABLE_FOR_15M_MEMORY_ONLY policy label.
- safety/composite.py persists the legacy safety_contract_label and owns the
  unchanged effective acceptance predicate.
- context_evidence/window_15m.py previously synthesized BLOCK_CLEAN_MEMORY as
  the default action label even after the exact composite gate accepted.
- operator_cli/commands.py previously overlaid the legacy contract label as the
  effective safety status for persisted window audit reporting.

### Consumers

- The shared context resolver serves current WINDOW_15M and WINDOW_4H paths.
- The audit-evidence overlay serves persisted window audit reporting and can
  receive WINDOW_15M, WINDOW_1H, or WINDOW_4H.
- Memory-quality consumers continue receiving the backward-compatible
  safety_status_label. The new canonical result is additional reporting
  context and does not replace an acceptance predicate.

### Persistence

- printer_solana_safety_evidence remains unchanged.
- printer_safety_evidence_composites remains unchanged.
- safety_context_label, safety_contract_label, optional_unknowns_json,
  blockers_json, field bindings, source trace, and provenance remain unchanged.
- No migration or historical row rewrite was made.

## Repair

A single neutral reporting helper now receives the already-decided gate result,
the source/stored row, and the explicit window_kind. It returns:

- window_kind
- effective_safety_context_result
- raw_safety_context_label
- raw_safety_contract_label
- raw_safety_action_label

The shared resolver and persisted-window audit overlay expose these fields.
window_kind remains a separate fact and is not encoded into the effective
safety label.

safety_action_label now presents the canonical effective result. A legacy raw
BLOCK_CLEAN_MEMORY value remains readable under raw_safety_action_label and is
not presented as the final action after the approved gate accepts the exact
evidence.

The backward-compatible safety_status_label remains available. This avoids
rewriting existing consumers or stored evidence while making the authoritative
effective result unambiguous.

## Exact Legacy-to-Effective Mapping

The mapping is controlled by the unchanged effective gate outcome, never by a
legacy label alone.

| Gate evaluation | Raw/source examples retained | Effective result |
|---|---|---|
| Accepted | SAFETY_CLEAN | SAFETY_CONTEXT_ACCEPTABLE |
| Accepted | SAFETY_ACCEPTABLE_FOR_15M_MEMORY_ONLY | SAFETY_CONTEXT_ACCEPTABLE |
| Accepted | raw BLOCK_CLEAN_MEMORY action plus an accepted exact composite | SAFETY_CONTEXT_ACCEPTABLE |
| Rejected | SAFETY_BLOCKED_FOR_15M_MEMORY | SAFETY_CONTEXT_BLOCKED |
| Rejected | explicit provider risk, exact-pair unlocked/removed liquidity, unsafe concentration, failed/stale/mismatched/untraceable evidence, or missing mandatory evidence | SAFETY_CONTEXT_BLOCKED |
| Not evaluated | absent or unevaluated context | SAFETY_CONTEXT_UNKNOWN |

SAFETY_CONTEXT_UNKNOWN is not an acceptance. Optional unknown LP semantics and
other source-coverage unknowns remain visible in raw fields and
source_coverage_pending_fields. They are never relabeled as known safe.

Legacy stored labels remain valid inputs to the existing acceptance predicate.
No new label independently grants acceptance.

## Safety Contract Preserved

The following behavior is unchanged:

- Mandatory evidence remains mandatory.
- Stale, failed, mismatched, untraceable, and missing mandatory evidence blocks.
- Explicit provider risk blocks.
- Explicit exact-pair unlocked or removed liquidity blocks.
- Unsafe or extreme holder concentration blocks.
- Unsupported optional LP semantics remain unknown.
- Optional unknowns are never relabeled as known safe.
- Exact target, freshness, provenance, source quality, blocker, and paper-only
  checks remain mandatory.
- No safety result unlocks retrieval or financial capabilities.

No new external GoPlus, pool, holder, LP, or provider-schema claim was made.
Anything not established by adopted code and tests remains
UNKNOWN_REQUIRES_RESEARCH.

## Verification Results

Focused and nearest fixture-only verification:

- 77/77 tests passed across:
  - V2-9.7B.2 timeframe-aware safety reporting
  - V2-4.1 composite safety contract
  - V2-4.1 shared context evidence
  - V2-4 one-command 15m factory
  - V2-6 1h audit gate
  - V2-8.1 one-token 4h runtime
  - V2-9.4.6 exact 4h closing boundary
  - V2-9.7B.1 authoritative promotion reporting
- 6/6 focused V2-9.7B.2 and V2-9.7B.1 tests passed again after the final
  legacy-action compatibility assertion.
- Accepted WINDOW_15M reports SAFETY_CONTEXT_ACCEPTABLE.
- Accepted WINDOW_1H reports SAFETY_CONTEXT_ACCEPTABLE.
- Accepted WINDOW_4H reports SAFETY_CONTEXT_ACCEPTABLE.
- Each effective report retains its actual window_kind.
- Explicit danger reports SAFETY_CONTEXT_BLOCKED.
- Missing mandatory evidence reports SAFETY_CONTEXT_BLOCKED.
- Optional unknown evidence remains visible as raw SAFETY_UNKNOWN and in
  source-coverage pending fields.
- Legacy SAFETY_ACCEPTABLE_FOR_15M_MEMORY_ONLY and BLOCK_CLEAN_MEMORY values
  remain readable as raw inputs.
- The composite acceptance predicate was not changed.
- V2-9.7B.1 authoritative-promotion reporting remains unchanged.
- Existing retrieval and financial forbidden-delta checks remain zero.
- Python compilation passed.
- git diff --check passed.

All database-backed tests used temporary isolated databases.

## Persistent DB Verification

- SHA-256 after implementation and tests:
  97DB9A15CC464D86137CBBB0DD0A4EF1880E9F4E231FB41E8B22CA09FB177FBB
- Size after implementation and tests: 13,017,088 bytes
- Result: byte-for-byte hash unchanged.
- Active runtime after tests: none.
- Active V2-9 proof lock after tests: absent.

## Money-Usefulness Contribution

The repair makes campaign safety reporting interpretable across the actual
memory lifecycle. Operators can distinguish raw provider uncertainty from the
approved composite gate outcome without mistaking a legacy 15m-only phrase or
synthetic block action for a rejected 1h or 4h context.

This improves corpus-quality review and prevents false safety-failure counts.
It does not make a trading recommendation, claim profit, or loosen any
evidence requirement.

## What This Lane Improves

- Adds one canonical effective safety vocabulary across 15m, 1h, and 4h.
- Separates raw/source safety state from effective composite-gate outcome.
- Removes contradictory effective BLOCK_CLEAN_MEMORY presentation after
  accepted exact evidence.
- Keeps window_kind explicit and separate from label semantics.
- Preserves historical and current legacy label readability.
- Preserves optional unknowns honestly.
- Closes the timeframe-confusing safety-label blocker from V2-9.7A.

## What Remains Locked

- Operational memory growth
- V2-9.7C, V2-9.7D, V2-9.7E, and V2-9.8 activation
- Retrieval and similarity activation
- Paper decisions
- BUY, SELL, and HOLD
- Paper positions and trade events
- Paper audits and PnL
- Live trading, wallets, private keys, signing, and real funds
- Paid APIs
- Scoring, ranking, confidence percentages, and weighted logic
- Migrations and historical row rewrites

Tracking queue/lifecycle behavior, heartbeat supervision, embedded Git
provenance, and other remaining V2-9.7A blockers were not repaired.

## Proof Requirements Completed

- Static producer/consumer/persistence/test inspection: complete
- 15m accepted reporting: complete
- 1h accepted reporting: complete
- 4h accepted reporting: complete
- Explicit window_kind retention: complete
- Explicit danger remains blocked: complete
- Missing mandatory evidence remains blocked: complete
- Optional unknown evidence remains raw and visible: complete
- Legacy label readability: complete
- No acceptance broadening: complete
- V2-9.7B.1 regression: complete
- Zero retrieval and financial deltas: complete
- Focused and nearest regressions: complete
- Python compilation: complete
- Persistent DB hash unchanged: complete
- Accidental-unlock scan and git diff --check: complete

No live proof or additional four-hour proof was required or run.

## Functionality Risks / Setbacks / Efficiency Blockers

### Functionality Risks

- Backward-compatible safety_status_label can still contain a legacy phrase.
  Consumers requiring the authoritative current result must use
  effective_safety_context_result.
- SAFETY_CONTEXT_UNKNOWN is reserved for a gate that was not evaluated. A
  completed evaluation with missing mandatory evidence remains blocked, even
  if individual raw fields are unknown.
- Optional unknown evidence remains visible and may look conservative to an
  operator. That is intentional and must not be converted into known-safe
  semantics.

### Setbacks

- The packaged patch helper remained inaccessible under the Windows app
  sandbox. Guarded exact-match workspace replacements were used and then
  verified by compilation, tests, and diff inspection.
- Temporary SQLite fixture suites require execution outside the restricted
  filesystem wrapper on this host. They remained fixture-only and passed.

### Efficiency Blockers

- The legacy persisted safety_contract_label vocabulary cannot be renamed
  without a migration and historical compatibility plan, both prohibited in
  this lane.
- Some older consumers still display safety_status_label. Migrating display
  consumers to prefer effective_safety_context_result may be considered only
  in a separately approved compatible lane if needed.
- Unsupported provider and pool semantics remain UNKNOWN_REQUIRES_RESEARCH.

## Files Changed

- src/printer_v1/safety/composite.py
- src/printer_v1/context_evidence/window_15m.py
- src/printer_v1/operator_cli/commands.py
- tests/test_v2_9_7b_2_timeframe_aware_safety_reporting.py
- tests/test_v2_4_1_shared_context_evidence.py
- tests/test_v2_4_one_command_15m_factory.py
- tests/test_v2_9_4_6_exact_closing_boundary.py
- docs/printer-v1-v2-9-7b-2-timeframe-aware-safety-label-closeout.md

## Final Status

V2_9_7B_2_TIMEFRAME_AWARE_SAFETY_LABEL_PASS

The next work remains a separately authorized V2-9.7B repair lane. This
closeout does not start V2-9.7C/D/E, operational memory growth, V2-9.8, or
V2-10.