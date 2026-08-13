# Printer V1 V2-9.8B Four-Token One-Use Authorization Wrapper Independent Review

Date: 2026-08-14

## Verdict

`V2_9_8B_FOUR_TOKEN_ONE_USE_AUTHORIZATION_WRAPPER_INDEPENDENT_REVIEW_BLOCKED_ZERO_STATE_SUPERVISION_AND_PROCESS_PROBE`

This is an independent static review only. It creates no authorization, starts no Printer process, performs no source/RPC call, mutates no authoritative database, applies no migration, and does not run the four-token proof.

## Baseline and reviewed implementation

- Design baseline: `0b1454667067c42bdf3244388c1bf04eec90a351`
- Implementation HEAD reviewed: `5defeb035e6693384c2fede5c128030668376c77`
- Compare status: implementation is 15 commits ahead, 0 behind; merge base is exactly the design baseline.
- GitHub commit statuses: none.
- GitHub workflow runs for the implementation HEAD: none.
- Local test results in the implementation closeout are useful implementation evidence, but were not independently rerun by this connector-backed review.

## Accepted seams

### PASS — dedicated proof-only authority

The four-token proof has a distinct authorization profile, schema, package root, manifest schema, wrapper schema, application namespace, and command mode. The standard two-token wrapper is not reused as four-token authority.

### PASS — exact 4/2/2 policy and timing

The authorization validator compares every proof-policy field using exact type/value equality against `exact_proof_policy()`, which derives capacity from `scaled_standard_four_hour_capacity_contract(4)`. The accepted shape remains 4 through-4h tokens, 2 active cycles, 2 total admissions, 2 tokens per cycle, >=300-second spacing, separate 900-second acquisition and 18,000-second proof clocks, no retries, no endpoint rotation, and locked 12h/24h.

### PASS — migration-055 evidence remains narrowly bound

`GitAuthorizationProfile` gained profile-specific migration package root/kind fields with migration-050 defaults for existing profiles. The four-token profile points only to the migration-055 application root/kind, and manifest validation uses the active profile's exact migration root. This does not grant generic trust to `operator-runs/`.

### PASS — one-use wrapper mechanics

The dedicated wrapper preserves the marker-before-child consumption law, outside-repository application namespace, immutable manifest/marker, one-child attempt, no retry/rerun/resume/restart/successor, and exact child-terminal identity handling.

### PASS — proof-only CLI composition

The new wrapper-bound CLI mode constructs `FourTokenProofController.exact()` and invokes the existing `_run_operational_campaign(...)` path once with the fixed four-token policy. No caller-selectable 6/3 capacity argument or second runner/event loop was found.

## BLOCKER 1 — zero-state supervision queries reject healthy historical terminal rows

`four_token_proof_zero_state_gate.py` currently defines:

```sql
SELECT COUNT(*) FROM printer_memory_factory_campaign_supervision
SELECT COUNT(*) FROM printer_proof_run_supervision
```

and requires both counts to be zero.

That is incompatible with Printer's durable supervision semantics. Migration 033 deliberately preserves campaign-supervision rows in `TERMINAL` state and defines active ownership as `ACTIVE` / `STOPPING`. Migration 030 similarly preserves proof-supervision rows in `TERMINAL` state and defines active proof ownership as `STARTING` / `RUNNING`.

Durable authoritative history already proves terminal supervision is expected in a healthy quiescent DB: the post-accounting-repair readiness audit recorded 18 terminal campaign-supervision rows with zero non-terminal rows and classified the DB as ready.

Therefore the current production zero-state gate would block a healthy authoritative DB solely because historical terminal evidence exists. Historical terminal rows must remain immutable evidence; they must not need deletion to authorize a new bounded proof.

Required repair:

- campaign supervision zero-state must count only `supervision_state IN ('ACTIVE','STOPPING')`;
- proof supervision zero-state must count only `execution_status IN ('STARTING','RUNNING')`;
- add focused regression fixtures containing terminal historical rows and prove they pass while active rows fail;
- do not delete or rewrite historical supervision rows.

The design wording `zero campaign/proof supervision` should be clarified as zero active/non-terminal supervision, consistent with the durable operational readiness model.

## BLOCKER 2 — production wrapper bypasses the Printer-process check

The reusable zero-state function correctly accepts a `printer_process_probe` and blocks when that probe reports a PID. Its focused unit test proves only that injected behavior.

However, the production wrapper's `_default_zero_state_gate(...)` defines:

```python
def _no_process_probe() -> tuple[int, ...]:
    return ()
```

and passes that hard-coded empty probe to `assert_four_token_proof_zero_state(...)`.

So the real default wrapper can never observe an already-running Printer process at this pre-consumption gate. It will report `printer_processes=0` regardless of host process reality, contrary to the approved design's explicit `no Printer process` requirement.

The wrapper tests do not cover this production default because they inject a fake passing `zero_state_gate` into `apply_authorization_once(...)`.

Required repair:

- replace the hard-coded empty default with a real bounded/read-only production process probe, preferably by reusing an existing repository process-ownership/readiness helper if one exists;
- fail closed if the process check itself cannot be performed reliably;
- exclude only the wrapper's own harmless current process if necessary, never other Printer runtime processes;
- add a focused wrapper-level test proving the default path (not an injected replacement gate) blocks when the production process probe reports an existing Printer process;
- keep the check before marker creation so the authorization remains unconsumed.

## Tests / evidence gap

The implementation reports focused and integrated local PASS results. GitHub has no commit status or workflow run attached to `5defeb035e6693384c2fede5c128030668376c77`, so this independent review treats those as local implementation evidence rather than an independently rerun test result.

The two reported baseline-identical failing test files remain unrelated to these two blockers and should not be expanded into this repair unless a focused change directly intersects them.

## Money-usefulness contribution

The accepted authority separation protects the future four-token learning proof from reusable or ambiguous launch authority. Repairing the two zero-state defects matters because a false block would waste the authorization lane, while a false process-negative could consume an authorization under overlapping runtime state and compromise attribution/safety.

## What this review improves

- accepts the dedicated authority, exact policy, migration evidence, one-use law, and canonical factory composition;
- identifies two narrow pre-consumption correctness gaps before a real authorization is created;
- preserves historical supervision evidence rather than forcing destructive cleanup;
- preserves the no-overlapping-Printer-process safety condition.

## What remains locked

- real four-token authorization preparation/creation;
- four-token runtime;
- live source/RPC execution;
- 12h/24h;
- retrieval;
- paper decisions / BUY / SELL / HOLD;
- positions, trades, audits, PnL;
- live wallet/private keys/real funds/live execution.

## Next permitted lane

`FOUR_TOKEN_ONE_USE_AUTHORIZATION_WRAPPER_INDEPENDENT_REVIEW_REPAIR`

Repair only the two blockers above with focused RED -> GREEN TDD. Preserve all accepted seams. After repair closeout, perform a focused independent rereview before any authorization package is prepared.

## Stop boundary

Do not prepare or create a real authorization and do not run Printer until the repair and independent rereview both pass.