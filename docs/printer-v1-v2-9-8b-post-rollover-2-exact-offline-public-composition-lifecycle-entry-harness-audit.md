# Printer V1 V2-9.8B Post-Rollover-2 Exact Offline Public Composition Lifecycle-Entry Harness Audit

Date: 2026-08-03

Baseline: `9f2163bbeb7f6a79d66de655a5bcedd077cb1422` — `Record frozen secondary exact proof blocker`

Branch: `agent/v2-9-8b-post-rollover-2-exact-public-composition-scheduler-claim-coverage-audit`

## Verdict

`V2_9_8B_POST_ROLLOVER_2_EXACT_OFFLINE_PUBLIC_COMPOSITION_LIFECYCLE_ENTRY_HARNESS_AUDIT_PASS`

Primary classification:

```text
TEST_ONLY_DEPENDENCY_INJECTION_REQUIRED
```

The production public fifteen-minute operational path correctly refuses a
disposable Migration-050 database under `operational_persistent_mode`. The
exact offline composition harness must remap only the lifecycle-factory entry
flags through the existing `OriginToLifecycleCampaignDriver(lifecycle_runner=…)`
dependency-injection seam so the real factory runs in disposable `proof_mode`.
No production preflight, corpus identity, Scheduler, Source Governor, six-unit
accounting, schema, or migration change is justified.

## Established facts (not reopened)

| Fact | Status |
| --- | --- |
| Frozen secondary repair passed | yes |
| Discovery succeeded (10 jobs) | yes |
| Two-slot activation succeeded | yes |
| Exact preflight rejected disposable DB under operational-persistent mode | yes — correct |
| Exact harness used disposable Migration-050 DB | yes |
| Classification of prior exact failure | `TEST_OR_PROOF_HARNESS_DEFECT` |
| Production preflight repair | **not** justified |
| Prior exact execution | consumed; must not be rerun |

Immutable first cause of the consumed exact composition:

```text
SAFE_STOP_PREFLIGHT_FAILED
operational persistent mode requires the authoritative corpus
```

## Lifecycle-entry call chain (source-grounded)

```text
public_command._run_operational_campaign
  → AuthoritativeLiveOperationalCampaignOwner.run_operational
       (fifteen_minute_only=True hardcoded by public coordinator)
  → OriginToLifecycleCampaignDriver.run
       proof_mode = not fifteen_minute_only          → False
       operational_persistent_mode = fifteen_minute_only → True
       continuous_* / four_hour_proof_mode = False
  → lifecycle_runner (default: run_one_command_15m_factory)
       + lifecycle_kwargs.operational_natural_disposition = True (forced by owner)
```

Factory preflight owners
(`src/printer_v1/operator_cli/one_command_15m_factory.py`):

| Condition | Result on disposable DB |
| --- | --- |
| `operational_persistent_mode=True` and path ≠ `CANONICAL_PERSISTENT_DB` | `SAFE_STOP_PREFLIGHT_FAILED`: authoritative corpus required |
| `proof_mode=True` and `operational_persistent_mode=True` | mutually exclusive |
| `operational_natural_disposition=True` and not continuous and not operational_persistent | `operational natural 15m-only mode requires operational persistent mode` |
| `proof_mode=True`, disposable path, not operational_persistent, not operational_natural | lawful `PROOF_ONLY` entry (existing e8 path) |

Public coordinator always sets `fifteen_minute_only=True`. The authoritative
owner always forces `operational_natural_disposition=True` into lifecycle kwargs
and rejects that key if the caller supplies it. Therefore the public 15m path
cannot lawfully enter disposable proof mode without a post-owner remapping of
lifecycle-entry flags.

## Seam evaluation

| # | Candidate | Decision |
| ---: | --- | --- |
| 1 | Existing lifecycle `proof_mode=True` entry | **Insufficient alone.** Reachable from the origin driver defaults and e8 tests, but unreachable from the public coordinator’s hard-coded `fifteen_minute_only=True` mapping. |
| 2 | Test-only lifecycle-runner injection | **Selected.** `OriginToLifecycleCampaignDriver` already accepts `lifecycle_runner`; the owner already accepts `driver=`. A harness runner can force `proof_mode=True` / `operational_persistent_mode=False` and clear operational-natural 15m coupling while still calling the real factory. |
| 3 | Proof-only configuration through the authoritative owner | **Insufficient without DI.** Owner rejects caller-supplied `operational_natural_disposition` and forces it True; it maps modes strictly from `fifteen_minute_only`. |
| 4 | Explicit offline-composition mode already present | **Not found.** No public offline composition mode parameter exists that lawfully enters disposable proof mode through the public 15m chain. |
| 5 | Patching `CANONICAL_PERSISTENT_DB` / corpus identity | **Rejected.** Impersonates the authoritative corpus; forbidden by lane law and prior root-cause guidance. |
| 6 | Copying or impersonating the authoritative corpus | **Rejected.** Offline composition must never open or mutate the live authoritative database. |

### Rejected unsafe approaches (confirmed)

- Patch `CANONICAL_PERSISTENT_DB` to the temp DB
- Treat a disposable DB as authoritative
- Disable or weaken the corpus preflight
- Invoke the lifecycle factory outside the public owner chain
- Bypass Scheduler or Source Governor
- Write to the real authoritative database

## Smallest valid boundary

```text
TEST_ONLY_DEPENDENCY_INJECTION_REQUIRED
```

Rationale:

1. Production preflight and public operational defaults are correct and must stay.
2. Existing proof-mode factory entry is already sufficient for disposable DBs when
   called with lawful kwargs (e8, focused factory suites).
3. The only missing piece is a harness-owned remapping **after** the real public
   coordinator and authoritative owner have performed discovery/activation, and
   **before** the real factory preflight.
4. That remapping fits the existing DI ports: owner `driver=` and driver
   `lifecycle_runner=`.
5. No production code change is required.

Secondary labels considered and not selected:

| Label | Why not selected |
| --- | --- |
| `EXISTING_PROOF_MODE_SEAM_SUFFICIENT` | Public path never reaches it without remapping |
| `TEST_HARNESS_ARGUMENT_REPAIR` | Public/owner APIs do not accept the required mode flags as ordinary arguments |
| `BOUNDED_PROOF_ONLY_PRODUCTION_SEAM_REQUIRED` | Existing DI ports already suffice |
| `NO_LAWFUL_OFFLINE_ENTRY_AVAILABLE` | Lawful disposable proof entry already exists |
| `INSUFFICIENT_EVIDENCE` | Owners, preflight, and prior exact evidence are sufficient |

## Exact lifecycle-entry contract (audit target)

The offline exact harness must preserve:

```text
public coordinator
  → authoritative campaign owner
  → real discovery and two-slot activation
  → origin-to-lifecycle driver
  → lifecycle factory (proof_mode=True, operational_persistent_mode=False)
  → two compressed WINDOW_15M closes
  → strict accounting
  → campaign acceptance
```

while using:

- disposable Migration-050 database;
- frozen transports;
- compressed timing only through existing proof-only parameters;
- no live or authoritative corpus;
- no weakened preflight.

### fifteen_minute_only semantics — proof equivalent

Public `fifteen_minute_only=True` means:

- no continuous first-hour / four-hour path;
- exactly two selected tokens;
- two `WINDOW_15M` terminal closes;
- no 1h/4h continuation unlock.

The lawful disposable proof equivalent is **not** `operational_persistent_mode=True`.
It is:

```text
proof_mode=True
operational_persistent_mode=False
continuous_first_hour=False
continuous_four_hour=False
four_hour_proof_mode=False
operational_natural_disposition=False   # required: natural 15m-only couples to operational-persistent
```

Clearing `operational_natural_disposition` is mandatory under current preflight:
operational-natural 15m-only requires operational-persistent mode, which requires
the authoritative corpus. Dropping natural disposition for offline disposable
entry is the smallest lawful proof equivalent of “two compressed WINDOW_15M
closes only.” It does not alter production public defaults.

### Production defaults that must remain

Ordinary public operational use (unchanged):

```text
proof_mode=False
operational_persistent_mode=True
authoritative corpus required
fifteen_minute_only=True
operational_natural_disposition=True
```

The harness remapper must never be reachable from ordinary public CLI paths.
It lives only in the exact offline composition test harness.

## What improves

- Offline exact composition can lawfully enter the real lifecycle factory on a
  disposable Migration-050 DB without impersonating the authoritative corpus.
- Prior `SAFE_STOP_PREFLIGHT_FAILED` harness defect is isolated and correctable
  as a test-only DI remap.
- Production corpus preflight remains the hard stop for non-proof operational use.

## What remains locked

- Production preflight rules and `CANONICAL_PERSISTENT_DB`
- Scheduler ownership/claim law and six-unit accounting
- Source Governor
- Schema and migrations
- Discovery/secondary contracts (already repaired; not reopened)
- Authorization, retry/restart/resume/successor
- Retrieval, decisions, BUY/SELL/HOLD, positions, trades, audits, PnL
- Live providers, wallets, signing, funds, paid APIs
- Scoring, ranking, confidence, weights, embeddings, vectors
- Exact public-composition node execution (requires separate authorization)

## Money-usefulness contribution

A lawful offline lifecycle-entry harness lets Printer prove that discovery →
activation → two owned `WINDOW_15M` closes → strict accounting → campaign
acceptance can complete without ever touching the live corpus. That protects
money-useful memory growth proofs from false operational-persistent stops while
keeping the real safety boundary that production may only write the
authoritative corpus under operational-persistent mode.

## Proof performed (this audit phase)

Source-grounded inspection of:

- exact public-composition harness;
- public coordinator (`operational_memory_factory_command._run_operational_campaign`);
- authoritative operational campaign owner;
- `OriginToLifecycleCampaignDriver`;
- `run_one_command_15m_factory` preflight;
- prior frozen-secondary exact-proof root-cause report;
- e8/e11/factory focused suites demonstrating disposable `proof_mode`.

Runtime matrix confirmation (local disposable DB, not the exact node):

| Entry | Result |
| --- | --- |
| operational_persistent + disposable | `SAFE_STOP_PREFLIGHT_FAILED` / authoritative corpus |
| proof_mode + operational_natural 15m-only | `SAFE_STOP_PREFLIGHT_FAILED` / natural requires operational-persistent |
| proof_mode only (no natural) | preflight passes; empty pool safe-stops after entry |

## Functionality Risks / Setbacks / Efficiency Blockers

| Item | Disposition |
| --- | --- |
| Harness must remap after owner forces operational-natural | Accepted; DI lifecycle_runner is the designed port |
| Dropping operational-natural for offline proof | Documented as the smallest lawful 15m-only proof equivalent |
| Exact composition still unauthorized | Correct; focused proof only in this lane |
| Patching `AUTHORITATIVE_DB` alone is insufficient | Confirmed; factory uses unpatched `CANONICAL_PERSISTENT_DB` |
| Application-level network patch | Not packet capture; retained as existing zero-network boundary |

## Next phase

Design the exact offline lifecycle-entry harness around
`TEST_ONLY_DEPENDENCY_INJECTION_REQUIRED`, then implement and focused-prove it
without running the exact public-composition node.
