from __future__ import annotations

import os
from pathlib import Path

new_summary = os.environ.get("NEW_TEST_SUMMARY", "UNKNOWN")
near_summary = os.environ.get("NEAREST_TEST_SUMMARY", "UNKNOWN")
content = f'''# Printer V1 V2-9.8B WINDOW_15M Checkpoint 1 Terminal Propagation Closeout

## Verdict

`V2_9_8B_WINDOW_15M_CHECKPOINT_1_TERMINAL_PROPAGATION_PASS`

The authorization/wrapper/child-launch segment was audited from the external one-shot owner through the public operational child. One reachable reporting defect was confirmed and repaired: the child already constructed structured terminal truth, but the wrapper received only an exit code and stderr file identity. The repaired path now uses one child-owned create-once terminal artifact and a strict bounded wrapper projection. No authorization or Printer/provider runtime was executed.

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

## Confirmed finding

Classification: `REPORTING_OR_DIAGNOSTIC_DEFECT_CONFIRMED`.

Root cause:

- `operational_memory_factory_command.main` produced a structured exception envelope;
- that envelope was printed only to redirected stderr;
- `window_15m_one_shot_wrapper.apply_authorization_once` recorded only `CHILD_EXITED_NONZERO`, exit code, and stdout/stderr identities;
- no canonical child terminal binding or artifact existed;
- `child-stderr.txt` therefore remained the only place carrying the precise campaign cause.

No wrapper authorization-consumption, retry, restart, successor, source, Scheduler, campaign, lifecycle, memory, or DB-schema defect was proven in this checkpoint.

## Repair

- Added `printer_v1.operator_cli.window_15m_child_terminal` as the sole child-terminal schema/binding/write/read owner.
- Added `PRINTER_V1_WINDOW_15M_CHILD_TERMINAL_PATH`, separate from the four manifest/marker binding variables.
- Wrapper binds the exact `child-terminal.json` sibling of `application-marker.json`.
- Child writes exactly one canonical, bounded, source-safe terminal JSON for ordinary-run success or handled failure.
- Child writes failure evidence only after the public command has completed its own terminalization/cleanup path and the action-local truth envelope has been built.
- Wrapper validates exact authorization ID, marker path/hash, mode, process exit code, success parity, schema, file type, sibling path, and size before projection.
- Wrapper projects the exact child first cause, phase, cleanup/lease status, bounded active work, DB identity, and operation/write counts.
- Missing or malformed child terminal evidence produces an explicit `*_TERMINAL_INVALID` classification.
- Process-start/bootstrap failures remain distinct and do not require a child artifact.
- stderr is never parsed as terminal truth and remains immutable debugging evidence.

## Source-safety and bounds

- maximum child terminal size: 64 KiB;
- bounded text fields and active-work mapping;
- URLs, authorization headers, bearer values, API-key/secret markers, cookies, and private-key-like terminal details are redacted;
- provider payloads, response bodies, headers, and unbounded lists are not projected.

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

- RED: the wrapper did not supply the child-terminal binding or project a child cause on the controlling baseline.
- focused terminal/wrapper tests: `{new_summary}`
- nearest selected operational terminal tests: `{near_summary}`
- changed-module Python compilation: PASS
- `git diff --check`: PASS
- migration/script/provider-command change scan: PASS

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
- explicit invalid-terminal classification;
- no dependence on stderr parsing;
- permanent fixture regressions for success, failure, redaction, path binding, and exit-code parity.

## What remains locked

Authorization, provider execution, live `WINDOW_15M`, selective 1h, 4h/12h/24h, retrieval, decisions, BUY/SELL/HOLD, positions, trades, audits, PnL, wallets, real funds, paid APIs, scoring, ranking, confidence, weighting, embeddings, and vectors.

## Functionality Risks / Setbacks / Efficiency Blockers

- A child killed before handled shutdown may not produce an envelope; the wrapper reports terminal-invalid while preserving stdout/stderr and exit code.
- The envelope is reporting evidence, not a new campaign authority; later checkpoints must verify cleanup truth at its durable owners.
- Historical wrappers remain unchanged and cannot retroactively gain structured child evidence.
- Checkpoint 2 must inspect whether every preflight/initialization failure reaches the child writer with the correct phase and zero/mutated DB truth.

## Exact next step

Begin Checkpoint 2: audit the child zero-source preflight, authoritative DB safety, provenance/migration gates, recovery ordering, and campaign/supervision initialization. Do not create an authorization or run Printer.
'''
path = Path(
    "docs/printer-v1-v2-9-8b-window-15m-checkpoint-1-terminal-propagation-closeout.md"
)
path.write_text(content, encoding="utf-8")
print(path)
