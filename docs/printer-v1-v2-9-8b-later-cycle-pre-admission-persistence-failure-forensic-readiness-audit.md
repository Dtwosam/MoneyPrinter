# Printer V1 V2-9.8B Later-Cycle Pre-Admission Persistence Failure Forensic / Readiness Audit

Date: 2026-08-24

Work class: read-only forensic/readiness audit

Starting HEAD: `8c3dddbe91f447204ddad2704e97dc11482b304c`

Consumed authorization: `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260824T123555Z_95dc47dd`

Consumed execution: `20260824T144455Z-7296588d4c98`

Required incident DB SHA-256: `9962fc4fe9e47c785e0732450102d0b2f5cd62fff6081b8517102b04a2a9efc5`

## Verdict

`V2_9_8B_LATER_CYCLE_PRE_ADMISSION_PERSISTENCE_FAILURE_FORENSIC_READINESS_AUDIT_PASS_NEXT_ACTION_IDENTIFIED`

Primary classification:

`E. DIAGNOSTIC_GAP_BLOCKS_ROOT_CAUSE_IDENTIFICATION`

Python Builder Guide blocker classification:

`DESIGN_GAP`

The campaign failed closed truthfully. Surviving evidence proves successful
attempt/Scheduler ownership, candidate supply, all 13 returned source-evidence
links, and two neutral token/pair identity writes. It also proves that no
pre-admission item, `PAIR_READY` transition, Cycle 2, Cycle-2 tracking authority,
or Cycle-2 materialization survived.

It does not prove the narrower `PreAdmissionAttemptError`. The production catch
maps materially different producers to
`LATER_CYCLE_ATTEMPT_PERSISTENCE_FAILED`, persists only that generic value, and
discards `str(exc)` and its chain. The exact application artifacts contain only
the later independent terminal-accounting `TypeError`. A specific code,
atomicity, or SQLite/environment defect cannot be selected honestly.

Another authorization is not ready. The exact next permitted action is:

`BOUNDED PERSISTENCE FAILURE DIAGNOSTIC DESIGN ONLY`

## Authority and scope

The audit used the current repository and durable evidence over historical
chat. It inspected `AGENTS.md`, the active Printer source stack,
`CURRENT_HANDOFF.md`, the consumed authorization/readiness/application evidence,
the terminal-accounting repair design/implementation/closeout, the Python
Builder Guide, and the actual production owners named below.

The terminal-accounting repair is a separate closed defect. Its `TypeError`
occurred after the pre-admission attempt was durably failed and does not identify
the initiating `PreAdmissionAttemptError`.

Allowed: static source/test inspection, read-only DB/artifact inspection, and
this documentation. Forbidden and not performed: production code, test,
migration, schema, configuration, DB, operator-evidence, provider, Scheduler,
campaign, authorization, retry, recovery, or successor mutation.

## Baseline and quiescence

| Check | Result |
|---|---|
| Starting HEAD | exact required `8c3dddbe91f447204ddad2704e97dc11482b304c` |
| Branch | `agent/v2-9-8b-consumed-4-2-2-full-operational-run-forensic-audit` |
| Consumed launch HEAD | manifest-pinned `a5c523b22ffba2b6943d81e66f9c6c99aa44332e` |
| Tracked worktree/index before docs | clean |
| Relevant untracked state | preserved operator evidence only; no untracked source was authority |
| Incident DB SHA before audit | exact required SHA |
| Incident DB SHA after audit | exact unchanged `9962fc4fe9e47c785e0732450102d0b2f5cd62fff6081b8517102b04a2a9efc5` |
| `PRAGMA integrity_check` | `ok` |
| `PRAGMA foreign_key_check` | zero rows |
| SQLite sidecars | none |
| Open DB handles | none |
| Printer/MoneyPrinter processes | none |
| Active Scheduler/campaign/factory/supervision work | zero |

Pre-existing untracked evidence directories were the four-token final
authorization directory, migration application evidence for 055/056/057/058/
059/061, pair-ready residual reconciliation, pre-admission-2364 reconciliation,
and standard-four-hour final-authorization evidence. They were not changed.

The only tracked changes between the consumed launch HEAD and the required
starting HEAD are the later terminal-accounting repair/closeout and its focused
test/handoff. The pre-admission owner, later-cycle callback, supply owner,
Cycle-2 coordinator, and materialization owner are byte-identical across those
two commits. The producer map below therefore describes the consumed
persistence boundary, not a post-incident reconstruction.

## Production error taxonomy and producer map

`PreAdmissionAttemptError` is defined at
`src/printer_v1/operator_cli/pre_admission_discovery_attempt.py:24-25`. No
production module outside that file constructs it. Other production modules
only catch or propagate it.

| Producer | Operation / exceptions | Detail and transaction behavior | Incident disposition |
|---|---|---|---|
| `_required`, `:109-112` | string validation | dynamic `*_INVALID`; no write | viable inside later item path; exact call absent |
| `_utc`, `:115-118`; `_parse_timestamp`, `:125-130` | time validation; parse catches `TypeError`/`ValueError` | categorical code; lower detail chained only; no write | viable helper family, not identified |
| `_decode_evidence_candidate`, `:137-143`; projection `:186-213` | JSON/evidence projection; catches `TypeError`/`JSONDecodeError` | `FROZEN_LANE_EVIDENCE_INVALID`; no write | viable after proven links |
| lane classification, `:237-260` | existing categorical discovery classifier | `FROZEN_TRACKING_LANE_UNAVAILABLE`; no write | viable; exact frozen carrier absent |
| frozen-field validation, `:293-320` | completeness, equality, allowlist, hash, owner | caller/helper code; no write; before pair savepoint | viable; exact item absent |
| attempt load, `:348-359` | durable lookup | `ATTEMPT_NOT_FOUND`; read only | ruled out at catch time; exact attempt was terminalized |
| attempt create, `:362-440` | owner/Scheduler checks and insert; catches `sqlite3.IntegrityError` | duplicate distinguished; other integrity failures become `ATTEMPT_PERSISTENCE_FAILED`; lower SQLite detail only chained | ruled out; exact attempt exists |
| `_transition`, `:443-469` | compare-and-set state update | `INVALID_ATTEMPT_TRANSITION`; caller transaction | viable only for pair readiness; FAILED transition succeeded |
| mark RUNNING, `:472-494` | exact claimed-job ownership | `SCHEDULER_CLAIM_MISMATCH`; caller transaction | ruled out; later source work and terminal RUNNING transition prove claim |
| scheduled create, `:501-575` | open-tx/uniqueness/ownership; Scheduler enqueue and attempt create | explicit `BEGIN IMMEDIATE`; commit on success; full rollback on exception | ruled out; attempt/job survive |
| terminalize, `:578-618` | terminal enum and state transition | terminal/state codes; caller transaction | its FAILED write succeeded; not initiating error |
| `_validate_pair`, `:622-643` | exact-two/ordinal/owner/distinct identity/channel checks | exact categorical code; no write; before savepoint | viable; attempted carrier absent |
| pair persist before savepoint, `:646-660` | pair/frozen-field/RUNNING validation | exact `PreAdmissionAttemptError` re-raised | viable |
| pair persist savepoint, `:662-716` | two item inserts plus RUNNING→PAIR_READY; catches `sqlite3.Error` and typed errors | rollback-to/release on error; typed code re-raised; every SQLite error becomes `PAIR_PERSISTENCE_FAILED`, lower detail chained only | viable; zero rows fits any pre-savepoint or rolled-back failure |
| pair load, `:719-736` | requires PAIR_READY/CONSUMED and exact two items | `PAIR_NOT_READY` / `EXACT_TWO_ITEMS_REQUIRED`; read only | not reached by Cycle-2 admission |
| pair-ready parent cancellation, `:835`, `:841`, `:871` | ownership/cancellation | exact categorical codes; caller transaction | not reached; never PAIR_READY |
| source-evidence link, `:875-905` | argument validation and immutable link insert; catches `sqlite3.IntegrityError` | exact argument codes or `SOURCE_EVIDENCE_LINK_INVALID`; lower integrity detail chained only | ruled out for the returned 13-row lineage; ordinals 1–13 all survive |

The sole production producer of
`LATER_CYCLE_ATTEMPT_PERSISTENCE_FAILED` is
`src/printer_v1/operator_cli/authoritative_live_operational_campaign.py:2460-2495`.
It catches every `PreAdmissionAttemptError`, reloads the attempt, writes attempt
`FAILED`, fails its Scheduler job with the same generic value and
`max_retries=0`, commits, and returns the terminal result. It does not persist
the exception text, producer, bounded subcode, SQLite class/code, or chain.

Consumers are the later-cycle callback result, the one-command factory's
Cycle-1/campaign stop path, the four-token terminal adapter, and shared campaign
terminalization. None restores the discarded subcause.

## Exact consumed-run production path

1. Cycle 1 was admitted and ran its bounded lifecycle.
2. The later-cycle callback atomically created the proposed-Cycle-2 attempt and
   Scheduler job, claimed the job, and moved the attempt to `RUNNING`.
3. It committed and closed that connection before supply
   (`authoritative_live_operational_campaign.py:2113-2115`).
4. The governed supply owner performed bounded source work and committed two
   neutral token/pair identities in `short_write_transaction`
   (`later_cycle_graduated_supply.py:409-418`).
5. Phase C reopened the operational DB and revalidated the exact RUNNING
   attempt and claimed Scheduler job (`:2192-2218`).
6. It linked every returned source-evidence row (`:2317-2327`).
7. It applied the existing discovery gate/selection, constructed two items,
   attached frozen lanes, and called pair persistence (`:2334-2404`).
8. A `PreAdmissionAttemptError` escaped after the completed link loop and
   before successful pair readiness.
9. The generic catch committed failed attempt and job truth (`:2460-2493`).
10. The factory terminalized Cycle 1 and safe-stopped on that cause.
11. The older shared-terminal bridge then raised the independently repaired
    `TypeError`; it did not rewrite the durable pre-admission cause.

Last durable successful state before the failure boundary:

- attempt RUNNING under claimed Scheduler job 2541;
- two supply-owned neutral token/pair identities;
- 13 immutable source-evidence links.

First durable terminal state after it:

- attempt `FAILED` on `LATER_CYCLE_ATTEMPT_PERSISTENCE_FAILED` at
  `2026-08-24T14:57:26.595970+00:00`;
- Scheduler job 2541 `FAILED` on the same generic value, unlocked, with no
  retry path at that timestamp.

## Authoritative DB forensics

| Identity | Value |
|---|---|
| campaign | `20260824T144455Z-7296588d4c98-campaign` |
| campaign run | `20260824T144455Z-7296588d4c98-campaign-run` |
| Cycle 1 | `20260824T144455Z-7296588d4c98-cycle` |
| proposed Cycle 2 | `20260824T144455Z-7296588d4c98-cycle-2` |
| supervision | `20260824T144455Z-7296588d4c98-supervision` |
| factory run | `144c70a0-d7bb-471d-a1a1-e72154386975` |
| attempt | `pre-admission:20260824T144455Z-7296588d4c98-campaign:20260824T144455Z-7296588d4c98-campaign-run:144c70a0-d7bb-471d-a1a1-e72154386975:c0002` |

Durable findings:

- one exact attempt: `FAILED`, generic cause, `consumed_cycle_id=NULL`;
- 13 source links, contiguous ordinals 1–13;
- eleven response-linked rows and two explicit GeckoTerminal rate-limit
  failures, together covering the exact DexScreener, GeckoTerminal, PumpSwap,
  migration, safety, mint, and holder lineage;
- two neutral identities: token rows 81/82 and pair rows 85/86 for the two
  selected mint/pair identities;
- zero pre-admission item rows;
- zero Cycle-2 campaign-cycle, slot, tracking-queue, discovery-materialization,
  or selection-materialization rows;
- Cycle 1 `TERMINAL_BLOCKED` on the generic persistence cause;
- factory run `SAFE_STOPPED` on that cause, with no final report JSON;
- supervision `TERMINAL/FAILED` on the later independent `TypeError`, cleanup
  complete and lease released;
- zero active owned work.

The absence of pair items proves that exact-two item persistence plus
PAIR_READY did not commit. Production semantics do not distinguish validation
before the savepoint from a rolled-back item/trigger/FK/constraint/SQLite or
PAIR_READY-transition failure inside it.

Normalized provider payloads preserve market rows for both selected mints, but
not the exact post-supply candidate carrier, canonical evidence JSON, frozen
classifier input, selected order, or attempted item values. Reconstructing
those objects would be inference and cannot prove which producer fired.

## Stderr and application evidence

Application artifact root:

`/Users/Dtwo1/PrinterOperations/v2-9-8/four-token-standard-four-hour-one-shot-applications/V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260824T123555Z_95dc47dd`

Run artifact root:

`/Users/Dtwo1/PrinterOperations/v2-9-8/20260824T144455Z-7296588d4c98`

| Artifact | SHA-256 |
|---|---|
| application marker | `1ecb94577b08a1ab7cb5546a2f09a65f81373a9b819a9b1d21756f80632993f4` |
| child stderr | `4252cbea772e9511bf4cd6961c5261c08b1ed744c3a7874cc06f6fe01bf4f857` |
| child stdout | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| child terminal | `10578af435a0e38c6a480387336be6e4c68457f8f8c94bceeb9ffbccd6c15484` |
| Git manifest | `5311b0bb73376ed6033b62e7319a283c9f960c8ce4bd2fd3299e902a8cb15237` |
| wrapper terminal | `24f6c59445893e952669561c965b5a3ac626994bf9e3ad5346598ebc5eb58a76` |
| run terminal summary | `91526e2650d54fdc82a4c73713e89d23d3371212764bb66245c54ed17dcc4263` |

Child stdout is empty. Child stderr is a terminal JSON envelope, not an
incremental log. Recursive searches across stderr, child/wrapper terminals,
manifest, marker, and run summary found no `PreAdmissionAttemptError`, pair or
source-link subcode, frozen-lane error, SQLite error, traceback, or preceding
message from the initiating failure.

The only surviving exception detail is the later:

`TypeError: run_one_command_15m_factory.<locals>._shared_terminal_from_accounting() missing 1 required keyword-only argument: 'terminal_accounting'`

The initiating detail does not exist outside the DB in the inspected evidence.

## Transaction and atomicity result

| Boundary | Behavior | Result |
|---|---|---|
| attempt + Scheduler creation | one `BEGIN IMMEDIATE`; commit together or full rollback | atomic and already durable |
| governed supply identity creation | separate short write transaction before carrier return | two neutral identities survive; no tracking/admission authority |
| source linking | Phase-C outer transaction, before pair savepoint | links may survive a later pair failure with terminal truth |
| pair freeze | validation, then savepoint covering both item inserts and RUNNING→PAIR_READY | rollback leaves no partial item set/PAIR_READY |
| Cycle-2 admission | separate `BEGIN IMMEDIATE`; tracking claim, Cycle 2/slots, and attempt consumption; full rollback (`multi_cycle_campaign_coordinator.py:742-872`) | never reached; no partial Cycle 2 |
| Cycle-2 materialization | requires consumed attempt and Cycle 2 (`pre_admission_materialization.py:227+`) | never reached |
| failure terminalization | failed attempt + failed Scheduler job + commit; `max_retries=0` | truthful terminal state; retry forbidden |

No design-required atomicity defect is proven. Pair-item/PAIR_READY atomicity
held and no partial Cycle 2 survived. The separate durability of source links
and neutral identities is not a partially admitted pair/cycle.

The design gap is diagnostic: several failures can roll back to the same zero
item state, while only one shared generic classification commits.

## Candidate disposition

`SUPPORTED` means viable as a family, not proven as root cause.

| Candidate | Status | Evidence |
|---|---|---|
| attempt/Scheduler create or claim | `RULED_OUT` | exact attempt/job reached RUNNING and later links |
| source scarcity/rate limit as direct initiating exception | `RULED_OUT` | failures 350/351 were normalized and linked; two candidate identities and all lineage links followed |
| source-evidence-link failure for returned lineage | `RULED_OUT` | all 13 returned source calls have contiguous durable links |
| frozen-evidence/lane/item validation | `SUPPORTED` | executes after last proven link; exact carrier/code discarded |
| duplicate identity/malformed attempted value | `UNRESOLVED` | durable neutral identities are distinct; attempted item fields absent |
| SQLite UNIQUE/CHECK/FK/trigger failure | `UNRESOLVED` | all become generic pair persistence and rollback |
| SQLite busy/locked/transaction-state failure | `UNRESOLVED` | no historical SQLite code/message; current quiescence is not historical proof |
| disk/full/fsync/I/O SQLite failure | `UNRESOLVED` | no support, but generic catch prevents retrospective exclusion; later commit only argues against persistent outage |
| pair-state compare-and-set failure | `UNRESOLVED` | transition shares savepoint; only failed terminal state survives |
| Cycle-2 admission/materialization | `RULED_OUT` | never PAIR_READY/CONSUMED; zero Cycle-2 row |
| later accounting `TypeError` as initiating cause | `RULED_OUT` | occurred after generic attempt/job terminal commit |

SQLite/environment failure is not proven. Current integrity, FK, sidecar,
process, and lease checks pass but cannot classify the discarded incident-time
exception.

No source/provider failure is proven as the initiating persistence cause. The
GeckoTerminal rate limits are real scarcity facts, but production continued
past them to candidate identity creation and complete lineage linking. They
must not be promoted into the persistence cause without the missing exact
lower-level evidence.

## Reproducibility

- `tests/test_v2_9_8b_pre_admission_discovery_attempt_persistence.py:189-218`
  proves pair shape and successful exact-two atomicity, but does not inject an
  incident-time SQLite or exact carrier condition.
- `tests/test_v2_9_8b_pre_admission_discovery_attempt_persistence.py:221+`
  proves source lineage constraints, not this failed boundary.
- `tests/test_v2_9_8b_cadence_authority_corrective_repair.py:185-189` proves
  weak evidence raises `FROZEN_TRACKING_LANE_UNAVAILABLE`, not that the
  consumed carrier was weak.
- `tests/test_v2_9_8b_shared_terminal_pre_lifecycle_factory_integration.py:133-270`
  monkeypatches `link_pre_admission_source_evidence` to raise
  `PreAdmissionAttemptError("SOURCE_EVIDENCE_LINK_INVALID")` directly. It
  proves terminal handling, not the real lower-level condition.
- Cycle-2 consumption/materialization tests exercise boundaries never reached.

No existing test reproduces the same underlying production condition. Because
that condition was not retained, a truthful same-condition test cannot yet be
selected.

## Diagnostic adequacy

Production adequately preserves fail-closed generic terminal truth, exact
ownership, no retry/recovery/successor, and proof that pair readiness/Cycle 2 did
not occur. It inadequately diagnoses future occurrences because pure
validation, evidence projection, lane unavailability, pair shape/state, and
multiple SQLite failure families collapse into one durable value.

Any future diagnostic proposal must preserve the first cause using an
allowlisted, bounded, deterministic, non-sensitive representation. It must not
store source payloads, provider bodies, secrets, filesystem detail, or unbounded
SQLite messages; weaken terminal behavior; or enable retry/recovery. This audit
does not design or implement that proposal.

## Classification and next-lane decision

Primary result:

`E. DIAGNOSTIC_GAP_BLOCKS_ROOT_CAUSE_IDENTIFICATION`

- Not A: no specific code defect is proven.
- Not B: pair and Cycle-2 atomicity matched committed boundaries.
- Not C: no incident-time SQLite/environment error survives.
- Not D: the failure is honest and fail closed, but the decisive actionable
  fact is that production discarded the discriminator across distinct producer
  families.
- Not F: no second underlying persistence defect is independently proven; the
  later accounting defect is separately closed.

A repair is required before another authorization, but no repair design or
implementation is authorized here. The required sequence begins with:

`BOUNDED PERSISTENCE FAILURE DIAGNOSTIC DESIGN ONLY`

Passing current tests, current DB health, or the closed terminal-accounting
repair is not authorization evidence.

## Consumed authority and permanent locks

The consumed authorization remains permanently dead. No retry, rerun, resume,
restart, recovery, successor, or replacement authorization was created.

Permanent locks PASS unchanged: Solana-only; memecoin-only; paper-only; no
wallets/keys/signing/funds/live execution; no paid APIs; no scoring/ranking/
confidence/weighted logic; no embeddings/vectors; Source Governor and Central
Scheduler mandatory; dirty memory excluded; 5m support-only; Cycle 3 locked;
12h/24h locked; retrieval locked; BUY/SELL/HOLD locked; positions/trades/audits/
PnL locked; V2-10 blocked.

## Verification and closeout

Minimum sufficient checks: static producer/consumer map, exact DB rows,
source-request lineage, exact application artifacts and hashes, transaction
trace, focused-test inventory, repository state, DB hash/integrity/FK/sidecars,
process/lease/Scheduler/supervision quiescence, and documentation diff checks.

No pytest, live provider, Scheduler runtime, campaign, DB repair, or
authorization command was run.

### Functionality Risks / Setbacks / Efficiency Blockers

- The initiating subcause is irrecoverable from the consumed evidence.
- Zero items cannot distinguish pre-savepoint validation from rolled-back DB or
  pair-transition failure.
- Normalized source payloads are not the exact ephemeral item carrier.
- Existing tests prove terminal behavior, not the unknown real condition.
- A fresh authorization would knowingly accept the same root-cause blindness.

### Required task closeout

- **Files changed:** this audit and minimal `CURRENT_HANDOFF.md` update only.
- **What was built:** forensic producer/path/DB/artifact/transaction/test map,
  supported classification, and next-lane decision.
- **What was not touched:** production/tests/migrations/schema/config/DB/
  operator evidence/providers/Scheduler/campaign/authorization/locked features.
- **Tests/checks run:** static and read-only checks above; no broad pytest.
- **Pass/fail:**
  `V2_9_8B_LATER_CYCLE_PRE_ADMISSION_PERSISTENCE_FAILURE_FORENSIC_READINESS_AUDIT_PASS_NEXT_ACTION_IDENTIFIED`.
- **Risks or concerns:** exact cause is not recoverable; another authorization
  is not ready.
- **Next recommended phase:**
  `BOUNDED PERSISTENCE FAILURE DIAGNOSTIC DESIGN ONLY`.
