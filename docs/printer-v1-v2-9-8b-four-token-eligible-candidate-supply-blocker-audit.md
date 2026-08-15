# Printer V1 V2-9.8B Four-Token Eligible-Candidate Supply Blocker Audit

Date: 2026-08-15

Baseline: `f687025fe28ebf3a9908e1764f7094438336f461`

Execution under audit: `20260815T194831Z-6d09a756e8d1`

Consumed authorization: `V2_9_8B_FOUR_TOKEN_PROOF_AUTH_20260815T194632Z_d96669fa`

## 1. Verdict

```text
V2_9_8B_FOUR_TOKEN_ELIGIBLE_CANDIDATE_SUPPLY_BLOCKER_AUDIT_BLOCKED_RUNTIME_CERTIFICATE_RECONCILIATION_REQUIRED
```

Python Builder Guide primary classification:

```text
UNKNOWN_REQUIRES_RESEARCH
```

Exact eligible-supply shortage classification:

```text
UNRESOLVED_FROM_AVAILABLE_COMMITTED_EVIDENCE
```

No code change is justified by this audit yet. No new authorization is justified.

The committed execution closeout proves that the one-shot machinery worked and
that the campaign terminalized safely, but it does **not** expose the exact
Cycle-2 eligible-supply exhaustion certificate needed to distinguish genuine
market/source shortage from source availability, budget/duration exhaustion,
stale evidence, or an architecture-induced false shortage.

## 2. Scope and lane boundary

This audit is read-only/static only.

Performed:

- inspected the authoritative-root execution closeout at the exact baseline;
- inspected the adopted Eligible Token Supply design/closeout;
- traced the canonical persistent supply implementation;
- traced the Cycle-2 later-cycle supply adapter and four-token carrier;
- inspected terminal-report surfaces for exhaustion-certificate propagation.

Not performed:

- no authorization creation or consumption;
- no provider, RPC, discovery, Source Governor, Scheduler, campaign, lifecycle,
  memory, retrieval, decision, position, trade, audit-runtime, or PnL execution;
- no authoritative DB mutation;
- no production code, test, migration, configuration, floor, capacity, budget,
  or retry change;
- no rerun/retry/resume/restart/successor of the four-token proof.

All V1/V2 locks remain unchanged.

## 3. Facts established by the consumed execution closeout

The committed closeout establishes:

- Stage 0 and A-C passed;
- the authorization was consumed exactly once;
- the child exited `0` with a valid terminal envelope;
- campaign/run terminalized `TERMINAL_FAILED` and Cycle 1 terminalized
  `TERMINAL_BLOCKED` with
  `BLOCKED_INSUFFICIENT_ELIGIBLE_CANDIDATE_POOL`;
- the factory selected two tokens for Cycle 1;
- Cycle 2 was never admitted, so four-token concurrency was not exercised;
- exactly one `WINDOW_15M` was created and it was
  `DIRTY_MEMORY / MISSING_CRITICAL_DATA / do_not_train=1`;
- all eleven active-ownership domains were zero after terminal cleanup;
- the closeout recorded authoritative DB SHA transition
  `555f9558... -> 09684edd...`, integrity `ok`, FK `0`, no sidecars, ledger
  `56 / 056`;
- no retry, rerun, resume, restart, successor, longer-window activation,
  retrieval, decision, position, trade, audit or PnL occurred.

These facts prove machinery/cleanup behavior. They do **not** by themselves
prove what kind of eligible-supply shortage occurred.

## 4. Adopted eligible-supply contract

`docs/printer-v1-v2-9-8b-eligible-token-supply-architecture-design.md` is
explicit:

1. discovery remains persistent inside the same authorized campaign until
   capacity or proven exhaustion;
2. the six-candidate front-door bound is one evaluation batch, not the reachable
   universe;
3. fewer than two eligible tokens may terminalize only under legitimate bounded
   stop conditions;
4. every below-capacity terminal must carry a durable exhaustion certificate;
5. the certificate must state exact counts, rejection reasons, source operations
   used/remaining, duration used/remaining, channel availability, whether a hard
   ceiling prevented unexplored work, and an exact shortage classification;
6. a one-batch conclusion while lawful unexplored work and budget remain is an
   invalid certificate;
7. blocked-supply terminal reporting must include:

```text
exhaustion_certificate
shortage_classification
discovery_rounds
eligible_reserve_count
```

The shortage classes include:

```text
TRUE_MARKET_SUPPLY_SHORTAGE
SOURCE_VISIBILITY_SHORTAGE
SOURCE_AVAILABILITY_FAILURE
BUDGET_EXHAUSTION
DURATION_EXHAUSTION
STALE_EVIDENCE_SHORTAGE
DISCOVERY_ARCHITECTURE_FALSE_SHORTAGE
```

Therefore the generic terminal
`BLOCKED_INSUFFICIENT_ELIGIBLE_CANDIDATE_POOL` is not enough to identify the
actual shortage class.

## 5. Static implementation trace

### 5.1 Canonical persistent supply preserves the required detail

`src/printer_v1/discovery/eligible_token_supply.py` owns the persistent
multi-round loop and durable exhaustion certificates.

Its result/diagnostic model distinguishes the approved shortage classes and
persists `printer_discovery_exhaustion_certificates` when capacity is unmet.
The implementation treats remaining lawful unexplored work plus remaining
budget/duration as `DISCOVERY_ARCHITECTURE_FALSE_SHORTAGE`, rather than true
market shortage.

### 5.2 `build_graduated_supply` retains the detail

`src/printer_v1/operator_cli/graduated_supply_front_door.py` invokes the
persistent supply owner. Its diagnostics include:

- `exhaustion_certificate`;
- `shortage_classification`;
- `discovery_rounds`;
- reserve/supply diagnostics.

For permanent availability, any not-ready result maps to the generic public
terminal `BLOCKED_INSUFFICIENT_ELIGIBLE_CANDIDATE_POOL`, regardless of which
underlying approved shortage classification explains the result.

That mapping is safe only if the underlying certificate/classification remains
available to terminal reporting, as the adopted design requires.

### 5.3 Cycle-2 adaptation loses that detail at its immediate boundary

`src/printer_v1/operator_cli/later_cycle_graduated_supply.py` calls the same
canonical `build_graduated_supply(...)` for proposed Cycle 2.

Its not-ready branch is:

```python
if not supply.ready or len(supply.graduated_supply) != 2:
    return LaterCycleCandidateSupply((), (), supply.terminal)
```

`LaterCycleCandidateSupply` in
`src/printer_v1/operator_cli/four_token_proof_integration.py` carries only:

- `candidates`;
- `source_evidence`;
- `terminal_cause`.

Therefore the immediate Cycle-2 return boundary does not carry the
`GraduatedSupply.diagnostics`, exhaustion certificate, shortage classification,
discovery rounds or reserve count. On the not-ready path its `source_evidence`
tuple is also empty.

This is a material reporting-boundary concern because the generic terminal alone
cannot prove honest external shortage.

### 5.4 No committed report query found that independently restores the detail

Static inspection found `printer_discovery_exhaustion_certificates` in the
operational DB surface/allowlist and in the eligible-supply/discovery-only
owners, but the final campaign report owner does not query or project an
exhaustion certificate.

The authoritative-root closeout also does not record the certificate,
`shortage_classification`, `discovery_rounds`, `eligible_reserve_count`,
unexplored-work state, or exact discovery budget/duration state for the Cycle-2
block.

This creates a static **reporting-contract mismatch candidate**. It is not yet
promoted to `COMMITTED_CODE_DEFECT` in this audit because the decisive current
run row(s) and terminal artifact must first be reconciled from the authoritative
database. The durable certificate may exist correctly even though the closeout
failed to surface it.

## 6. Why `external supply` is not yet an auditable conclusion

The execution closeout's statement that the blocker is external supply is a
reasonable hypothesis, but the committed evidence available here does not prove
it.

The same generic terminal can sit above several materially different facts:

- all reachable candidates genuinely exhausted;
- approved sources returned no additional unique candidates;
- provider/source availability failed;
- discovery operation budget exhausted;
- duration exhausted;
- only stale evidence remained;
- lawful unexplored work still existed, which would be an architecture false
  shortage.

Printer previously repaired exactly this class of false-shortage error, so the
current run must be classified from its exact durable certificate rather than by
terminal wording.

## 7. Evidence still required from the authoritative DB

The connected GitHub repository contains the committed code and closeout, but
not the live authoritative SQLite corpus or the untracked host-only execution
artifacts. This audit therefore cannot independently re-derive the current DB
SHA or read the exact Cycle-2 exhaustion certificate.

The minimum sufficient read-only reconciliation is:

1. Record current repository branch/HEAD/tracked state and current authoritative
   DB identity; reconcile legitimate drift from the closeout-recorded POST SHA
   `09684edd...` before interpreting rows.
2. Identify the exact Cycle-2 pre-admission attempt for:
   - campaign `20260815T194831Z-6d09a756e8d1-campaign`;
   - its campaign run;
   - authoritative factory run
     `9296ffff-7e71-46d2-8e63-dd7b755780c9`;
   - proposed cycle ordinal `2`.
3. Read the matching row from
   `printer_discovery_exhaustion_certificates` using exact campaign/run/cycle/
   execution identities, not timestamps or symbols.
4. Reconcile the certificate against:
   - `printer_eligible_token_reserve`;
   - relevant market-floor state;
   - source requests/responses/failures under the exact Cycle-2 request-key
     scope;
   - pre-admission attempt/source-evidence/item rows;
   - discovery operation accounting and duration boundary.
5. Independently verify:
   - required capacity = 2;
   - exact eligible reserve count;
   - unique candidates observed/evaluated;
   - exact rejection reasons;
   - channels attempted/unavailable;
   - provider failures;
   - source operations used/remaining;
   - duration used/remaining;
   - whether lawful unexplored unique work remained;
   - persisted shortage classification.
6. Validate the row against `HONEST_EXHAUSTION` and only then classify the
   execution as true market, visibility, source availability, budget, duration,
   stale-evidence, or architecture-false shortage.

No source/provider call is needed for this reconciliation.

## 8. Python Builder Guide blocker classification

```text
BLOCKER CLASSIFICATION:
UNKNOWN_REQUIRES_RESEARCH

EVIDENCE:
Consumed execution terminal + adopted eligible-supply contract + static
Cycle-2 supply/reporting call path. Exact current-run exhaustion-certificate
row is not available through committed GitHub evidence.

PRINTER-CONTRACT COMPARISON:
The contract requires honest exhaustion plus certificate/classification detail
for a below-capacity terminal. The generic terminal alone is insufficient.

ROOT CAUSE:
The actual Cycle-2 shortage class is not recoverable from the committed closeout.
The immediate later-cycle adapter also drops supply diagnostics on its not-ready
return boundary.

CODE CHANGE JUSTIFIED:
NO — not until the exact authoritative certificate/report state is reconciled.

AUTHORIZATION STATUS:
Consumed and permanently non-reusable. No fresh authorization justified.
```

## 9. Money-usefulness contribution

This audit prevents Printer from burning another one-shot authorization based on
an unproven supply diagnosis. The useful money-learning path requires honest
candidate scarcity: if the market is truly thin, retrying wastes source budget;
if visibility/provider/budget is the problem, a retry under unchanged conditions
also wastes budget; if a false shortage remains, repeated attempts hide a real
architecture defect and starve clean memory growth.

## 10. What this audit improves

- separates execution-machinery success from candidate-supply truth;
- prevents the generic terminal from being treated as proof of market scarcity;
- identifies the exact durable evidence required to classify the run;
- exposes a Cycle-2 reporting-boundary concern without prematurely patching it;
- preserves the consumed authorization as historical/non-reusable evidence.

## 11. What remains locked

Still locked:

- another four-token authorization/attempt;
- six-token proof or capacity widening;
- `WINDOW_1H`, `WINDOW_12H`, `WINDOW_24H` activation;
- retrieval;
- paper decisions and BUY/SELL/HOLD;
- positions, trade events, paper-trade audits and PnL;
- wallets, private keys, signing, real funds and live execution;
- paid APIs;
- scoring, ranking, confidence, weighted logic, embeddings and vectors.

## 12. Proof needed before this blocker can close

One authoritative-root, **read-only**, zero-source reconciliation of the exact
Cycle-2 exhaustion certificate and its source/reserve/budget evidence.

No broad test suite is needed. No production code should change during that
reconciliation.

## 13. Functionality Risks / Setbacks / Efficiency Blockers

| Risk / blocker | Consequence | Control |
|---|---|---|
| Generic terminal treated as true market shortage | Wrong diagnosis and wasted authorization | Require exact exhaustion certificate |
| Another authorization before classification | Likely repeats a non-informative failure | Keep authorization locked |
| Certificate exists but closeout omits it | Operator cannot audit shortage truth | Reconcile durable row, then review reporting boundary |
| No valid certificate exists | Honest-exhaustion contract was violated | Stop for separate design/repair classification |
| Unexplored work remained with budget/duration | Architecture false shortage | Classify fail-closed; no rerun |
| Provider/source failure hidden as market shortage | Misstates external conditions | Preserve shortage-class precedence |
| Repairing the adapter before DB reconciliation | Could fix the wrong boundary | Finish read-only evidence audit first |

## 14. Exact next permitted lane

```text
V2-9.8B Four-Token Cycle-2 Authoritative Exhaustion-Certificate Read-Only Reconciliation
```

Type: audit continuation / read-only only.

It may inspect the authoritative DB and existing host artifacts. It may not call
providers/RPC, mutate the DB, create authorization, execute a campaign, change
code, or unlock any later capability.

After that reconciliation:

- if the certificate proves a legitimate operational shortage and reporting is
  otherwise contract-complete, classify
  `EXPECTED_OPERATIONAL_BLOCKER__NO_CODE_CHANGE` and decide separately whether a
  bounded discovery-only supply qualification is useful before another proof;
- if the durable certificate/report contract is absent or contradicted by the
  code path, classify the exact coding/design category under Python Builder
  Guide section 13 and only then open the required design/repair lane;
- if evidence remains insufficient, stay `UNKNOWN_REQUIRES_RESEARCH` and do not
  spend another authorization.
