# Printer V1 — Standard-4H Budget + Cycle-2 Refresh Re-entry Joint Repair Design

Status: **CLOSED PASS as design / specification only**

Lane:

`SEP-3 4/2/2 STANDARD-4H BUDGET + CYCLE-2 REFRESH-REENTRY REPAIR — JOINT DESIGN / SPECIFICATION`

This document specifies two independently audited Sep-3 repairs. It does not
implement either repair. It does not modify `src/`, tests, or migrations. It
does not mutate the authoritative DB. It does not run Printer, contact
providers/RPC/WebSockets, run Central Scheduler, or prepare/apply an
authorization.

The two slices remain independently specified. One slice's PASS does not hide a
blocker in the other.

---

## 1. Baseline

| Item | Value |
|---|---|
| Branch | `assistant/v2-9-8b-later-cycle-mint-market-replay-repair` |
| Design baseline HEAD | `3ceaeb256322778629b6fc024f678bf5bcbcb61e` |
| Authorized Sep-3 execution HEAD | `26d7b91bb5f115ad816b3cd632b5036d07b82b0e` |
| Production-code drift since execution HEAD | **none** (`git diff --stat 26d7b91b..HEAD -- src tests migrations` empty) |
| Authoritative DB | `data/printer_v1.sqlite3` |
| Authoritative DB SHA-256 | `575984caa484b12f4bb5fca0a06cdf7865adeb03b5f16874406fb0c1a73daa6e` |
| Consumed authorization | `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260903T121923Z_202fbea1` permanently non-reusable |
| Future prior-non-reuse root | 60 IDs, including this consumed ID |

`3ceaeb25...` is the **design baseline**, not a later implementation binding.
Committing this design changes HEAD. The later implementation lane must bind
the **actual final committed design HEAD** via live `git rev-parse HEAD`.

Governing closed audits (diagnosis not reopened):

- Budget:
  `docs/printer-v1-v2-9-8b-four-token-standard4h-per-token-request-ceiling-wiring-repair-audit.md`
  verdict `V2_9_8B_FOUR_TOKEN_STANDARD4H_PER_TOKEN_REQUEST_CEILING_WIRING_REPAIR_READINESS_AUDIT_PASS`
- Cycle-2:
  `docs/printer-v1-v2-9-8b-sep3-cycle2-duplicate-transport-no-pair-blocker-audit.md`
  verdict `V2_9_8B_SEP3_CYCLE2_DUPLICATE_TRANSPORT_NO_PAIR_BLOCKER_AUDIT_PASS`

Independence from the audits is preserved:

```text
BUDGET_DEFECT_NOT_INVOLVED          (Cycle-2 terminal at 13:01Z; budget stop at 13:44Z)
CYCLE2_FINDING_INDEPENDENT          (duplicate-transport owners do not share the per-token selector)
```

Approved 4/2/2 envelope, unchanged by this design:

```text
outer lifecycle ceiling = 476
per-token lifecycle ceiling = 118
Scheduler ceiling = 444
retries = 0
endpoint rotation = false
refresh timing = +600 / +1200 / +1800 / deadline +2400
```

Permanent V1 locks remain unchanged. Source Governor remains the sole
source-request owner. Central Scheduler remains the sole scheduling owner.

---

## 2. Two independent audited defects

### Repair A — four-token Standard-4H per-token budget wiring

Diagnosis is closed. Do not reopen it.

```text
four_token_proof
-> outer selector correctly chooses 476

but

continuous_first_hour
-> _CONTINUOUS_MAX_REQUESTS_PER_TOKEN
-> 50
-> _enforce_budgets_before_step
```

Sep-3 stopped at token count `51` on `CONTINUATION_CLOSE_CONTEXT`
(projected `0`) although `51 < 118`. Outer run ceiling `476` and Scheduler
ceiling `444` were already selected correctly.

Defective consumer:

`one_command_15m_factory._enforce_budgets_before_step` pre-4h branch.

Missing helper:

`_token_ceiling_for_run_config`

Stale value source:

`_CONTINUOUS_MAX_REQUESTS_PER_TOKEN = 50`

Approved value source:

`scaled_standard_four_hour_capacity_contract(4)["lifecycle_requests_per_token"]`
= `118`

### Repair B — Cycle-2 Pump live-tail refresh re-entry

Diagnosis is closed. Do not reopen it.

Primary classification: `NEW_NARROW_REFRESH_REENTRY_DEFECT`

Historical mint-batch repair disposition: `REPAIR_REACHED_BUT_SCOPE_GAP`

Sep-3 collision:

```text
Cycle-2 initial request 4724:
Pump getSignaturesForAddress
target = withdraw-authority | before=HEAD

Cycle-2 refresh-1 request 4756:
same RPC
same target
same canonical transport identity
same byte-identical empty response

request keys differed
canonical transport identity did not
```

`CampaignSixUnitOwner` correctly rejected `DUPLICATE_TRANSPORT_IDENTITY`.
Do not weaken that guard.

The producer re-issued an already-sealed Cycle-2 `before=HEAD` page because
refresh composition always calls `run_direct_migration_discovery` with a new
refresh request-key prefix. DexScreener / GeckoTerminal already skip by
exact refresh request-key checkpoint; Pump has no equivalent
already-completed canonical-identity skip.

---

## 3. Budget Repair A contract

### 3.1 Canonical numeric owner

Do **not** hard-code `118`.

Use the same contract getter already used by `_request_ceiling_for_run_config`
and `_scheduler_ceiling_for_run_config`:

```python
scaled_standard_four_hour_capacity_contract(4)["lifecycle_requests_per_token"]
```

That getter returns the unscaled per-token share `118` (it does not double
the per-token figure). The same `118` is already bound by
`exact_operational_policy()`, `FOUR_TOKEN_STANDARD_FOUR_HOUR_POLICY`, the
authorization validator, and the frozen Sep-3 operational policy.

### 3.2 New mode-aware helper

Add `_token_ceiling_for_run_config(config)` in
`src/printer_v1/operator_cli/one_command_15m_factory.py`, immediately beside
`_request_ceiling_for_run_config`.

Required semantics:

```python
def _token_ceiling_for_run_config(config: Mapping[str, Any]) -> int:
    if bool(config.get("four_token_proof")):
        from printer_v1.operator_cli.multi_cycle_memory_growth import (
            scaled_standard_four_hour_capacity_contract,
        )
        return int(
            scaled_standard_four_hour_capacity_contract(4)[
                "lifecycle_requests_per_token"
            ]
        )
    if bool(config.get("continuous_first_hour")):
        return _CONTINUOUS_MAX_REQUESTS_PER_TOKEN  # 50
    return _MAX_GOVERNED_REQUESTS_PER_TOKEN  # 22
```

Do not add extra branches. Selective-1h already sets `continuous_first_hour`
and `_SELECTIVE_1H_MAX_REQUESTS_PER_TOKEN` already equals
`_CONTINUOUS_MAX_REQUESTS_PER_TOKEN`. Compressed two-token and standalone
continuous-1h therefore remain `50` through the second branch.

Proof-only four-token shares `four_token_proof = true` and the same scaled
`118`. Including it is not a broadening.

Two-token Standard-4H (`four_token_proof` false, `continuous_first_hour`
true) remains `50`. That residual is **out of this repair**.

### 3.3 Live enforcement replacement

In `_enforce_budgets_before_step`, pre-4h branch only (the branch that is
not `LONG_CONTINUATION_*`), replace the inline selector:

```python
token_ceiling = (
    _CONTINUOUS_MAX_REQUESTS_PER_TOKEN
    if continuous else _MAX_GOVERNED_REQUESTS_PER_TOKEN
)
```

with:

```python
token_ceiling = _token_ceiling_for_run_config(config)
```

Keep the existing comparison and stop:

```text
if current + projected > ceiling: _GlobalStop(STOP_BUDGET, scope="CUMULATIVE_LIFECYCLE")
```

Exactly at the ceiling remains lawful. Overshoot remains a global integrity
safe-stop. Do not convert a genuine per-token `118` exhaustion into
`TOKEN_LOCAL_*`.

Classification preserved:

`GLOBAL_STOP_SEMANTICS_ALREADY_CORRECT`

### 3.4 Constants that must not change

Do not mutate:

- `_CONTINUOUS_MAX_REQUESTS_PER_TOKEN = 50`
- `_SELECTIVE_1H_MAX_REQUESTS_PER_TOKEN = 50`
- `_MAX_GOVERNED_REQUESTS_PER_TOKEN = 22`
- outer four-token `476`
- Scheduler `444`
- retries `0`
- endpoint rotation `false`
- `_GlobalStop` semantics
- `_request_ceiling_for_run_config`
- `_scheduler_ceiling_for_run_config`

### 3.5 Caller propagation — one canonical selector

Production callers of `_enforce_budgets_before_step`:

| Caller | Role after this repair |
|---|---|
| factory loop after Scheduler claim | live enforcement uses four-token `118` |
| `authoritative_admission_health.project_lifecycle_budget_reserve` | inherits the same helper; no admission-health-specific workaround |

Do not add a second ceiling path inside `project_lifecycle_budget_reserve`.
That function already calls `_enforce_budgets_before_step`. Once the helper
exists, both naturally see four-token `118`.

### 3.6 Reporting classification

```text
REPORTING_CHANGE_NOT_REQUIRED
```

Proven from current production code:

1. Four-token Standard-4H sets `continuous_four_hour = true`, so `_run_budgets`
   takes the 4h reporting branch. For `standard_four_hour_campaign` that
   branch sets `governed_requests_per_token_ceiling = None` and does **not**
   apply the inline `50`.
2. The non-4h `_run_budgets` tail still inlines
   `_CONTINUOUS_MAX_REQUESTS_PER_TOKEN`. That tail is not a four-token
   behavioral consumer.
3. `governed_requests_per_token_ceiling` is assigned only inside
   `_run_budgets`. No other production file reads it.

Do not expand this repair into cosmetic reporting alignment.

---

## 4. Budget Repair A proof matrix

Focused deterministic tests only. Extend
`tests/test_v2_9_8b_standard4h_pre4h_request_ceiling_wiring.py`.
No live Standard-4H campaign. No authoritative DB mutation.

Keep existing proofs that four-token **run** ceiling is `476` and Scheduler
ceiling is `444`. Stop stubbing `_token_request_count = 0` for the new
per-token cases.

Required later proof:

| Mode | current | projected | ceiling | `current + projected > ceiling` | required result |
|---|---|---|---|---|---|
| four-token | 50 | 1 | 118 | false | allow |
| four-token | 51 | 0 | 118 | false | allow |
| four-token | 117 | 1 | 118 | false | allow |
| four-token | 118 | 0 | 118 | false | allow |
| four-token | 118 | 1 | 118 | true | `_GlobalStop` / `CUMULATIVE_LIFECYCLE` |
| four-token | 119 | 0 | 118 | true | `_GlobalStop` / `CUMULATIVE_LIFECYCLE` |
| selective-1h | 49 | 1 | 50 | false | allow |
| selective-1h | 50 | 1 | 50 | true | `_GlobalStop` |

Additional helper proofs:

- `_token_ceiling_for_run_config(_FOUR_TOKEN_STD4H)` equals
  `scaled_standard_four_hour_capacity_contract(4)["lifecycle_requests_per_token"]`
  and is not a copied literal `118`.
- selective-1h remains `_CONTINUOUS_MAX_REQUESTS_PER_TOKEN` (`50`).
- 15m-only (`continuous_first_hour` false, `four_token_proof` false) remains
  `_MAX_GOVERNED_REQUESTS_PER_TOKEN` (`22`).
- two-token Standard-4H (`four_token_proof` false) remains `50` (explicit
  non-repair).
- `_request_ceiling_for_run_config` four-token remains `476`.
- `_scheduler_ceiling_for_run_config` four-token remains `444`.
- `automatic_retries` remains `0`; endpoint rotation remains false.
- genuine `118` overshoot remains `_GlobalStop`, not token-local.

Use `CONTINUATION_SNAPSHOT` (projected `1` by default) and
`CONTINUATION_CLOSE_CONTEXT` (reserved operations `0`, so projected `0`) so
the Sep-3 `51 + 0` shape is represented without inventing a new projector.

---

## 5. Cycle-2 Repair B exact producer / checkpoint law

### 5.1 Required law

```text
If the current Cycle-2 accounting scope has already successfully completed and
sealed Pump live-tail transport:

address | before=HEAD

then a later persisted refresh/re-entry must not issue that exact same canonical
transport again merely because it has a new refresh request-key prefix.
```

The skip must operate **before the network request is emitted**. Do not issue
a duplicate and suppress `DUPLICATE_TRANSPORT_IDENTITY` afterward.

### 5.2 Selected owner

```text
REFRESH_COMPOSITION_SKIP_OWNER
```

Not `DIRECT_MIGRATION_PRODUCER_SKIP_OWNER`.
Not `BOTH_REQUIRED_FOR_CLEAN_OWNERSHIP`.

Placement:

`pre_lifecycle_refresh_composition.refresh_stage`, Pump branch of
`build_pre_lifecycle_refresh_stage`, **before** calling
`run_direct_migration_discovery`.

Why this owner, not the producer:

1. The defect is refresh re-entry, not first-time live-tail. Initial Cycle-2
   discovery must still issue the first `before=HEAD` page.
2. DexScreener / GeckoTerminal already skip at this same composition layer
   via `_cooperative_checkpointed_request`. Pump is the missing sibling skip,
   keyed by canonical identity rather than the current refresh request-key.
3. `run_direct_migration_discovery` is a shared producer (initial discovery,
   backfill, refresh, offline proofs). Putting a HEAD skip there would either
   suppress lawful first-time HEAD work or require a new caller flag, spreading
   ownership.
4. The producer already has same-request-key cooperative replay through
   `load_terminal_governed_execution_by_request_key`. That replay does **not**
   cover the Sep-3 collision, because refresh uses a different request key.
   Do not mix request-key replay with cross-prefix canonical-identity skip.

Do not duplicate skip logic in `direct_migration_discovery.py`.
That file is **not** an implementation file for this repair.

### 5.3 Existing durable evidence to reuse

No new table or schema.

Helper, new, narrow, and explicit — do **not** merge into
`load_completed_cooperative_mint_market_batch_mints`:

```text
cycle_pump_live_tail_head_already_completed(connection, *, request_key_root) -> bool
```

Live in `pre_lifecycle_refresh_composition.py` beside
`_cooperative_checkpointed_request`.

Minimum existing query, same pattern as the mint-batch helper:

```sql
SELECT r.request_key, s.normalized_payload_json
FROM printer_source_requests AS r
JOIN printer_source_responses AS s ON s.source_request_id = r.id
WHERE (r.request_key = ? OR r.request_key LIKE ?)
  AND r.source_name = 'solana_rpc'
  AND r.request_kind = 'restored_pump_migration_signature_page'
  AND s.source_status = 'COMPLETE'
  AND s.data_quality_label = 'CLEAN_DATA'
ORDER BY r.id ASC
```

Bind `(request_key_root, request_key_root || '%')`.

Then, for each row:

1. Keep only keys that pass `request_key_belongs_to_root(request_key, request_key_root)`.
   Do not trust the `LIKE` alone. Cycle-1 root `v2-9-8b-window15m-<execution>`
   is a string prefix of Cycle-2 `v2-9-8b-window15m-<execution>:c0002`, but
   `request_key_belongs_to_root` requires `key == root` or
   `key.startswith(root + "-")`. The Cycle-2 delimiter is `:c0002-`, so
   Cycle-1 lookup cannot suppress Cycle-2, and Cycle-2 lookup cannot suppress
   Cycle-1.
2. Parse `normalized_payload_json.transport_operation_identities`.
3. Project each identity through `canonical_transport_identity_key`.
4. Compare to the canonical HEAD key constructed from existing owners, not a
   copied address literal:

```text
(
  "DIRECT_PUMP_NOMINATION",
  "solana_rpc",
  "restored_pump_migration_signature_page",
  "getSignaturesForAddress",
  1,
  "pump_migration_withdraw_authority_page",
  direct_migration_signature_page_target_identity(
      indexed_address=DIRECT_MIGRATION_INDEXED_ADDRESS,
      cursor_before=None,
  )   # "{withdraw-authority}|before=HEAD"
)
```

Return `True` when at least one such completed identity exists.

Do **not** skip on:

- failures (`printer_source_failures` only);
- `PARTIAL` / non-`CLEAN_DATA` responses;
- malformed identities;
- a different `target_identity` such as `address|before=<signature>`;
- a foreign request-key root (other cycle, other campaign, other execution).

Lookup scope at minimum:

```text
same campaign / run / proposed Cycle 2 / acquisition attempt
via the already-bound refresh request_key_prefix
(cycle 1: execution_id root; cycle 2: execution_id:c0002 root)
same canonical Pump live-tail HEAD transport
successful COMPLETE + CLEAN_DATA evidence
```

`build_pre_lifecycle_refresh_stage` already captures that cycle-scoped
`request_key_prefix`. Cycle 1 is composed with `execution_id`. Cycle 2 is
rebound with the later-cycle request-key prefix (the `:c0002` root). Do not
add `execution_id` / typed `CampaignSourceRequestScope` to the refresh
builder unless implementation proves the prefix is insufficient. Current
production wiring already supplies the narrowest durable root.

Do not query a new six-unit table. Six-unit evidence is in-memory plus sealed
stage payloads; Source Governor rows are the durable completed-transport
authority, matching the mint-batch repair.

### 5.4 Pump-branch control flow

In the `channel == PUMP_FRESH_CHANNEL` branch, after the existing transport-
configured and worst-case-budget checks, and **before**
`channels_attempted.append` / `run_direct_migration_discovery`:

```text
if cycle_pump_live_tail_head_already_completed(
    connection, request_key_root=request_key_prefix
):
    channels_skipped.append({
        "channel": channel,
        "reason": "CANONICAL_PUMP_LIVE_TAIL_HEAD_ALREADY_COMPLETED",
    })
    stage_reports[channel] = {
        "status": "CANONICAL_TRANSPORT_ALREADY_COMPLETED",
        "source_requests": 0,
        "target_identity": "<canonical HEAD identity>",
    }
    continue
```

Invariants for that skip:

- no Source Governor request;
- no `stage_evidence_sink` emission;
- not `channels_attempted` (this is unperformed work, not a checkpoint replay
  of this ordinal's request-key);
- not `channels_unavailable` (not a provider failure);
- `provider_failures` unchanged;
- `source_operations` unchanged (`0` added);
- do **not** set `cooperative_incomplete`.

Do not reuse `COOPERATIVE_CHECKPOINT_REPLAY`. That status means the **same
refresh request-key** already checkpointed. Sep-3 is a different request-key
and a prior opportunity's canonical identity.

### 5.5 Cycle-2 later proof matrix

Focused deterministic proofs in
`tests/test_v2_9_8b_cycle2_pump_live_tail_refresh_reentry_repair.py`.
Disposable SQLite only. No live providers. No Printer run.

#### Exact Sep-3 replay

Persist a completed Cycle-2 Pump live-tail:

```text
address|before=HEAD
response signatures=[]
COMPLETE + CLEAN_DATA
request_key under the Cycle-2 request_key_prefix
  (initial form `{root}-migration-page-live-tail`)
```

Then enter refresh ordinal 1 with `cooperative_yield=True` and a transport
that fails the test if called.

Require:

- same canonical transport network invocation count remains 1;
- no second Source Governor request for that exact transport;
- `run_direct_migration_discovery` is not called;
- no duplicate stage evidence;
- no `DUPLICATE_TRANSPORT_IDENTITY`;
- original source request/response rows preserved;
- Pump recorded in `channels_skipped` with
  `CANONICAL_PUMP_LIVE_TAIL_HEAD_ALREADY_COMPLETED`;
- stage returns without `cooperative_incomplete`;
- refresh owner path would therefore be `REFRESH_COMPLETED`, not
  `INTERNAL_INVARIANT`.

#### Re-entry idempotence

Re-enter the same refresh checkpoint / ordinal again against the same
completed HEAD evidence. Require no duplicate request and no duplicate
stage evidence.

#### Genuine cursor advancement

Persist the completed HEAD identity, then present a different lawful
canonical identity `address|before=<real-signature>`. The HEAD skip must
not suppress that different transport. Implementation may prove this at
the helper: `cycle_pump_live_tail_head_already_completed` is true for HEAD
and false for a payload whose identity uses a real `before=<signature>`.
Do not invent a cursor inside refresh composition.

#### Other fresh work

Non-cooperative ordinal 1: Pump skip must not prevent DexScreener /
GeckoTerminal in the same stage (existing `continue` law).

Cooperative ordinal 1: Pump skip completes that ordinal; a subsequent
ordinal 2 stage must still select DexScreener first under
`_rotated_fresh_channels(2)`.

#### Cycle / campaign isolation

- Completed HEAD under a Cycle-1 root must not make the Cycle-2 helper
  return true.
- Completed HEAD under a foreign campaign / execution root must not
  suppress the current root.
- Same identity in a different lawful ownership scope remains eligible
  according to existing six-unit / source ownership law.

#### Strict guard

Bypass the skip and inject a genuine second identical canonical identity
into `CampaignSixUnitOwner`. Require `DUPLICATE_TRANSPORT_IDENTITY` still
fires. The detector is unchanged.

#### Mint-batch non-regression

Do not modify
`tests/test_v2_9_8b_later_cycle_mint_market_replay_repair.py` except if a
one-line import collision appears. The mint-batch helper must continue to
protect cooperative `MARKET_DISCOVERY` resume.

---

## 6. Pump HEAD / cursor semantics

This case matters and is the Sep-3 payload:

```text
getSignaturesForAddress
before=HEAD
response signatures=[]
```

There is no protocol cursor to advance. `run_direct_migration_discovery` in
`LIVE_TAIL_MODE` keeps `cursor_before = None` and only
`touch_direct_migration_cursor_live_tail` (timestamp, no position move).
Polling `before=HEAD` again is the same canonical transport, not new work.

Required:

```text
already completed empty HEAD page
-> do not replay identical HEAD transport during persisted re-entry
```

The skip is identity-based, not emptiness-based. A completed non-empty HEAD
page is still `address|before=HEAD` and must also be skipped. Emptiness does
not create a new transport.

Do **not** invent a fake cursor to force uniqueness.

A later real protocol cursor remains lawful because it is a different
canonical identity:

```text
address|before=<different-signature>
```

Refresh composition currently calls the producer in default `LIVE_TAIL_MODE`.
This design does **not** convert refresh Pump work into `BACKFILL_MODE`.
If a future approved lane introduces a real live-tail cursor, that page is a
different transport and this skip will not match it.

`canonical_transport_identity_key` stays the seven-field key. Do not add
request id, Scheduler job id, refresh ordinal, stage sequence, or nonce.

---

## 7. Refresh opportunity continuation semantics

Preserve:

```text
+600 / +1200 / +1800 / deadline +2400
```

Skipping an already-satisfied Pump transport must **not** mean skip the entire
refresh opportunity, and must **not** invent new channel-rotation or timing
policy.

### 7.1 Existing cooperative production law (4/2/2)

`PreLifecycleTemporalRefreshOwner.for_cycle(..., cooperative_yield=True)`
causes:

```python
selected_channels = rotated_channels[:1]
```

Ordinal 1 first channel is Pump. Existing law then:

- runs only that first channel in the claim;
- sets `conversion_allowed = False` when the selected tuple is exactly Pump,
  so unknown-liquidity backup and protocol confirmation do not run in that
  claim;
- if `source_operations > 0`, yields `cooperative_incomplete` for the **same**
  ordinal;
- if `source_operations == 0` after the Pump branch (already true today for
  `MIGRATION_TRANSPORT_NOT_CONFIGURED` and
  `INSUFFICIENT_WORST_CASE_SOURCE_BUDGET`), does **not** set
  `cooperative_incomplete` and returns a completed stage;
- the refresh owner terminalizes that wait as `REFRESH_COMPLETED` with `0`
  new source operations;
- the acquisition loop treats `REFRESH_COMPLETED` as lawful continuation and
  may enqueue the next ordinal under existing `refresh_opportunity_at`.

The already-completed HEAD skip must use that **existing** 0-ops skip path
(`channels_skipped` + `continue`). It must not:

- expand `selected_channels` under cooperative yield so DexScreener runs in
  the same Pump-first claim (new intra-claim rotation);
- set `cooperative_incomplete` on a 0-ops skip (that would re-enter the same
  Pump-first ordinal and loop);
- map the skip to `INTERNAL_INVARIANT` / `NO_PAIR`.

Later ordinals remain the existing rotation:

| Ordinal | First rotated channel |
|---|---|
| 1 | Pump |
| 2 | DexScreener |
| 3 | GeckoTerminal |

So a Pump-first cooperative skip completes ordinal 1 honestly, and ordinal 2
(+1200) still starts on DexScreener. That is existing opportunity law, not a
new timing policy.

### 7.2 Existing non-cooperative stage law

When `cooperative_yield` is false, `selected_channels` is the full rotation.
Existing `continue` after a Pump skip already proceeds to DexScreener and
GeckoTerminal in the same stage
(`test_low_remaining_budget_skips_pump_but_keeps_peer_sources`). The HEAD
skip must keep that `continue` so peer fresh work remains available.

### 7.3 Selected continuation disposition

```text
cooperative 4/2/2:
  skip Pump HEAD, complete this ordinal without a new Pump request,
  leave +1200 / +1800 / deadline on the existing rotation

non-cooperative full stage:
  skip Pump HEAD and continue the existing rotated-channel loop
```

Do not invent a third rotation policy.

---

## 8. Duplicate-guard preservation

```text
request key != canonical transport identity
```

A new request key such as
`...refresh-1-pump-migration-page-live-tail` does not make the same protocol
transport new.

Do **not** modify `canonical_transport_identity_key` by adding request /
job / refresh / stage / nonce identity.

Do **not** change `CampaignSixUnitOwner`, `MeasuredTransportLedger`, or
`DUPLICATE_TRANSPORT_IDENTITY`.

The skip prevents the producer from creating the second genuine transport.
The detector remains fail-closed for any genuine duplicate that still reaches
it (tests must inject one directly).

Historical Sep-1 helper
`load_completed_cooperative_mint_market_batch_mints` remains intact. It
protects cooperative `MARKET_DISCOVERY` resume from re-issuing completed
DexScreener `MINT_MARKET_BATCH` due-mints. Cycle-2 Pump HEAD is a separate
state class. Do not merge the two helpers into a generic dedupe abstraction.

---

## 9. NO_PAIR truth preservation

Sep-3 classification:

`NO_PAIR_FALSE_SHORTAGE_FROM_INTERNAL_FAILURE`

The duplicate fired on the first refresh while +1200 / +1800 / deadline
remained unused. Code already maps an internal refresh invariant to
`DISCOVERY_ARCHITECTURE_FALSE_SHORTAGE`, then to attempt `NO_PAIR`.

After this repair:

- an already-satisfied transport skip is **not** provider shortage;
- it is **not** `INTERNAL_INVARIANT`;
- it does **not** terminalize the attempt as `NO_PAIR`;
- later lawful acquisition opportunities remain available;
- true no-pair remains possible only after existing acquisition law
  establishes it truthfully (horizon exhausted, honest empty universe, or
  other current shortage owners).

Do not change the +2400 deadline.
Do not map it to factory `PROOF_DEADLINE`.
Do not convert the skip into `channels_unavailable` or a provider failure
fact, which would distort `_temporal_terminal_source_failure_facts`.

---

## 10. Exact implementation files

Smallest exact set. Additional production files require explicit
justification during implementation; any such need is a stop condition.

### Repair A

```text
src/printer_v1/operator_cli/one_command_15m_factory.py
tests/test_v2_9_8b_standard4h_pre4h_request_ceiling_wiring.py
```

### Repair B

```text
src/printer_v1/discovery/pre_lifecycle_refresh_composition.py
tests/test_v2_9_8b_cycle2_pump_live_tail_refresh_reentry_repair.py
```

The new Cycle-2 test file sits next to
`tests/test_v2_9_8b_later_cycle_mint_market_replay_repair.py` and must not
modify that mint-batch helper. Optionally extend
`tests/test_v2_9_8b_persistent_multisource_refresh.py` only if a non-cooperative
peer-channel continuation case is cheaper there than duplicating stage
fakes; that is a test-only choice, not a second production owner.

`src/printer_v1/discovery/direct_migration_discovery.py` is **not** required.

### Joint seam

```text
tests/test_v2_9_8b_standard4h_budget_and_cycle2_refresh_reentry_joint_seam.py
```

Test-only. No additional production file.

### Explicitly unchanged

- Source Governor core
- Central Scheduler
- `CampaignSixUnitOwner` / `DUPLICATE_TRANSPORT_IDENTITY`
- `canonical_transport_identity_key`
- `load_completed_cooperative_mint_market_batch_mints`
- migrations / schema
- wrapper / authorization profile / validator / `exact_operational_policy()`
- `_run_budgets` reporting
- `authoritative_admission_health.py` (inherits via the factory helper)

---

## 11. Joint seam proof

One focused deterministic coexistence proof. No live providers. No full 4h
runtime.

Scenario:

```text
Cycle-1 token has >50 governed lifecycle requests
while Cycle-2 refresh re-enters after prior Pump HEAD completion
```

Require:

- `_token_ceiling_for_run_config` / `_enforce_budgets_before_step` on
  four-token config with token current `51` and projected `0` allows
  (ceiling `118`, not `50`);
- Cycle-2 is not false-blocked by stale budget wiring in that same config;
- exact prior Pump HEAD is not reissued (network / Source Governor
  invocation count for that canonical identity remains 1);
- other lawful Cycle-2 acquisition work remains possible (DexScreener first
  channel on ordinal 2, or non-cooperative peer channel after the Pump skip);
- Source Governor remains sole source-request owner;
- Central Scheduler remains sole scheduling owner.

This is not a live 4/2/2 campaign and does not replace the two independent
proof verdicts.

---

## 12. Explicit exclusions

Do **not** include:

- two-token Standard-4H `102 / 50` residual;
- selective-1h catalog mismatch (`92 / 45` vs factory `102 / 50`);
- Cycle-2 timing changes;
- provider improvements;
- retry policy changes;
- endpoint rotation;
- request-budget increase (do not raise `118`; do not treat fallback extras
  as a reason to raise it);
- new ranking / scoring / confidence / weights;
- Source Governor redesign;
- Scheduler redesign;
- six-unit duplicate relaxation;
- schema / migrations;
- converting refresh Pump work into backfill;
- generic cross-stage dedupe abstraction;
- `WINDOW_12H` / `WINDOW_24H`;
- retrieval;
- BUY / SELL / HOLD;
- positions / trades / audits / PnL.

---

## 13. Risks / setbacks / efficiency blockers

- Two-token Standard-4H factory pre-4h path still uses `102 / 50` despite
  public policy `238 / 118`. Out of scope; do not silently widen Repair A.
- Selective-1h command policy currently prints `92 / 45` while factory
  constants are `102 / 50`. Unrelated catalog mismatch; do not “align” by
  changing `50`.
- `_run_budgets` non-4h reporting still inlines `50`. Four-token reporting
  currently takes the 4h branch with `token_ceiling = None`. Classified
  `REPORTING_CHANGE_NOT_REQUIRED`; revisit only if a later consumer is
  proven.
- Cooperative Pump-first skip completes ordinal 1 with 0 new requests. That
  is existing 0-ops law, not Dex-in-the-same-claim. If a later live run
  still looks “short” because ordinal 2 has not fired yet, that is remaining
  horizon, not a new defect.
- A failed (not COMPLETE/CLEAN_DATA) initial HEAD is not skipped. If such a
  failure nevertheless sealed the canonical identity into six-unit, a later
  refresh could still collide. That is not the Sep-3 case. Do not expand
  this repair to rewrite failure accounting.
- Consumed `...202fbea1` is permanently non-reusable. Future prior-non-reuse
  root is 60 IDs.
- Both independent implementations must PASS, plus the joint seam, before
  another live 4/2/2 authorization.

---

## 14. Implementation stop conditions

STOP without shipping, and return
`DESIGN_BLOCKED_BY_SCOPE_EXPANSION` from the implementation lane, if work
discovers a requirement for:

- schema change;
- Source Governor-core rewrite;
- Central Scheduler rewrite;
- duplicate-accounting relaxation;
- new timing policy;
- provider-budget increase;
- broad candidate-acquisition redesign;
- repair of unrelated two-token mode;
- change to permanent V1 locks;
- adding request/job/refresh identity to the canonical transport key;
- replacing or modifying
  `load_completed_cooperative_mint_market_batch_mints` except a proven
  shared extraction that does not change mint-batch behavior.

This design itself is **not** blocked. Inspection found existing owners for
both slices.

---

## 15. Verdicts

### Budget slice

`V2_9_8B_FOUR_TOKEN_STANDARD4H_PER_TOKEN_REQUEST_CEILING_WIRING_REPAIR_DESIGN_PASS`

Classification:

`NARROW_MODE_AWARE_TOKEN_CEILING_SELECTOR_DESIGN`

### Cycle-2 slice

`V2_9_8B_SEP3_CYCLE2_DUPLICATE_TRANSPORT_ACQUISITION_REPAIR_DESIGN_PASS`

Classification:

`NARROW_REFRESH_REENTRY_COMPLETED_TRANSPORT_SKIP_DESIGN`

Owner:

`REFRESH_COMPOSITION_SKIP_OWNER`

### Joint design

Both independent slices PASS.

`V2_9_8B_STANDARD4H_BUDGET_AND_CYCLE2_REFRESH_REENTRY_JOINT_REPAIR_DESIGN_PASS`

---

## 16. Exact next lane

```text
STANDARD-4H BUDGET + CYCLE-2 REFRESH-REENTRY JOINT REPAIR — IMPLEMENTATION + BOUNDED PROOF
```

That later implementation lane may implement both designs together. It must
preserve separate proof verdicts:

```text
BUDGET_REPAIR_PASS
CYCLE2_REFRESH_REENTRY_REPAIR_PASS
JOINT_SEAM_PASS
```

Do not begin implementation automatically.
Do not run Printer.
Do not prepare or apply another authorization.

Consumed `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260903T121923Z_202fbea1` remains
permanently non-reusable.

STOP.
