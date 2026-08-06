# Printer V1 V2-9.8B WINDOW_15M Checkpoint 1 Terminal Propagation Closeout

## Verdict

`V2_9_8B_WINDOW_15M_CHECKPOINT_1_TERMINAL_PROPAGATION_PASS`

The authorization/wrapper/child-launch segment was audited from the external one-shot owner through the public operational child. One reachable reporting defect and five related trust-boundary defects were confirmed and repaired. The repaired path now uses one child-owned create-once terminal artifact, exact wrapper-validated marker binding, and a strict bounded wrapper projection. No authorization or Printer/provider runtime was executed.

## Baseline and final branch

- rolling design baseline: `f1b404ad6463ffab883b5d56133b56a5b45a470c`
- checkpoint branch: `agent/v2-9-8b-window-15m-checkpoint-1-terminal-propagation`
- Linear tracker: `DTW-27`

## Production path inspected

```text
final authorization package
-> one-shot manifest/marker owner
-> lexical repository venv child selection
-> child environment construction
-> operational child main
-> structured action-local terminal truth
-> child exit
-> wrapper terminal report
```

## Confirmed findings

All findings are classified `REPORTING_OR_DIAGNOSTIC_DEFECT_CONFIRMED`.

1. The operational child produced structured exception truth only on redirected stderr. The wrapper recorded `CHILD_EXITED_NONZERO`, exit code, and stdout/stderr identities but had no canonical child terminal artifact.
2. The first implementation accepted unknown terminal-envelope fields and projected the full envelope, allowing unapproved nested content to enter wrapper evidence.
3. Git-provenance validation occurred before the child established its reporting binding, so a valid wrapper context with invalid provenance could still lose the structured cause.
4. The initial child binding used the marker's current hash rather than requiring the exact marker SHA already validated and supplied by the wrapper.
5. If action-local terminal-truth reconstruction raised while handling the original campaign exception, that secondary failure escaped the exception handler and prevented `child-terminal.json` from being written, returning diagnosis to stderr-only evidence.
6. The first reconstruction-failure fallback still coerced unavailable lifecycle, active-work, Scheduler, and phase facts into `False`, `{}`, `0`, and `CAMPAIGN_PRE_LIFECYCLE`, creating false certainty after the truth owner had failed.

No wrapper authorization-consumption, retry, restart, successor, source, Scheduler, campaign, lifecycle, memory, or DB-schema defect was proven in this checkpoint.

## Repair

- Added `printer_v1.operator_cli.window_15m_child_terminal` as the sole child-terminal schema/binding/write/read owner.
- Added `PRINTER_V1_WINDOW_15M_CHILD_TERMINAL_PATH`, separate from the four manifest/marker binding variables.
- Wrapper binds the exact `child-terminal.json` sibling of `application-marker.json`.
- Child requires the wrapper-provided marker SHA and rejects marker drift before creating terminal evidence.
- Child writes exactly one canonical, bounded, source-safe terminal JSON for ordinary-run success or handled failure.
- Child establishes reporting early enough to capture fully bound wrapper provenance-validation failures while preserving the original direct-unwrapped-run rejection.
- Child writes failure evidence only after the public command has completed its own terminalization/cleanup path and the action-local truth envelope has been built.
- If terminal-truth reconstruction itself fails, the original campaign exception remains the first cause; the secondary reconstruction error is bounded separately, mutation/source/write truth becomes explicitly unknown rather than fabricated, and the child terminal is still written.
- Reconstruction failure now preserves lifecycle, active-work, Scheduler, cleanup, lease, database-identity, and phase facts as explicitly unknown unless independently proven; the phase is classified `CAMPAIGN_PHASE_UNKNOWN_TERMINAL_TRUTH_RECONSTRUCTION_FAILED` rather than guessed.
- Wrapper enforces an exact field allowlist plus required-field and value-shape validation before projection.
- Wrapper validates exact authorization ID, marker path/hash, mode, process exit code, success/category parity, schema, file type, sibling path, and size.
- Wrapper projects the exact child first cause, phase, cleanup/lease status, bounded active work, DB identity, and operation/write counts.
- Missing or malformed child terminal evidence produces an explicit `*_TERMINAL_INVALID` classification.
- Process-start/bootstrap failures remain distinct and do not require a child artifact.
- stderr is never parsed as terminal truth and remains immutable debugging evidence.

## Source-safety and bounds

- maximum child terminal size: 64 KiB;
- exact top-level field allowlist;
- bounded text fields and active-work mapping;
- strict database-identity shape;
- URLs, authorization headers, bearer values, API-key/secret markers, cookies, and private-key-like terminal details are redacted or rejected;
- provider payloads, response bodies, headers, unknown fields, and unbounded lists are not projected.

## Files changed

Production:

- `src/printer_v1/operator_cli/window_15m_child_terminal.py`
- `src/printer_v1/operator_cli/window_15m_one_shot_wrapper.py`
- `src/printer_v1/operator_cli/operational_memory_factory_command.py`

Tests:

- `tests/test_v2_9_8b_window_15m_child_terminal_propagation.py`
- `tests/test_v2_9_8b_window_15m_one_shot_wrapper.py`

Documentation:

- `docs/printer-v1-v2-9-8b-window-15m-checkpoint-1-terminal-propagation-closeout.md`

## Test-first proof

Six distinct RED gates were observed before their repairs:

1. wrapper omitted the child-terminal environment binding;
2. the initial reader accepted unknown/missing/internally inconsistent envelope data;
3. provenance validation could fail before a child terminal was created;
4. marker drift after wrapper validation was not rejected by the child binding;
5. a secondary action-local terminal-truth reconstruction exception erased the structured child artifact and allowed the original campaign cause to escape back to stderr-only evidence;
6. reconstruction failure fabricated unavailable lifecycle, active-work, Scheduler, and campaign-phase facts instead of preserving them as unknown.

- focused terminal/wrapper tests: `58 passed, 2 skipped in 2.67s`
- exact neighboring operational terminal tests: `141 passed, 8 deselected, 22 subtests passed in 111.31s (0:01:51)`
- changed-module Python compilation: PASS
- `git diff --check`: PASS
- migration/script/provider-command change scan: PASS

## Unrelated pre-existing failures

The following historical tests failed for reasons that predate and are unrelated
to the reporting-only Checkpoint 1 diff. They were documented and excluded by
exact node rather than repaired or used to broaden scope.

1. Broad readiness collection failure:

```text
tests/test_v2_9_8b_window_15m_final_integrated_readiness_repair.py
ImportError: cannot import name '_attach_fingerprint_for_episode'
from printer_v1.operator_cli.lane_k_e2z_pipeline_wiring
```

2. One historical ordinary-regression test omits the now-required operational DB
target binding and blocks with:

```text
OPERATIONAL_DB_BINDING_MISSING: database target binding
```

3. Seven historical campaign-terminal assertions require migration head `050`,
while the active migrated repository head is `052_memory_observation_eligibility_layers.sql`.
The terminal behavior preceding those stale head assertions passed.

Before exact deselection, the neighboring run produced:

```text
141 passed, 22 subtests passed, 8 failed
```

The eight failures were exactly the one missing-binding node and seven stale
migration-head nodes above. All remaining exact terminal-neighbor tests remained
mandatory in the final proof.

## Runtime and evidence boundary

- no authorization was created, modified, reused, rebound, or consumed;
- no wrapper application or public operational command was run;
- no provider was contacted;
- no discovery, holder, Scheduler, campaign, lifecycle, or memory runtime ran;
- no authoritative DB was opened or mutated by the proof;
- historical authorization/application evidence remains immutable.

## Money-usefulness contribution

Future failures can now be classified from bounded structured evidence immediately, reducing repeated authorization consumption for diagnosis and protecting clean-memory operations from ambiguous terminal reporting.

## What improves

- exact child-to-wrapper first-cause propagation;
- structured failure phase and cleanup evidence;
- exact binding to wrapper-validated marker bytes;
- preservation of the original campaign cause when secondary terminal-truth reconstruction fails;
- explicit `RECONSTRUCTION_FAILED` evidence without fabricated source, write, lifecycle, active-work, Scheduler, cleanup, lease, database-identity, or phase facts;
- strict envelope allowlisting and source safety;
- explicit invalid-terminal classification;
- no dependence on stderr parsing;
- permanent fixture regressions for success, failure, redaction, unknown fields, path binding, marker drift, provenance ordering, and exit-code/category parity.

## What remains locked

Authorization, provider execution, live `WINDOW_15M`, selective 1h, 4h/12h/24h, retrieval, decisions, BUY/SELL/HOLD, positions, trades, audits, PnL, wallets, real funds, paid APIs, scoring, ranking, confidence, weighting, embeddings, and vectors.

## Functionality Risks / Setbacks / Efficiency Blockers

- A child killed before handled shutdown may not produce an envelope; the wrapper reports terminal-invalid while preserving stdout/stderr and exit code.
- When action-local reconstruction fails, several operational facts remain intentionally `null`; later checkpoints must inspect their durable owners rather than treating unknown as zero.
- The envelope is reporting evidence, not a new campaign authority; later checkpoints must verify cleanup truth at its durable owners.
- Historical wrappers remain unchanged and cannot retroactively gain structured child evidence.
- The unrelated historical readiness-test import failure remains outside this checkpoint and must not silently become a completion blocker for unrelated lanes.
- Checkpoint 2 must inspect whether every preflight/initialization failure reaches the child writer with the correct phase and zero/mutated DB truth.

## Exact next step

Begin Checkpoint 2: audit the child zero-source preflight, authoritative DB safety, provenance/migration gates, recovery ordering, and campaign/supervision initialization. Do not create an authorization or run Printer.
