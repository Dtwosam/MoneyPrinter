# Printer V1 V2-9.8B Cycle-2 Exhaustion Reporting / Canonical Execution-Binding Repair Closeout

Date: 2026-08-15

Branch: `agent/v2-9-8b-cycle2-exhaustion-reporting-binding-repair`

Lane: `V2-9.8B — Active Bounded Memory Growth Operations`

## 1. Verdict

```text
V2_9_8B_CYCLE2_EXHAUSTION_REPORTING_CANONICAL_EXECUTION_BINDING_REPAIR_PASS
```

Python Builder Guide §13.3 classification carried through implementation:
`COMMITTED_CODE_DEFECT`. §13.4 coding gate satisfied — smallest correction in the
canonical owner, with focused regression proof.

## 2. Commits

| Stage | SHA | Subject |
|---|---|---|
| starting commit (baseline) | `d5afefab31861b8851b5feb8f799769ae16ad277` | Correct Cycle-2 blocker classification to COMMITTED_CODE_DEFECT |
| design | `90e13bad1a64d87f5dc37b9e8affcb363420611b` | Design Cycle-2 exhaustion reporting canonical execution binding repair |
| RED tests | `a544c4f150cde717d524866b9b4624dc4fee25b3` | Add RED for Cycle-2 exhaustion reporting canonical execution binding |
| implementation | `3d04546d91a9eab823581497b96ef756d7f17a54` | Repair Cycle-2 exhaustion reporting and canonical execution binding |
| closeout | this document | — |

### Branch provenance note

The working branch `agent/v2-9-8b-cycle2-exhaustion-reporting-binding-repair`
did not exist at task start and was created from the baseline commit. The main
worktree was previously on `agent/v2-9-8b-post-repair-zero-state-residue-audit`
@ `8fbfb088`, which is an **ancestor** of the baseline; its work was fully
committed and nothing was lost. Tracked tree and index were clean at start.

Four untracked directories were present at start and remain untouched and
uncommitted — pre-existing local run-evidence residue from prior authorization
and migration applications, untracked at the baseline and not gitignored:

```text
operator-runs/v2-9-8b-four-token-final-authorization/
operator-runs/v2-9-8b-migration-055-application/
operator-runs/v2-9-8b-migration-056-application/
operator-runs/v2-9-8b-standard-four-hour-final-authorization/
```

## 3. Exact files changed

| File | Change |
|---|---|
| `docs/printer-v1-v2-9-8b-cycle2-exhaustion-reporting-canonical-execution-binding-repair-design.md` | new — narrow repair design (design commit) |
| `tests/test_v2_9_8b_cycle2_exhaustion_reporting_canonical_execution_binding.py` | new — 13 focused regression tests (RED commit) |
| `src/printer_v1/operator_cli/four_token_proof_integration.py` | `LaterCycleCandidateSupply` gains a defaulted `diagnostics` field; `dataclasses.field` import |
| `src/printer_v1/operator_cli/later_cycle_graduated_supply.py` | required keyword `execution_id`; cycle-qualified canonical execution identity owns the scope and the `execution_id` kwarg; `selection_seed` now only `cycle_seed`; diagnostics propagated on blocked and successful returns |
| `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py` | `production_later_supply` passes the canonical `execution_id`; classified blocked later-cycle terminals route through the existing `_graduated_supply_terminal_cause` |
| `tests/test_v2_9_8b_four_token_gate_a_supply_identity.py` | updated the one assertion that encoded the defective binding (`scope.execution_id == selection_seed`) to the repaired contract, plus explicit seed/execution separation assertions |

Production diff totals: 3 source files, +54 / −3 lines.

Not touched: `eligible_token_supply.py`, `permanent_discovery_availability.py`,
`graduated_supply_front_door.py`, `one_command_15m_factory.py`,
`pre_admission_discovery_attempt.py`, `migrations/**`, tracking/cooldown
eligibility, reserve exclusion/removal, liquidity floors, source budgets,
discovery algorithm, capacity, scoring/ranking/confidence, retry/automation.

## 4. What was implemented

### 4.1 Canonical execution-binding defect

`build_later_cycle_graduated_supply` now takes a required keyword `execution_id`
— the canonical execution identity of the outer V2-9.8B command — and derives:

```python
cycle_execution_identity = f"{canonical_execution_id}:c{proposed_cycle_ordinal:04d}"
```

which owns both the governed source-request scope and the `execution_id` kwarg
that the exhaustion-certificate owner records. `selection_seed` is now passed
only as `cycle_seed`. An empty canonical id fails closed with
`CANONICAL_EXECUTION_ID_REQUIRED`.

The cycle qualifier is not cosmetic. Source inspection during design proved the
scope identity and the certificate identity are one channel:
`graduated_supply_front_door` validates
`scope.execution_id == execution_id` and
`scope.request_key_root == derive(scope.execution_id)`, then
`inspect_preexisting_source_request_scope_collision` blocks any root a durable
`printer_source_requests` row already owns. A bare canonical id would therefore
reuse Cycle-1's root and block Cycle-2 supply with
`CAMPAIGN_SOURCE_REQUEST_SCOPE_ALREADY_EXISTS`, and would additionally collide
on `certificate_id TEXT PRIMARY KEY` in
`migrations/046_eligible_token_supply.sql`. The cycle-qualified canonical
identity satisfies every stated invariant without either failure. This is
recorded in §4.3 of the design and is the one place where the literal repair
instruction was refined against proven source constraints.

The caller supplies `execution_id=selection_seed` from the enclosing
`run_operational` scope — that outer value is the canonical execution identity,
as the Cycle-1 path at line 3091 already uses. The later-cycle composite arrives
separately as `context["selection_seed"]`.

### 4.2 Blocked diagnostic-propagation defect

`LaterCycleCandidateSupply` gained a fourth, defaulted `diagnostics` field. The
adapter now returns `dict(supply.diagnostics)` on the blocked return and the
successful return. The blocked later-cycle terminalization consults the single
existing mapping owner when a classification is present:

```python
if supply_diagnostics.get("shortage_classification"):
    blocked_cause = _graduated_supply_terminal_cause(supply)
else:
    blocked_cause = supply.terminal_cause or "NO_EXACT_PAIR"
```

No parallel reporting owner was created. `_graduated_supply_terminal_cause`
already reads `getattr(supply, "diagnostics", {})`, so it accepts the carrier
verbatim with no signature change.

## 5. Tests and checks run, with results

All commands run with the repository virtualenv interpreter `.venv/bin/python`.

| # | Command | Result |
|---|---|---|
| 1 | `pytest tests/test_v2_9_8b_cycle2_exhaustion_reporting_canonical_execution_binding.py` (at baseline, RED) | **11 failed, 2 passed** — RED established |
| 2 | `pytest tests/test_v2_9_8b_cycle2_exhaustion_reporting_canonical_execution_binding.py` (post-repair) | **13 passed** |
| 3 | `pytest` on the 10 nearest directly affected modules + the focused module | **63 passed** |
| 4 | `python -m compileall` on the 3 touched source modules + 2 touched test modules | `COMPILEALL_OK` |
| 5 | `importlib.import_module` on the 3 touched source modules | `IMPORT_OK` |
| 6 | `git diff --check` | `DIFF_CHECK_OK` |
| 7 | manual diff/static inspection of the full production diff | reviewed, minimal, no unrelated change |

The 2 tests already passing at RED are the backward-compatibility guards
(3-positional construction reaching the callback, and the no-diagnostics blocked
path preserving `NO_EXACT_PAIR`), which correctly must not have been broken by
the baseline.

Modules in check 3:

```text
tests/test_v2_9_8b_cycle2_exhaustion_reporting_canonical_execution_binding.py
tests/test_v2_9_8b_four_token_gate_a_supply_identity.py
tests/test_v2_9_8b_pre_admission_later_cycle_callback.py
tests/test_v2_9_8b_four_token_factory_terminal_integration.py
tests/test_v2_9_8b_four_token_gate_h_integrated_disposable.py
tests/test_v2_9_8b_four_token_consumed_proof_blocker_tdd.py
tests/test_v2_9_8b_callback_consume_materialize_integration.py
tests/test_v2_9_8b_selective_1h_liquidity_evidence_repair.py
tests/test_v2_9_8b_post_dtw96_supply_truth_repair.py
tests/test_v2_9_8b_four_token_later_cycle_discovery_callback_contract.py
tests/test_v2_9_8b_post_dtw99_build_graduated_supply_temporal_owner_interface.py
```

No unrelated pre-existing failure was observed in this set. No broad or full
suite was run; the change stayed narrow, so verification stayed inside the
Risk-Based Verification Policy band for a narrow code change.

### 5.1 Exactly what the focused tests prove

1. the canonical `execution_id` reaches the governed source-scope construction —
   `scope.execution_id`, `scope.request_key_root`,
   `discovery_request_key_prefix`, `front_door_request_key_prefix`;
2. the canonical `execution_id` reaches the graduated-supply `execution_id`
   kwarg that owns the exhaustion certificate;
3. `selection_seed` is preserved separately and reaches only `cycle_seed`; the
   factory-run and campaign-run identities no longer appear in the scope or the
   execution identity;
4. an empty canonical execution id fails closed;
5. blocked later-cycle supply preserves `shortage_classification`,
   `exhaustion_certificate` and `tracking_terminal_cause`;
6. the successful path preserves diagnostics;
7. 3-positional `LaterCycleCandidateSupply(candidates, evidence, cause)`
   construction remains valid;
8. `TRACKING_STATE_CAPACITY_BLOCKED` reaches the existing authoritative mapping
   and yields `COOLDOWN_REOPEN_REQUIRED` — never
   `BLOCKED_INSUFFICIENT_ELIGIBLE_CANDIDATE_POOL` or
   `BLOCKED_INSUFFICIENT_GRADUATED_POOL` — end to end into the durable
   `printer_pre_admission_discovery_attempts.first_terminal_cause`;
9. `_project_supply_exhaustion_certificate` is non-null for adapter-supplied
   diagnostics;
10. a proven `TRUE_MARKET_SUPPLY_SHORTAGE` still retains the historical
    insufficient-pool compatibility conclusion;
11. a blocked supply with no diagnostics keeps its existing terminal cause
    exactly.

## 6. Proof that no DB / runtime / source-fetch / authorization / live-proof activity occurred

- **Authoritative database untouched.** `data/printer_v1.sqlite3` after all work:
  sha256 `09684edd29a013a80748a03a7d3932f2dde1804c91ea58a02c4f76fb67863645`,
  size `96612352`, inode `1230526`. This is byte-identical to the SHA, size and
  inode recorded by the preceding read-only reconciliation (§2 of
  `docs/printer-v1-v2-9-8b-cycle2-authoritative-exhaustion-certificate-reconciliation.md`).
  No `-wal`, `-shm` or `-journal` sidecar exists.
- **No authoritative DB connection was opened.** Every database in this lane was
  a per-test `tmp_path` SQLite fixture created by `apply_migrations`; the
  authoritative path was only `stat`/hashed read-only for this evidence.
- **No source fetching.** `build_graduated_supply` was monkeypatched in every
  focused test; no transport, provider, RPC, DexScreener, GeckoTerminal,
  PumpPortal or Solana RPC call was constructed or issued. `migration_transport`
  was an inert `object()`.
- **No runtime.** No campaign, Source Governor, Central Scheduler, factory loop,
  lifecycle, window, or memory-generation execution was started. The scheduler
  rows exercised in tests are fixture rows inside `tmp_path`.
- **No memory generation.** Zero `printer_memory_windows` rows created outside
  fixtures; the gate-A regression asserts zero across tracking queue, scheduler
  jobs, campaign cycles, campaign windows and memory windows.
- **No authorization.** No authorization was created, consumed, read as
  execution authority, or referenced. Authorization #7 was not created. The
  existing `operator-runs/` authorization directories were not read, written,
  modified or committed.
- **No four-token proof rerun**, no retry, resume, restart, successor or
  campaign of any kind.
- **No schema migration and no historical DB rewrite.** `migrations/` is
  unchanged; ledger stays at `56` / head `056`. Existing certificates keep their
  recorded historical identities.
- **No financial capability touched:** no retrieval, paper decisions,
  BUY/SELL/HOLD, positions, trade events, paper audits or PnL.

## 7. Money-usefulness contribution

Printer becomes money-useful only by growing clean memory, and it only grows
clean memory if the operator's read of *why* a campaign produced no tokens is
true. Before this repair every later-cycle shortage — of any classification —
surfaced as an insufficient-pool market conclusion. That is exactly what
happened on execution `20260815T194831Z-6d09a756e8d1`: the durable certificate
said `TRACKING_STATE_CAPACITY_BLOCKED` with liquidity-proven reserve tokens
present, while the host artifacts said the market was thin.

An operator acting on that false reading either burns another scarce one-shot
authorization against an unchanged internal condition, or abandons a supply
route that was never empty. This repair makes the already-correct classification
visible at the point of decision, at zero authorization and zero source cost. It
ends the wasted-proof loop and points the next lane at the real, internal,
addressable condition.

## 8. What improved

- The Cycle-2 exhaustion certificate is now bound to the canonical execution id
  (cycle-qualified) rather than to the factory-run/campaign-run selection seed,
  so it is discoverable by canonical-execution-id prefix and no longer invisible
  to tooling keyed on execution id.
- The selection seed no longer silently owns execution identity, source-request
  scope, and certificate identity; it is selection input only.
- `LaterCycleCandidateSupply` carries the diagnostics the adopted eligible-supply
  design requires, on the blocked **and** successful paths, without breaking any
  existing construction site.
- `TRACKING_STATE_CAPACITY_BLOCKED` now reaches the existing truthful mapping, so
  the pre-admission attempt terminal — and therefore the factory `stop_reason`,
  `terminal-summary.json` and `child-terminal.json` — record
  `COOLDOWN_REOPEN_REQUIRED` (or the exact `tracking_terminal_cause`) instead of
  a market conclusion the code's own docstring forbids.
- `exhaustion_certificate` and `shortage_classification` project non-null from
  adapter-supplied diagnostics through the existing projection owner.
- Only a proven `TRUE_MARKET_SUPPLY_SHORTAGE` — or an absent classification,
  which preserves prior behaviour byte-for-byte — retains the historical
  insufficient-pool conclusion.
- The correction is unconditional on the later-cycle path, so every future
  later-cycle shortage class is reported truthfully, not only this run's
  condition.

## 9. What remains locked

Unchanged and still locked: authorization creation and consumption (including
authorization #7), four-token proof execution or rerun, campaign start,
six-token proof and capacity widening, `WINDOW_1H` / `WINDOW_12H` / `WINDOW_24H`
activation, discovery and source fetching, runtime, authoritative DB mutation,
memory generation, schema migration and historical DB rewrite, tracking/cooldown
eligibility changes, reserve exclusion/removal changes, liquidity-floor changes,
source-budget changes, discovery-algorithm changes, capacity changes,
scoring/ranking/confidence/weighted logic, retry/automation, retrieval, paper
decisions, BUY/SELL/HOLD, positions, trade events, paper audits, PnL, wallets,
private keys, real funds, live execution, paid APIs, embeddings and vectors.
Solana memecoin-only and paper-only remain in force.

The tracking-state / reserve-exclusion question — including the 10
`PERSISTED_GRADUATED` / `LIQUIDITY_PROVEN` rows observed `EXCLUDED` / `REMOVED`
— was **not** investigated, **not** assumed defective, and **not** begun. It
remains the separate next lane.

## 10. Functionality Risks / Setbacks / Efficiency Blockers

| Risk / blocker | Consequence | Status / control |
|---|---|---|
| Bare canonical execution id for the Cycle-2 scope | Would block Cycle-2 supply on `CAMPAIGN_SOURCE_REQUEST_SCOPE_ALREADY_EXISTS` and collide on `certificate_id` | Avoided by design §4.3; cycle-qualified identity implemented and asserted |
| Cycle-2 request-key root changed | Cycle-2 `_source_lineage` window moves | Root stays cycle-exclusive; no Cycle-1 key can start with the Cycle-2 root; gate-A lineage regression passes |
| Historical certificates keep the old composite identity | A canonical-id query still misses pre-repair Cycle-2 rows | Accepted and explicit — no historical rewrite, no migration. Recorded as historical evidence |
| Fourth dataclass field | Could break 3-positional construction | Defaulted; five existing modules exercising the 3-positional form pass |
| `diagnostics` makes the frozen carrier unhashable | A caller hashing it would fail | Static inspection found no caller hashing or set-inserting `LaterCycleCandidateSupply`; only `isinstance` and equality are used |
| Routing the blocked cause through the mapping owner | Could change causes where no classification exists | Guarded and asserted: unclassified supplies keep the exact prior cause |
| Truthful cause becomes the factory `stop_reason` | A different terminal string reaches host artifacts | Intended and contract-required; no lifecycle, retry, or cleanup logic is keyed on the old string |
| Certificate still not durably projected into the later-cycle host report | `report.exhaustion_certificate` can remain null for a Cycle-2 block | Out of boundary — see §11. The truthful *classification* now reaches the terminal, which is the decision-relevant fact |
| One pre-existing test asserted the defective binding | Repair would appear to regress it | `tests/test_v2_9_8b_four_token_gate_a_supply_identity.py` updated to the repaired contract with explicit seed/execution separation assertions; documented here, not silently changed |
| Repair mistaken for resolution of the underlying shortage | Operator could assume supply is fixed | It is a diagnosis fix only. The reserve-exclusion audit remains required before any authorization |
| Verification deliberately narrow | A distant consumer could be affected | Scope confined to three modules with no signature change reaching outside the later-cycle seam; if a broader consumer is later found, a bounded follow-up check is cheap |

## 11. Is further bounded offline proof required?

**Not for this repair.** Focused verification is GREEN and the boundary is
closed.

One bounded offline follow-up is *recommended but not required by this lane*:
durably projecting the Cycle-2 exhaustion certificate itself into the campaign
terminal report. That needs either an approved schema addition to
`printer_pre_admission_discovery_attempts` or an approved in-memory hand-back
from the later-cycle callback into the report assembler — both outside this
repair boundary and both requiring their own design lane. Until then,
`report.exhaustion_certificate` may remain null for a Cycle-2 block even though
the truthful terminal cause is now correct and the certificate is correctly
persisted and canonically addressable.

The design also flagged a boundary worth future coverage, carried forward from
the reconciliation: four GeckoTerminal rate-limit `STALE` failures occurred
outside the liquidity stage in the observed run and are not represented in the
certificate counters. Under a different ordering they would have selected
`STALE_EVIDENCE_SHORTAGE`. That is a classification-precedence concern owned by
`eligible_token_supply.py`, which this lane did not touch.

## 12. Exact next permitted lane

```text
V2-9.8B Tracking-State / Reserve-Exclusion Read-Only Audit
```

Read-only. It must explain why liquidity-proven `PERSISTED_GRADUATED` reserve
entries are `EXCLUDED` / `REMOVED`. It must not assume they are defective.

No authorization may be created and the four-token proof must not be rerun until
that audit closes.
