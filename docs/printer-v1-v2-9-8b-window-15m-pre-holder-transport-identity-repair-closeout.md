# Printer V1 V2-9.8B Exact Pre-Holder Transport-Identity Repair Closeout

## Verdict

`V2_9_8B_WINDOW_15M_PRE_HOLDER_TRANSPORT_IDENTITY_REPAIR_BLOCKED`

The implementation and focused disposable proof passed in GitHub-hosted CI.
Formal PASS remains blocked only because this executor cannot mount or remeasure
the operator's authoritative macOS database and untracked external application
evidence. No authorization or Printer runtime was created or run.

## Baseline

- design branch: `agent/v2-9-8b-window-15m-pre-holder-transport-identity-repair-design`
- design HEAD: `94b85eb72e44f9d0b73c76f52a0f30e30b05e8e4`
- repair branch: `agent/v2-9-8b-window-15m-pre-holder-transport-identity-repair`
- consumed authorization preserved by non-access: `V2_9_8B_WINDOW_15M_AUTH_20260806T131011Z`

## Exact files changed

Production:

- `src/printer_v1/sources/measured_transport.py`
- `src/printer_v1/discovery/memory_observation_activation.py`
- `src/printer_v1/discovery/permanent_discovery_availability.py`
- `src/printer_v1/operator_cli/holder_reliability_budget_control.py`

Tests:

- `tests/test_v2_9_8b_pre_holder_transport_identity_repair.py`
- exact-key fixture updates in the nearest request-scope and manifest suites

## Repair

- `canonical_transport_identity_key` is owned by measured transport and
  normalizes current mappings/dataclasses and historical seven/twelve-field keys
  into the approved seven-field identity.
- production request coverage carries count and keys from the same ledger delta;
  the known GeckoTerminal fallback omission is repaired.
- permanent scoped manifests require exact keys, count/key parity, valid keys,
  within-request uniqueness, and campaign-wide unique ownership.
- request-ID `D = S = M_requests` remains unchanged.
- pre-holder now requires exact `M = C = A` and preserves all six bounded set
  differences plus manifest request/stage owners.
- no count was lowered and no identity was fabricated.

## Focused proof

- RED test was observed before implementation.
- new tests: `14 passed in 0.23s`
- nearest suites: `148 passed in 52.32s`
- Python compilation: PASS
- `git diff --check`: PASS
- provider/runtime/static forbidden-command scan: PASS
- DB migration changes: none

## Authoritative DB and evidence boundary

Controlling pre-repair identity supplied by the operator:

- size: `69328896`
- SHA-256: `7380f9b4c172c218e6c9ab1fed996a06fcdeb90ff67f2b414d805f280403d54e`
- inode: `1230526`
- mtime_ns: `1786022001929258221`

GitHub-hosted CI had no mount or credential path to that database or
`$HOME/PrinterOperations`. It therefore could not mutate those artifacts, but it
also could not perform the required fresh before/after remeasurement. A later
read-only local verification is required before this closeout may be promoted
from BLOCKED to PASS. Do not restore or alter the database.

## Evidence preservation

The executor did not have access to authorization/application roots or the
operator database. It therefore performed no edit, move, deletion, regeneration,
reuse, restore, vacuum, checkpoint, or mutation of the consumed authorization,
requests `1969–1978`, responses `1749–1756`, failures `220–221`, or terminal rows.
Byte-identity verification remains part of the local read-only closeout step.

## Money-usefulness contribution

Exact source-operation identity parity prevents holder admission and memory
formation from relying on unattached or double-owned source-cost claims.

## What improves

- exact identity-bearing source manifests;
- one canonical identity shape;
- exact M/C/A parity;
- request/stage-local bounded diagnostics;
- the prior 9-versus-5 defect becomes reproducible offline.

## What remains locked

Authorization, provider execution, holder runtime, Scheduler runtime, lifecycle,
memory, 1h/4h/12h/24h, retrieval, decisions, positions, trades, PnL, wallets,
paid APIs, scoring, weighting and embeddings remain locked.

## Functionality Risks / Setbacks / Efficiency Blockers

- Local DB/evidence remeasurement is still required for formal closeout.
- Historical unscoped fixtures remain compatibility-only and cannot establish
  permanent operational readiness.
- Full end-to-end blocker readiness hardening remains a later audit/design lane.

## Exact next step

Perform one read-only local DB/evidence verification. If exact identity,
integrity, FK, sidecar, active-residue and consumed-evidence checks pass, amend
only this closeout verdict/evidence section in a dedicated closeout completion
commit. Do not create an authorization.
