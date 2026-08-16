# Printer V1 — V2-9.8B Post-Four-Token-Proof Blocker Repair — Design

Lane: V2-9.8B only. Scope: repair the four proven **non-causal** closeout/evidence
defects observed after the consumed four-token bounded-capacity proof.

* Design baseline HEAD: `7774a0c3474da464e18d6d28aab59e8c9d1845ac`
* Baseline branch: `agent/v2-9-8b-persistent-multisource-fresh-acquisition-implementation`
* Accepted entry verdict:
  `V2_9_8B_POST_FOUR_TOKEN_PROOF_BLOCKER_REPAIR_READINESS_AUDIT_PASS_READY_FOR_DESIGN`

The consumed four-token proof is immutable historical evidence. This lane never
reruns, retries, resumes, restarts, or re-authorizes it, never contacts a
provider, and never advances V2-10.

---

## 1. Authoritative defect evidence (read-only, from the consumed proof)

All four defects are reproduced from durable artifacts of the single consumed
authorization `V2_9_8B_FOUR_TOKEN_PROOF_AUTH_20260816T212509Z_89920eef`
(execution `20260816T213315Z-5039b5eecb81`, factory run
`77a24090-8b4d-415c-b0ae-26c41df9838a`). No authoritative write was performed to
gather it.

Observed run shape (honest): `run_status=SAFE_STOPPED`,
`first_terminal_cause=TERMINAL_TRACKING_STATE`, 1 cycle, 2 tokens, 18 lifecycle
Scheduler jobs (16 `SNAPSHOT` + 2 `WINDOW_CLOSE`), no `WINDOW_1H`/`WINDOW_4H`
continuation steps, memory windows 199/200 both `CLEAN_PROMOTED`.

### D1 → R1 — Closeout window identity

`campaign_acceptance.compensation_blocked_reasons` contains:

```
WINDOW_NOT_REGISTERED_AT_CLOSE_BOUNDARY:57
WINDOW_NOT_REGISTERED_AT_CLOSE_BOUNDARY:58
```

The campaign windows **were** correctly registered. Durable rows carry the
canonical precreated identity:

```
cw:<campaign>:<run>:<cycle>:slot-<cycle>-1:WINDOW_15M:factory-root  token 57 pair 61 mem 199 CLEAN_PROMOTED
cw:<campaign>:<run>:<cycle>:slot-<cycle>-2:WINDOW_15M:factory-root  token 58 pair 62 mem 200 CLEAN_PROMOTED
```

`campaign_full_run_accounting.finalize_full_run_ownership_and_report`
(`campaign_full_run_accounting.py:2522`) computes the **legacy** identity
`f"{cycle_id}:window:{token_id}"` unconditionally and looks that up
(`:2540`). Under the proof-owned path the factory persists into the canonical
`cw:` row (`one_command_15m_factory.py:4160-4182` →
`operational_selective_1h.persist_15m_campaign_window`), so the legacy lookup
misses. Non-causal: the ownership row exists, is exact, and is terminal.

### D2 → R2 — Scheduler ownership

18 identical block reasons:

```
SCHEDULER_PROJECTION_FAILED:<job>:scheduler job already owned by another campaign work row
```

for jobs 2060–2077. Each job already has exactly **one** canonical
`V2_STAGE_SCOPED` / `WINDOW_LIFECYCLE` owner created at enqueue time by
`one_command_15m_factory._project_proof_15m_scheduler_owner` with
`scheduler_work_id = cw15m:<campaign>:<run>:<cycle>:<slot>:<window>:<job>`.

The closeout re-projects the same job under a *different* deterministic id
`campaign_scheduler_work_id() = campaign-work|<campaign>|<job>`
(`campaign_full_run_accounting.py:2605-2638`), and
`campaign_ownership.project_campaign_scheduler_work` correctly refuses
(`campaign_ownership.py:2208-2217`) to give one Scheduler job a second owner.
Non-causal: the one-job-one-owner invariant is *working*; the closeout is asking
for a second owner it does not need.

Read-only confirmation of the 18 owner rows: `work_state='SUCCEEDED'`,
`work_scope='WINDOW_LIFECYCLE'`, `target_category='CAMPAIGN_WINDOW'`,
`target_identity == window_id == cw:…:WINDOW_15M:factory-root`,
`ownership_contract_version='V2_STAGE_SCOPED'`, exact campaign/run/cycle/
factory-run/slot. The canonical owner is already state-synchronized with the
Scheduler row, so no closeout projection is needed to advance it.

### D3 → R3 — Proof-root correspondence

`full_run_accounting.scheduler_ownership`:

```
correspondence_exact       : false
expected_lifecycle_scheduler_count : 18
lifecycle_job_ids == owned_job_ids == all 18
duplicate_step_job_ids / duplicate_owned_job_ids : false
all_lifecycle_jobs_succeeded : true
lineage_mismatch_job_ids   : all 18
```

Every other lineage predicate in `_load_terminal_scheduler_correspondence`
(`:1805-1821`) holds. The single failing predicate is `_terminal_stage_matches`
(`:1686-1703`): the canonical proof owner carries the bare root stage
`stage_id='WINDOW_15M'`, which is accepted only when `allow_proof_root_stage` is
true — and the closeout call site (`:2656`) passes no `factory_step_ids`, so the
flag is false. Non-causal: the already-approved proof-aware acceptance exists but
is not threaded to the closeout.

### D4 → R4 — Child-terminal fidelity

The consumed proof's `child-terminal.json` (create-once, schema
`PRINTER_V1_FOUR_TOKEN_PROOF_CHILD_TERMINAL_V1`) reports:

```
lifecycle_started        : null      cleanup_complete   : null
cycle_id                 : null      lease_released     : null
supervision_id           : null      active_locked_work : null
terminal_report_path     : null      source_calls       : null
terminal_report_sha256   : null      scheduler_runtime_calls : null
database_identity_after  : null      database_writes    : null
success: true   process_exit_code: 0   terminal_truth_status: NOT_APPLICABLE_SUCCESS
```

while the campaign verdict was `BLOCKED_UNSAFE`. Every one of those facts existed
authoritatively at the terminal boundary. The cause is that the four-token
success result (`operational_memory_factory_command.py:4094-4129`, the `terminal`
dict) does not expose them under the names the child-terminal projector reads,
and `window_15m_child_terminal._find_key` deliberately does not traverse
arbitrarily. Non-causal: the envelope schema, bound, redaction, and create-once
contract are all intact — only the projected values are absent.

`success: true` alongside `BLOCKED_UNSAFE` also demonstrates the standing
invariant this repair must preserve: **`CHILD_EXITED_ZERO` is not proof PASS.**

---

## 2. Repair boundary

| | Mutation | Verification |
|---|---|---|
| R1 | **none** — never creates, rewrites, or replaces a campaign window row | resolve the already-persisted canonical window as authority; verify slot/token/pair/memory binding |
| R2 | only the pre-existing legacy projection, and only for genuinely **unowned** jobs | when an exact canonical `V2_STAGE_SCOPED` owner exists, verify it and project nothing |
| R3 | **none** | per-step-identity widening of stage acceptance inside the already-approved proof-aware context |
| R4 | **none** — read-only `stat`/`sha256` of files already written | truthful projection of values already computed at the terminal boundary |

No repair introduces a write that did not already exist. R2 strictly reduces the
set of writes the closeout attempts.

---

## 3. R1 — Closeout window identity

### Algorithm

New private helper in `campaign_full_run_accounting.py`:

```
_resolve_close_boundary_campaign_window(
    connection, *, context, token_slot_id, token_id, pair_id, memory_row_id
) -> (window_id: str, terminal_state: str | None, blocked: list[str])
```

1. Query the canonical authority — the already-persisted campaign window for this
   exact ownership tuple:

   ```sql
   SELECT window_id, window_state, memory_window_row_id, token_row_id, pair_row_id
     FROM printer_memory_factory_campaign_windows
    WHERE campaign_id=? AND run_id=? AND cycle_id=? AND token_slot_id=?
      AND window_kind='WINDOW_15M'
    ORDER BY window_id
   ```

2. **> 1 row** → `CAMPAIGN_WINDOW_IDENTITY_AMBIGUOUS:{token_id}`; return the
   legacy identity with no terminal state. Duplicate bindings still block.

3. **1 row** → that row's `window_id` is the authority (canonical `cw:` in the
   proof-owned shape; a legacy id if that is what was persisted). Verify, all
   fail-closed:
   * `token_row_id == token_id` and `pair_row_id == pair_id`, else
     `CAMPAIGN_WINDOW_IDENTITY_MISMATCH:{token_id}` (wrong-slot binding blocks);
   * `memory_window_row_id` is not NULL and equals the close step's
     `memory_window_id`, else `WINDOW_NOT_REGISTERED_AT_CLOSE_BOUNDARY:{token_id}`
     (wrong-memory binding blocks — reason string preserved verbatim).
   On success return `(row.window_id, str(row.window_state), [])`.

4. **0 rows** → lawful legacy non-precreated fallback: return
   `(f"{context.cycle_id}:window:{token_id}", None, [])` and let the **existing**
   exact-lookup path at `:2540` run unchanged. A genuinely missing registration
   therefore still yields `WINDOW_NOT_REGISTERED_AT_CLOSE_BOUNDARY:{token_id}`.

The caller keeps `token_to_window[token_id] = window_id`, so the resolved
identity flows into `token_to_identity[...]["campaign_window_id"]`, into the
Scheduler-owner resolution (R2), and into `registered_windows`.

### Failure behavior

Missing, duplicate, wrong-slot, and wrong-memory bindings all block, as today.
Only the *identity computation* changes; no acceptance check is relaxed.

### Compatibility

* Legacy non-precreated runs: 0 canonical rows for the slot → step 4 → byte-for-byte
  the current code path.
* `registered_windows` keeps its current cardinality and contents on legacy runs.

---

## 4. R2 — Scheduler ownership

### Algorithm

New private helper in `campaign_full_run_accounting.py`:

```
_resolve_lifecycle_scheduler_owner_disposition(
    connection, *, context, scheduler_job_id, token_slot_id, window_id
) -> ("VERIFIED" | "PROJECT" | "BLOCKED", reason: str | None)
```

Query every owner of the job (global, not scoped — this is the one-job-one-owner
probe):

```sql
SELECT scheduler_work_id, campaign_id, run_id, cycle_id, factory_run_id,
       token_slot_id, window_id, work_scope, target_category, target_identity,
       ownership_contract_version
  FROM printer_memory_factory_campaign_scheduler_work
 WHERE scheduler_job_id = ?
 ORDER BY scheduler_work_id
```

* **0 rows** → `PROJECT`. Genuinely unowned legacy work; the existing
  `project_campaign_scheduler_job(...)` call runs unchanged.
* **> 1 rows** → `BLOCKED`, `SCHEDULER_OWNERSHIP_DUPLICATE:{job_id}`. Fails closed.
* **1 row** → exact-identity gate, all required:
  * `ownership_contract_version == 'V2_STAGE_SCOPED'`
  * `work_scope == 'WINDOW_LIFECYCLE'`
  * `campaign_id`, `run_id`, `cycle_id`, `factory_run_id` equal `context`
  * `token_slot_id` equals the close-boundary slot
  * `window_id` equals the R1-resolved window id
  * `target_category == 'CAMPAIGN_WINDOW'` and `target_identity == window_id`

  All hold → `VERIFIED` (project nothing). Any mismatch → `BLOCKED`,
  `SCHEDULER_OWNERSHIP_CONFLICT:{job_id}:{first_failing_field}`.

`stage_id` is deliberately **not** evaluated here; stage acceptance stays the sole
responsibility of R3 inside `_load_terminal_scheduler_correspondence`, so a
canonical owner with an unapproved stage still fails the correspondence gate.

### Result surface

* `projected_scheduler_jobs` keeps its exact current meaning: jobs this closeout
  projected. Unchanged for legacy runs; empty in the proof-owned shape.
* New sibling `verified_scheduler_jobs`: jobs whose pre-existing canonical owner
  was verified. Additive only; no existing consumer reads either key
  (`projected_scheduler_jobs` has no consumer in `src/` or `tests/`).

### Failure behavior

One-job-one-owner is strengthened, never weakened: the closeout no longer
*requests* a second owner, and a conflicting or duplicate owner is an explicit
fail-closed block rather than an exception string.

---

## 5. R3 — Proof-root correspondence

### Algorithm

1. `_load_terminal_scheduler_correspondence` gains one keyword:
   `proof_root_stage_step_ids: Sequence[int] | None = None`, normalized to a
   frozenset of ints (empty when `None`).
2. The single lineage call becomes per-step-identity:

   ```python
   _terminal_stage_matches(
       window_kind=window_kind,
       stage_id=str(owned["stage_id"] or ""),
       allow_proof_root_stage=(
           factory_step_ids is not None
           or int(step["id"]) in proof_root_stage_step_id_set
       ),
   )
   ```

   `_terminal_stage_matches` itself is **unchanged**. Ordinary `WINDOW_15M`
   (`WINDOW_15M_SLOT_1/2` and the `|WINDOW_15M_SLOT_n|` campaign-stage suffixes)
   and the exact `WINDOW_1H` / `WINDOW_4H` rules are untouched — those branches
   return before the flag is consulted.
3. `finalize_full_run_ownership_and_report` gains
   `four_token_proof_owned: bool = False`. When true — and only then — it resolves
   the exact proof-owned step identities through the **already-approved** owner
   `four_token_proof_integration.cycle_scoped_factory_step_ids(connection,
   campaign_id, campaign_run_id, factory_run_id, cycle_id)` and passes them as
   `proof_root_stage_step_ids`. A resolver fault (ambiguous Scheduler ownership)
   propagates as a closeout block — it is never swallowed.
4. `operational_memory_factory_command._apply_full_run_campaign_acceptance` gains
   the same keyword and forwards it; `_run_operational_campaign` supplies
   `four_token_proof_owned=four_token_proof_controller is not None`.

### Failure behavior

Bare `stage_id='WINDOW_15M'` is accepted only for a step id that the canonical
proof-cycle owner itself resolves, inside a run whose four-token proof controller
is active. Every other step — ordinary run, standard-4h, or a step outside the
proof-owned set — retains the strict slot-stage requirement. Acceptance is never
globally broadened.

### Compatibility

`proof_root_stage_step_ids=None` on every ordinary and standard-4h path ⇒
identical behavior; the existing `factory_step_ids` cycle-scoped callers
(`four_token_factory_adapter`, `one_command_15m_factory`) are untouched.

---

## 6. R4 — Child-terminal fidelity

### Algorithm

`window_15m_child_terminal.py` requires **no change**. Its allow-list already
carries every field, and `_find_key` already resolves each at the top level of
the source mapping. The repair is a truthful projection at the four-token result
boundary — `operational_memory_factory_command._run_operational_campaign`, the
`terminal` dict (`:4094-4129`), which is both the printed/summary result and the
`source=` argument of `write_child_terminal_envelope`. Keeping one surface avoids
any divergence between the operator summary and the child terminal.

Fields added, each from an authoritative in-scope owner:

| Field | Authoritative source |
|---|---|
| `cycle_id` | coordinator-local `cycle_id` |
| `supervision_id` | `command.supervision_id` |
| `lifecycle_started` | `bool(result.lifecycle_started)` |
| `cleanup_complete` | `cleanup["cleanup_completed"] is True` (durable cleanup owner) |
| `lease_released` | `cleanup["lease_released"] is True` (durable cleanup owner) |
| `active_locked_work` | `{"active_owned_work_after": int(cleanup["active_owned_work_after"])}` when present and integral, else `None` |
| `database_identity_after` | `action_local_terminal_truth.capture_database_identity(command.db_path)` — read-only `stat` + `sha256` |
| `source_calls` | `report["campaign_source_calls"]` (campaign total already embedded in the persisted report) |
| `scheduler_runtime_calls` | `len(scheduler_runtime_records)` — the Central Scheduler runtime operations observed by the existing observer |
| `terminal_report_path` | `report["artifact_path"]` from `write_campaign_terminal_report` |

`terminal_report_sha256` is **not** projected: the child terminal already derives
it by hashing the file at `terminal_report_path`
(`window_15m_child_terminal.py:371-375`), and that derivation is the stronger
evidence.

`database_writes` is **not** projected. No authoritative scalar write count
exists at the success boundary; inventing one is forbidden. It stays `None`.

### Preserved locks (explicit)

* Schema field allow-list: unchanged set; no field added or removed.
* 64 KiB bound: unchanged; the added fields are ≈400 bytes.
* Redaction / unsafe-text rules: unchanged. Every added value passes through the
  existing `_safe_text` / `_safe_identifier` / `_bounded_mapping` /
  `_database_identity` filters.
* Create-once, read-only terminal (`open("xb")` + `chmod 0o444`): unchanged.
* `success == process exit disposition`: unchanged; the
  `success is not (exit_code == 0)` guard is untouched.
* `CHILD_EXITED_ZERO` is **not** proof PASS: no proof verdict, campaign verdict,
  or acceptance field is added to the envelope. The child terminal continues to
  report only process disposition plus truthful operational facts.

### Compatibility

The `terminal` dict is shared by `run`, `standard-four-hour-run`, and
`four-token-bounded-capacity-proof-run`. All three gain the same truthful fields
under the same schema. Existing keys keep their values and meaning; the addition
is purely additive.

---

## 7. Exact files

### Production (3)

| File | Change |
|---|---|
| `src/printer_v1/operator_cli/campaign_full_run_accounting.py` | R1 helper + call site; R2 helper + call site; R3 `proof_root_stage_step_ids` keyword, per-step allowance, `four_token_proof_owned` keyword and proof-owned step resolution; `verified_scheduler_jobs` result key |
| `src/printer_v1/operator_cli/operational_memory_factory_command.py` | R3 `four_token_proof_owned` thread-through (`_apply_full_run_campaign_acceptance`, `_run_operational_campaign`); R4 truthful projection into the `terminal` result |
| `src/printer_v1/operator_cli/window_15m_child_terminal.py` | **no change** (recorded as the proven-unnecessary outcome for R4) |

`operational_memory_factory_command.py` is narrowly required and proven so: it is
the only site that knows the run is proof-owned (R3) and the only site that owns
the terminal result mapping (R4).

### Explicitly not modified

Tracking, discovery, provider/source transports, `campaign_ownership.py`
(Scheduler-owner authority), `one_command_15m_factory.py`,
`operational_selective_1h.py`, `four_token_proof_integration.py`, the Central
Scheduler, the Source Governor, migrations, and schema. If implementation shows
any of these must change, the lane **BLOCKS**.

### Tests (1 new, 3 reused)

| File | Role |
|---|---|
| `tests/test_v2_9_8b_post_four_token_proof_blocker_repair.py` (new) | focused R1/R2/R3/R4 contracts, negative controls, fixture A, fixture B |
| `tests/test_v2_9_8b_standard_4h_close_accounting_repair.py` | standard-4h + ordinary-15m correspondence compatibility, one-job-one-owner |
| `tests/test_v2_9_8b_full_run_wiring_integration.py` | legacy non-precreated window + legacy projection end-to-end compatibility |
| `tests/test_v2_9_8b_window_15m_child_terminal_propagation.py` | child-terminal schema / bound / redaction / create-once locks |

---

## 8. Disposable offline fixtures

Both are in-memory / temp-dir only. No network, no provider, no authoritative DB
write, no authorization, no marker, no live Printer child.

### Fixture A — CONSUMED-SHAPE NEGATIVE CONTROL

Shape (mirrors the consumed proof exactly): one cycle, two tokens, canonical `cw:`
`WINDOW_15M` windows bound to their exact memory rows, canonical
`V2_STAGE_SCOPED` / `WINDOW_LIFECYCLE` Scheduler owners with
`stage_id='WINDOW_15M'` and `work_state='SUCCEEDED'`, 16 `SNAPSHOT` + 2
`WINDOW_CLOSE` steps, no `WINDOW_1H`/`WINDOW_4H` evidence,
`run_status=SAFE_STOPPED`, `first_terminal_cause=TERMINAL_TRACKING_STATE`,
campaign disposition `MANUAL_REVIEW`.

**After repair it must show:**
* no `WINDOW_NOT_REGISTERED_AT_CLOSE_BOUNDARY:*`
* no `SCHEDULER_PROJECTION_FAILED:*`, no `SCHEDULER_OWNERSHIP_CONFLICT:*`,
  no `SCHEDULER_OWNERSHIP_DUPLICATE:*`
* `registered_windows` == the two canonical `cw:` ids
* `verified_scheduler_jobs` == all 18 job ids; `projected_scheduler_jobs` == `[]`
* `scheduler_ownership.correspondence_exact is True`,
  `lineage_mismatch_job_ids == []`, `missing_ownership == []`,
  `extra_ownership == []`

**And it must still FAIL the four-token proof**, asserted positively:
* only 2 tokens and 1 cycle against the required 4 tokens / 2 cycles
* zero `WINDOW_4H` (and zero `WINDOW_1H`) through-4h evidence
* the honest campaign-acceptance failures survive untouched
  (`runtime_terminal_completed`, `mandatory_stage_statuses_completed`,
  `persisted_slot_dispositions_exact` all remain `False`), so the verdict is not
  `PASS`.

This fixture is the primary guard that the repair removes only *false* blockers.

### Fixture B — SYNTHETIC SUCCESS-SHAPED ACCOUNTING FIXTURE

**This is not the four-token proof and is never described as one.** It proves one
thing only: that correct ownership / window / stage / evidence is *recognised*.

Shape: canonical `cw:` window, exact canonical owner, proof-owned step ids
threaded, jobs `SUCCEEDED`. Asserts `correspondence_exact is True`,
disposition `VERIFIED` for every job, and the R1 authority resolving to the
canonical `cw:` id with a clean block list. It asserts nothing about proof
capacity, four-token completeness, or campaign PASS.

---

## 9. Minimum verification (risk-based; no full-suite expansion)

1. Focused **R1** tests: canonical authority resolution; legacy fallback;
   duplicate → `CAMPAIGN_WINDOW_IDENTITY_AMBIGUOUS`; wrong token/pair →
   `CAMPAIGN_WINDOW_IDENTITY_MISMATCH`; wrong/NULL memory binding →
   `WINDOW_NOT_REGISTERED_AT_CLOSE_BOUNDARY`; missing row → unchanged legacy block.
2. Focused **R2** tests: unowned → `PROJECT`; exact canonical owner → `VERIFIED`;
   foreign campaign/run/cycle/factory-run/slot/window/scope/target/contract-version
   → `BLOCKED` conflict (one case per field); two owners → `BLOCKED` duplicate.
3. Focused **R3** tests: bare `WINDOW_15M` accepted **only** for a threaded
   proof-owned step id; the same row rejected when the id is absent from the set;
   a second 15m step not in the set still rejected in the same call; `WINDOW_1H`
   and `WINDOW_4H` acceptance unchanged with and without the set.
4. Focused **R4** tests: envelope built from a proof-shaped terminal result
   carries each of the ten truthful fields; `database_writes` stays `None`;
   `terminal_report_sha256` is derived from the file; `success=True` with a
   non-PASS campaign verdict still yields no proof-PASS signal; envelope passes
   `read_child_terminal_envelope` unchanged; size under 64 KiB.
5. Fixture A (consumed-shape negative control) — assertions of §8.
6. Fixture B (synthetic success-shaped) — assertions of §8.
7. Ordinary-run compatibility:
   `tests/test_v2_9_8b_standard_4h_close_accounting_repair.py`.
8. Standard-4h compatibility: same file (15m+1h+4h exact lineage; no expansion to
   long work when `standard_four_hour_campaign=False`).
9. Legacy non-precreated window compatibility:
   `tests/test_v2_9_8b_full_run_wiring_integration.py` (registers two legacy
   windows, projects jobs, reconciles).
10. One-job-one-owner negative controls: R2 duplicate/conflict cases plus the
    existing `extra_ownership` rejection test.
11. Child-terminal lock compatibility:
    `tests/test_v2_9_8b_window_15m_child_terminal_propagation.py`.
12. `python -m compileall` on every changed module.
13. `git diff --check`.
14. Changed-file manifest (`git diff --stat`) reviewed against §7.
15. Restricted-surface scan of the diff for: migrations/schema, provider/source
    transports, tracking/cooldown/requalification, liquidity/exact-pair, Source
    Governor, Central Scheduler, capability unlock, retry/rerun/resume/restart/
    successor, authorization/marker creation, proof capacity constants, V2-10.

### Required invariants (must all hold)

1. Consumed-shape fixture remains BLOCKED for honest proof reasons.
2. R1/R2/R3 false blockers disappear.
3. Genuine ownership / window / stage mismatches still block.
4. Child terminal exposes available truth without turning process success into
   proof success.
5. No Source Governor / Central Scheduler bypass.
6. No capability unlock.
7. No migration / schema / provider change.

---

## 10. Preserved locks (unchanged by this lane)

Tracking reuse rules · `TERMINAL_TRACKING_STATE` · `DUPLICATE_ACTIVE_TRACKING` ·
cooldown/requalification · liquidity floor and exact-pair rules · market scarcity
behavior · Source Governor · Central Scheduler authority · one-job-one-owner ·
single durable cycle-2 opportunity · 2400s pre-lifecycle acquisition semantics ·
retries/reruns/resumes/restarts/successors · proof capacity (4 tokens / 2 cycles /
2 per cycle) · providers · migrations and schema · financial and retrieval locks ·
the consumed four-token proof evidence.

---

## 11. Closeout meaning

A PASS on this repair lane does **not** authorize another proof. It makes a fresh
four-token authorization *eligible for a separate authorization-readiness lane*.
V2-10 remains locked.

Design verdict target:
`V2_9_8B_POST_FOUR_TOKEN_PROOF_BLOCKER_REPAIR_DESIGN_PASS_READY_FOR_IMPLEMENTATION`
