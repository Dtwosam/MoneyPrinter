# Printer V1 V2-9.8B Post-Rollover-2 Exact Offline Public Composition Lifecycle-Entry Harness Focused Proof

Date: 2026-08-03

Baseline: `9f2163bbeb7f6a79d66de655a5bcedd077cb1422`

## Verdict

`V2_9_8B_POST_ROLLOVER_2_EXACT_OFFLINE_PUBLIC_COMPOSITION_LIFECYCLE_ENTRY_HARNESS_FOCUSED_PROOF_PASS`

## Final focused command and result

```bash
PYTHONPATH=src:tests .venv/bin/python -m pytest -q \
  tests/test_v2_9_8b_exact_offline_public_composition_lifecycle_entry_harness.py
```

Result:

```text
9 passed in 8.00s
```

Exact node **not** run:

```text
tests/test_v2_9_8b_token_slot_id_exact_public_composition.py::
ExactPublicTokenSlotIdCompositionProof::
test_exact_public_coordinator_owner_driver_factory_composition
```

No broad/full pytest.

## Required coverage

| # | Requirement | Result |
| ---: | --- | --- |
| 1 | Ordinary public 15m operational mode still requires authoritative corpus | PASS |
| 2 | Disposable DB + operational-persistent mode still safe-stops | PASS; zero factory runs |
| 3 | Approved offline composition path enters lifecycle in proof mode | PASS; remapper + `PROOF_ONLY` factory run |
| 4 | Public coordinator and authoritative owner are not bypassed | PASS; `_run_operational_campaign` + owner `run_operational` observed |
| 5 | Origin driver receives the same two activated slots | PASS; two durable slot IDs match discovery stage callback |
| 6 | Lifecycle factory uses disposable DB lawfully | PASS; remapper path is temp DB; `db_mode=PROOF_ONLY` |
| 7 | Exactly two compressed `WINDOW_15M` lifecycles can complete | PASS; two succeeded `WINDOW_CLOSE`; zero continuation closes |
| 8 | Scheduler transitions are real | PASS; jobs present; zero active/locked residue |
| 9 | Strict accounting remains unchanged | PASS; handoff validations match slots; locked windows empty |
| 10 | Campaign acceptance can evaluate the completed proof | PASS; `campaign_pass=True` |
| 11 | No live provider/RPC/WebSocket calls | PASS; `urlopen` call count 0 |
| 12 | No authoritative DB opened or mutated | PASS; no `sqlite3.connect` to `CANONICAL_PERSISTENT_DB` |
| 13 | No retry, restart, resume or successor | PASS; `AUTOMATIC_RETRIES=0`; restart/successor false |
| 14 | Retrieval and financial surfaces remain zero | PASS; locked capability table counts all 0 |
| 15 | Previous `SAFE_STOP_PREFLIGHT_FAILED` remains negative coverage | PASS; exact corpus reason string |

Additional matrix coverage:

- `proof_mode=True` + `operational_natural_disposition=True` still safe-stops
  (`operational natural 15m-only mode requires operational persistent mode`).
- Remapper forces lawful flags even when inbound public flags are hostile.
- `CANONICAL_PERSISTENT_DB` identity remains the real repo corpus path.

## Static verification

- Python compilation of changed harness/proof modules performed.
- `git diff --check` performed.
- Exact changed-file review: no production preflight, corpus constant,
  Scheduler, Source Governor, six-unit accounting, schema, migration,
  discovery/secondary, authorization, or retry/restart changes.

## Money-usefulness contribution

Focused proof shows Printer can complete two owned compressed `WINDOW_15M`
closes through the real public chain on a disposable Migration-050 database
without ever opening the live corpus, while production operational-persistent
mode continues to refuse disposable targets. That is the honest boundary for
offline money-useful memory-factory proofs.

## What improves

- Lawful offline lifecycle entry is deterministic and tested.
- Prior harness defect is a permanent negative.
- Production defaults remain proven, not assumed.

## What remains locked

The exact public-composition node remains unexecuted and requires a new
explicit authorization. All capability locks listed in the implementation
document remain locked.

## Proof required (next authorization only)

Exactly one future execution of:

```text
test_exact_public_coordinator_owner_driver_factory_composition
```

is permitted only under a new explicit operator authorization. It must not be
retried, rerun, resumed, restarted, or succeeded by another run in this lane.

## Functionality Risks / Setbacks / Efficiency Blockers

| Item | Status |
| --- | --- |
| Focused composition reuses frozen exact transports | Deterministic; not a live proof |
| Application-level urllib patch | Not packet capture |
| Exact node still unrun | Intentional stop condition |
| Owner still emits public operational flags | Expected; remapper converts only at factory entry |
