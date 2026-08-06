# Printer V1 V2-9.8B Exact Pre-Holder Transport-Identity Repair Closeout

## Verdict

`V2_9_8B_WINDOW_15M_PRE_HOLDER_TRANSPORT_IDENTITY_REPAIR_PASS`

The approved exact pre-holder transport-identity reconciliation repair is implemented, focused disposable proof passed, and the operator completed the required read-only local database and failed-evidence verification. No authorization was created and Printer was not run.

## Baseline

- design branch: `agent/v2-9-8b-window-15m-pre-holder-transport-identity-repair-design`
- design HEAD: `94b85eb72e44f9d0b73c76f52a0f30e30b05e8e4`
- implementation branch: `agent/v2-9-8b-window-15m-pre-holder-transport-identity-repair`
- implementation commit: `f977bc4f1000e53fc3971ad7371056616a4a219d`
- closeout-completion branch: `agent/v2-9-8b-window-15m-pre-holder-transport-identity-repair-closeout-completion`
- consumed authorization preserved: `V2_9_8B_WINDOW_15M_AUTH_20260806T131011Z`
- controlling execution: `20260806T131312Z-829382105482`

## Exact files changed

Production:

- `src/printer_v1/sources/measured_transport.py`
- `src/printer_v1/discovery/memory_observation_activation.py`
- `src/printer_v1/discovery/permanent_discovery_availability.py`
- `src/printer_v1/operator_cli/holder_reliability_budget_control.py`

Tests:

- `tests/test_v2_9_8b_pre_holder_transport_identity_repair.py`
- exact-key fixture updates in the nearest request-scope and manifest suites

Documentation:

- `docs/printer-v1-v2-9-8b-window-15m-pre-holder-transport-identity-repair-closeout.md`

## Repair delivered

- `canonical_transport_identity_key` is owned by measured transport and normalizes current mappings/dataclasses plus exact historical seven-field and twelve-field keys into the approved seven-field identity.
- Production source-request coverage carries `transport_identity_count` and `transport_identity_keys` from the same measured-ledger delta.
- The known GeckoTerminal reconciliation fallback omission is repaired.
- Permanent scoped manifests require exact keys, count/key parity, valid keys, within-request uniqueness, and campaign-wide unique ownership.
- Request-ID reconciliation remains `D = S = M_requests`.
- Pre-holder now constructs exact manifest, campaign-owner, and action-local identity sets and requires `M = C = A`.
- All six bounded set differences are preserved on failure.
- Manifest request/stage owners reported in diagnostics are limited to actual mismatched manifest keys.
- No transport count was lowered and no identity was fabricated.

## Focused disposable proof

- RED test observed before implementation: PASS
- new focused tests: `14 passed in 0.23s`
- nearest selected suites: `148 passed in 52.32s`
- Python compilation: PASS
- `git diff --check`: PASS
- forbidden runtime/provider static scan: PASS
- DB migration changes: none
- provider/runtime execution: none

## Authoritative database verification

Read-only local verification completed against:

`/Users/Dtwo1/Developer/MoneyPrinter/data/printer_v1.sqlite3`

Exact identity before and after repair work:

- size: `69328896`
- SHA-256: `7380f9b4c172c218e6c9ab1fed996a06fcdeb90ff67f2b414d805f280403d54e`
- inode: `1230526`
- mtime_ns: `1786022001929258221`

Verification results:

- exact identity match: PASS
- integrity check: `ok`
- foreign-key violations: `0`
- WAL sidecar: absent
- SHM sidecar: absent
- journal sidecar: absent
- campaign runs active: `0`
- campaign supervision active: `0`
- campaigns active: `0`
- discovery work active: `0`
- factory run steps active: `0`
- locked Scheduler jobs: `0`
- proof supervision active: `0`
- Scheduler jobs active: `0`

## Failed-run evidence preservation

Durable row preservation:

- requests `1969–1978`: all 10 present
- responses `1749–1756`: all 8 present
- failures `220–221`: both present

Consumed application evidence remained byte-identical:

- `application-marker.json`: `0895e91e4e554ea9207898ddfd4bcfe469334bf708554c82643fe61426dcd4d5`
- `git-provenance-manifest.json`: `94e927b697c2e9bd3a0c5a16ed50c991bb0e1acbe2569fa078e9304f93b2f359`
- `wrapper-terminal.json`: `57cc561d7d339481ec39652fe4cac79d5a81dda28144a69df85f942c9114ae0b`
- `child-stderr.txt`: `72f7ecd42048307ce903b0f81822bfefb3be9d193f4bb7136ec9524f336dfb62`
- `child-stdout.txt`: `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`

Consumed authorization package remained byte-identical:

- `final_authorization.json`: `a4e0acb604556b9ccb813ce0aa9597813d866f38089cce40e584a309bd84b969`

The authorization remains permanently non-reusable with disposition `CONSUMED_CHILD_EXITED_NONZERO`.

## Local Git note

The operator's local checkout remained on the prior authorization branch at `7defc2945c42053d9c770ebc66248d27c63ff4a3`, and the local repository had not yet fetched the new repair branch, so `git rev-parse origin/agent/v2-9-8b-window-15m-pre-holder-transport-identity-repair` failed locally. This is a missing local remote-tracking ref only. It does not alter the verified remote implementation commit or invalidate the database/evidence checks.

The listed untracked `operator-runs` directories are expected preserved authorization/evidence directories. They were not modified by this closeout.

## Money-usefulness contribution

Exact source-operation identity parity prevents holder admission and later memory formation from relying on unattached, duplicated, or count-only source-cost claims. It makes the original `9` versus `5` defect reproducible and diagnosable without another live run.

## What improves

- exact identity-bearing source manifests;
- one canonical transport identity shape;
- exact `M = C = A` pre-holder parity;
- request/stage-local bounded diagnostics;
- permanent operational fail-closed behavior on missing, malformed, duplicate, or mismatched identity evidence;
- preserved request-ID reconciliation and source accounting boundaries.

## What remains locked

This PASS does not unlock:

- a new authorization or campaign run;
- provider execution;
- holder collection;
- Scheduler or lifecycle runtime;
- `WINDOW_15M` proof by itself;
- `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, or `WINDOW_24H`;
- retrieval or dirty-memory use;
- paper decisions or BUY/SELL/HOLD;
- positions, trades, audits, or PnL;
- wallets, private keys, signing, real funds, or live execution;
- paid APIs;
- scoring, ranking, confidence, weighting, embeddings, or vectors.

## Functionality Risks / Setbacks / Efficiency Blockers

- A full end-to-end deterministic blocker-readiness and terminal-propagation audit remains required before another authorization is considered.
- Historical unscoped fixtures remain compatibility-only and cannot prove permanent operational readiness.
- Live provider availability, candidate sufficiency, holder evidence quality, and market freshness remain runtime conditions that disposable proof cannot guarantee.
- The wrapper still needs a later approved hardening lane so the first structured child terminal cause appears directly in wrapper output rather than requiring `child-stderr.txt` inspection.

## Exact next step

Do not create another authorization yet.

Proceed to the comprehensive `WINDOW_15M` end-to-end blocker-readiness and structured child-terminal-propagation audit, followed by design, implementation if approved, focused disposable proof, and closeout. Only after that lane passes should one fresh authorization be considered.
