# Printer V1 V2-9.8B Four-Token Proof Readiness Review

Date: 2026-08-13

## Verdict

`V2_9_8B_FOUR_TOKEN_PROOF_READINESS_PARTIAL_READY_WITH_AUTHORITATIVE_DB_STATE_BLOCKER`

The four-token integration is implementation-ready, but this review does **not** authorize a proof or create an authorization. The remaining boundary is operational readiness of the authoritative Mac state, with migration 055 still intentionally unapplied in the last verified evidence.

## Reviewed implementation identity

- Repository: `Dtwosam/MoneyPrinter`
- Branch: `agent/v2-9-8b-four-token-bounded-capacity-proof-integration-implementation`
- Independent implementation rereview baseline: `c15ecc6bb2d7ca083031e7e291f41456528ae73c`
- Prior verdict: `V2_9_8B_FOUR_TOKEN_FINAL_INDEPENDENT_REREVIEW_PASS_READY_FOR_PROOF_READINESS_REVIEW`

## Static readiness findings

### PASS — exact proof authority

The proof controller remains exact:

- configured through-4h tokens = 4
- configured active cycles = 2
- total cycle admissions = 2
- tokens per cycle = 2
- minimum spacing >= 300 seconds

`build_four_token_proof_policy(...)` rejects attempts to widen this proof authority to 6/3. The compiled six-token foundation remains non-authoritative for this proof.

### PASS — public two-token contract remains frozen

The standard public four-hour owner still has `TOKEN_CAPACITY = 2`. The four-token controller is optional and the controller-absent factory path retains the ordinary two-token terminal flow.

### PASS — duration envelope is sufficient at the implementation layer

The canonical factory requires a standard 15m + 1h + 4h lifecycle duration of 15,300 seconds. The exact four-token policy defaults its finite intake/proof deadline to 18,000 seconds. With the earliest lawful second admission at +300 seconds, the second cycle can reach the canonical lifecycle boundary by +15,600 seconds, leaving a 2,400-second margin before 18,000 seconds.

A future authorization/wrapper must preserve a total runtime of at least 18,000 seconds and must not shorten the controller deadline below the lawful second-cycle completion boundary.

### PASS — capacity is derived, not copied

`scaled_standard_four_hour_capacity_contract(4)` derives the simultaneous four-token envelope from the canonical two-token `standard_four_hour_capacity_contract()`.

The canonical two-token public contract remains:

- shared discovery requests = 2
- lifecycle request outer ceiling = 236
- lifecycle requests per token = 117
- lifecycle Scheduler outer ceiling = 210

Therefore the exact four-token simultaneous envelope is derived as:

- shared discovery requests = 4
- lifecycle request outer ceiling = 472
- lifecycle requests per token = 117
- lifecycle Scheduler outer ceiling = 420
- automatic retries = 0
- endpoint rotation = false
- long windows activated = false

### PASS — provider ceilings remain unchanged/free-first

Current registry ceilings relevant to the later-cycle source-free capacity owner remain:

- DexScreener: 60/min
- GeckoTerminal: 10/min
- GoPlus: 20/min
- Helius Free: 30/min
- Solana RPC: 30/min

The capacity owner reads these ceilings from `SOURCE_REGISTRY`; it does not widen them or reserve/execute source work during readiness projection.

### PASS — migration 055 is additive and disposable-schema tested

`055_pre_admission_discovery_attempt_ownership.sql` is additive. The committed schema test applies the canonical migration chain to a disposable DB and proves integrity/FK validity plus the attempt/item/source-link invariants and Scheduler priority law.

No evidence in this review authorizes applying migration 055 to the authoritative DB.

### PASS — implementation verification evidence

The accepted repair closeout records:

- integrated focused set: 183 passed, 31 subtests passed
- complete four-token set: 76 passed, 22 subtests passed
- terminal integration: 2 passed
- accounting adapter + Gate H: 9 passed
- touched production modules: `py_compile` PASS
- `git diff --check` PASS

Known unrelated stale fixture/baseline failures remain outside this lane and must not be misrepresented as new four-token failures.

## Blocking operational evidence

The last verified authoritative-DB evidence before this review was:

- applied migration count = 54
- migration head = `054_pre_lifecycle_discovery_refresh_wait.sql`
- migration 055 applied = false

Current production preflight compares an operational invocation against the canonical migration chain. The canonical chain now includes migration 055. Therefore a four-token operational proof cannot be declared ready while the authoritative DB remains at 054.

Before any DB mutation or authorization, one fresh **read-only** local snapshot must prove all of the following on the Mac:

1. local Git safely fast-forwarded to this review's GitHub head;
2. authoritative DB exists at `data/printer_v1.sqlite3`;
3. current migration ledger/head and whether 055 is absent;
4. `PRAGMA integrity_check = ok`;
5. `PRAGMA foreign_key_check` has zero rows;
6. zero active campaigns/runs/cycles requiring cleanup;
7. zero active campaign Scheduler work, discovery work, factory steps, proof supervision, leases/locks, or Scheduler jobs;
8. no active Printer process/sidecar;
9. old standard-four-hour authorization artifacts remain historical/non-reusable and untouched;
10. authoritative DB hash is recorded before any later migration action.

If that read-only snapshot is clean and still shows 054, the next permitted lane is a narrowly scoped **migration-055 operational readiness/application design and proof**, not four-token authorization.

If 055 is already present unexpectedly, stop and reconcile its provenance before proceeding.

## Money-usefulness contribution

This readiness review protects the first four-token proof from mixing a valid implementation with stale operational schema or leftover ownership. That matters because the intended benefit—four overlapping Solana memecoin trajectories—only improves future memory usefulness if all four paths remain exactly attributable and cleanly closed.

## What this lane improves

- establishes the implementation/static side of four-token proof readiness;
- freezes exact 4/2/2 authority and 18,000-second minimum proof envelope;
- confirms derived four-token budget arithmetic and unchanged provider ceilings;
- identifies the authoritative migration/local-state boundary before authorization.

## What remains locked

This review does not unlock:

- migration 055 application;
- proof authorization or wrapper creation;
- four-token runtime;
- source fetching or Scheduler runtime;
- 12h/24h;
- retrieval;
- paper decisions or BUY/SELL/HOLD;
- positions, trades, audits, or PnL.

## Proof/test required before completion

A fresh read-only authoritative Mac snapshot is required. If clean, migration 055 must then pass its own controlled operational migration lane and closeout before proof readiness can be re-evaluated as PASS.

## Functionality Risks / Setbacks / Efficiency Blockers

- Authoritative DB is last known one migration behind canonical code.
- Local process/lease/active-work state cannot be proven from GitHub alone.
- Applying 055 before a fresh zero-state read would violate the migration/readiness boundary.
- Creating an authorization now would bind a proof to an operational state that is not yet proven current.

## Stop boundary

Stop before any migration write, authorization creation, or runtime proof. The immediate next action is one consolidated read-only local readiness snapshot.