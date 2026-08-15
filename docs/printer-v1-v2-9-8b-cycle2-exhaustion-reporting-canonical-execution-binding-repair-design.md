# Printer V1 V2-9.8B Cycle-2 Exhaustion Reporting / Canonical Execution-Binding Repair Design

Date: 2026-08-15

Baseline: `d5afefab31861b8851b5feb8f799769ae16ad277`

Branch: `agent/v2-9-8b-cycle2-exhaustion-reporting-binding-repair`

Lane: `V2-9.8B — Active Bounded Memory Growth Operations`

Type: narrow repair design (design-only; no code changes in this document's commit)

## 1. Verdict

```text
V2_9_8B_CYCLE2_EXHAUSTION_REPORTING_CANONICAL_EXECUTION_BINDING_REPAIR_DESIGN_PASS
READY_FOR_NARROW_IMPLEMENTATION
```

Python Builder Guide §13.3 primary blocker classification:

```text
COMMITTED_CODE_DEFECT
```

Per §13.3: *"A reproducible mismatch exists between committed behavior and
official/Printer contracts."* Both manifestations below are reproducible from
committed source at their canonical owner. The §13.4 coding-recommendation gate
is therefore open, and the response is *"the smallest correction in the canonical
owner with focused regression proof."*

Authority classification of the violated contract: `PRINTER_BINDING` (Builder
Guide §1). The certificate/reporting contract is required by the active Printer
source stack, not by official Python/SQLite/pytest documentation. This is an
authority classification, not the blocker classification.

## 2. Established diagnosis (not reinterpreted)

This design consumes, and does not reopen, the two closed read-only lanes:

- `docs/printer-v1-v2-9-8b-four-token-eligible-candidate-supply-blocker-audit.md`
- `docs/printer-v1-v2-9-8b-cycle2-authoritative-exhaustion-certificate-reconciliation.md`
  (verdict
  `V2_9_8B_CYCLE2_AUTHORITATIVE_EXHAUSTION_CERTIFICATE_RECONCILIATION_CERTIFICATE_VALID_REPORTING_CONTRACT_VIOLATED`)

Facts carried forward unchanged:

- The Cycle-2 exhaustion certificate exists, is valid, and satisfies
  `HONEST_EXHAUSTION`.
- The persisted shortage classification is `TRACKING_STATE_CAPACITY_BLOCKED`.
- That classification is **correct** under the committed precedence rule in
  `eligible_token_supply._apply_permanent_shortage_precedence`.
- The tracking-state exclusion behaviour is **not** claimed to be defective here.
- The 10 `PERSISTED_GRADUATED` / `LIQUIDITY_PROVEN` reserve rows observed as
  `EXCLUDED` / `REMOVED` are **out of scope**; they belong to the separate
  follow-on read-only audit lane.
- The defects are in the *ownership binding* and *evidence propagation* around
  that correct classification.

## 3. Defect manifestations

### 3.1 Canonical execution-binding defect

`src/printer_v1/operator_cli/later_cycle_graduated_supply.py`
(`build_later_cycle_graduated_supply`) passes the later-cycle **selection seed**
where the canonical **execution identity** is required, in two places:

```python
scope = build_campaign_source_request_scope(
    execution_id=selection_seed,        # line 105
    ...
)
kwargs.update({
    ...
    "execution_id": selection_seed,     # line 116
    ...
})
```

The later-cycle selection seed is constructed in
`one_command_15m_factory._run_four_token_admission_boundary` (lines 193-196) as:

```python
selection_seed=(
    f"{binding.authoritative_factory_run_id}:"
    f"{binding.campaign_run_id}:c0002"
)
```

`eligible_token_supply` derives both the certificate identity and the certificate
ownership column from that value (lines 2026-2032):

```python
certificate_id=(f"exh-{execution_id or campaign_id or uuid.uuid4().hex[:12]}"),
campaign_id=campaign_id,
execution_id=execution_id,
```

Observed consequence: the persisted Cycle-2 certificate carries
`execution_id = 9296ffff-7e71-46d2-8e63-dd7b755780c9:20260815T194831Z-6d09a756e8d1-campaign-run:c0002`
instead of the canonical execution id `20260815T194831Z-6d09a756e8d1`. All 11
earlier certificates use canonical execution ids, so a canonical-execution-id
lookup returns **zero rows** for Cycle-2. Campaign/run/cycle bindings are correct
and unaffected.

### 3.2 Blocked diagnostic-propagation defect

`graduated_supply_front_door.build_graduated_supply` assembles the complete
evidence into `GraduatedSupply.diagnostics` (lines 1031-1054): the
`exhaustion_certificate` dict, `shortage_classification`, `discovery_rounds`,
plus the inherited persistent diagnostics including `tracking_terminal_cause`,
`eligible_reserve_count` and `last_stop_reason`.

The later-cycle adapter discards all of it on the blocked path
(`later_cycle_graduated_supply.py` lines 132-133):

```python
if not supply.ready or len(supply.graduated_supply) != 2:
    return LaterCycleCandidateSupply((), (), supply.terminal)
```

`LaterCycleCandidateSupply` (`four_token_proof_integration.py` lines 137-141) is
a frozen dataclass with exactly three fields — `candidates`, `source_evidence`,
`terminal_cause` — and **no diagnostics field**. The certificate and the
classification cannot survive the boundary. The successful path (line 208) drops
them too.

Downstream, in `authoritative_live_operational_campaign.py`, the blocked
later-cycle attempt is terminalized at line 2102 with:

```python
cause=supply.terminal_cause or "NO_EXACT_PAIR",
```

`supply.terminal` for a permanent-availability shortage is the generic
`BLOCKED_INSUFFICIENT_ELIGIBLE_CANDIDATE_POOL`, so the attempt records a market
conclusion. That cause becomes the factory `stop_reason`
(`one_command_15m_factory.py` lines 7200-7205) and reaches
`terminal-summary.json` and `child-terminal.json`.

The existing authoritative mapping owner `_graduated_supply_terminal_cause`
(lines 849-868) is never consulted on this path, so its
`TRACKING_STATE_CAPACITY_BLOCKED` branch is unreachable, and
`_project_supply_exhaustion_certificate` (lines 871-872) has no diagnostics to
project. Observed: `report.exhaustion_certificate` and
`report.shortage_classification` were `null`, `TRACKING_STATE_CAPACITY_BLOCKED`
and `COOLDOWN_REOPEN_REQUIRED` appeared 0 times, and
`BLOCKED_INSUFFICIENT_ELIGIBLE_CANDIDATE_POOL` appeared 3 times.

This defect is **unconditional on the later-cycle path**: every later-cycle
shortage, of any classification, currently surfaces as a market conclusion.

## 4. Ownership and invariants

### 4.1 Canonical owners (unchanged)

| Concern | Sole owner |
|---|---|
| persistent multi-round eligible supply + durable certificate | `src/printer_v1/discovery/eligible_token_supply.py` |
| governed source-request scope + request-key root | `src/printer_v1/discovery/permanent_discovery_availability.py` |
| graduated-supply front door + `GraduatedSupply.diagnostics` | `src/printer_v1/operator_cli/graduated_supply_front_door.py` |
| Cycle-2 adaptation of the canonical supply | `src/printer_v1/operator_cli/later_cycle_graduated_supply.py` |
| Cycle-2 carrier type | `src/printer_v1/operator_cli/four_token_proof_integration.py` |
| truthful terminal-cause mapping | `authoritative_live_operational_campaign._graduated_supply_terminal_cause` |
| certificate projection | `authoritative_live_operational_campaign._project_supply_exhaustion_certificate` |

No new owner is created. The repair only routes existing evidence into the
existing owners.

### 4.2 Invariants the repair must preserve

1. `selection_seed` remains a **selection input only** — it stays the
   `cycle_seed` argument to `build_graduated_supply` and the `cycle_seed`
   argument to `apply_existing_discovery_gate_and_selection`. It must no longer
   act as the execution identity.
2. Campaign / run / cycle binding is exact and unchanged
   (`campaign_id`, `run_id=campaign_run_id`, `cycle_id=proposed_cycle_id`).
3. Cycle-2 must retain a collision-free governed request-key root (§4.3).
4. The truthful mapping stays single-owner: the later-cycle path must **call**
   `_graduated_supply_terminal_cause`, never restate its rules.
5. `TRACKING_STATE_CAPACITY_BLOCKED` must never be presented as a market
   conclusion. Only a proven `TRUE_MARKET_SUPPLY_SHORTAGE` (or an absent
   classification, preserving current behaviour) retains the historical
   insufficient-pool compatibility conclusion.
6. `LaterCycleCandidateSupply` must stay backward compatible with existing
   3-positional construction.
7. No historical DB row is rewritten. Existing certificates remain as historical
   evidence under their recorded identities.

### 4.3 Proven constraint on the execution identity

Source inspection establishes that the scope identity and the certificate
identity are **one channel**, not two:

- `permanent_discovery_availability.derive_campaign_source_request_key_root`
  (line 3555) derives the root from `execution_id` **alone** — the cycle id is
  not part of it.
- `graduated_supply_front_door.build_graduated_supply` (lines 846-861), under
  `permanent_availability=True` (which the later-cycle adapter sets),
  calls `validate_campaign_source_request_scope(scope, execution_id=execution_id, ...)`,
  which enforces `scope.execution_id == execution_id` **and**
  `scope.request_key_root == derive(scope.execution_id)` (lines 3643-3676).
  The scope identity and the `execution_id` kwarg therefore cannot differ.
- `inspect_preexisting_source_request_scope_collision` (lines 3706-3752) then
  blocks with `CAMPAIGN_SOURCE_REQUEST_SCOPE_ALREADY_EXISTS` when *any* durable
  `printer_source_requests` row already equals or starts with that root.

Consequence: binding the Cycle-2 scope to the **bare** canonical execution id
would reuse Cycle-1's root, and the collision gate would block Cycle-2 supply
before its first provider request. It would also make
`certificate_id = exh-<canonical>` collide with a Cycle-1 certificate on the
`certificate_id TEXT PRIMARY KEY` of
`printer_discovery_exhaustion_certificates` (`migrations/046_eligible_token_supply.sql`
line 56).

**Design decision.** The Cycle-2 execution identity becomes a canonical
execution-bound, cycle-qualified identity, derived only from exact invocation
identities:

```text
scope_execution_identity = f"{execution_id}:c{proposed_cycle_ordinal:04d}"
```

For the observed execution this is `20260815T194831Z-6d09a756e8d1:c0002`, giving
root `v2-9-8b-window15m-20260815T194831Z-6d09a756e8d1:c0002` (53 chars, within
the 180 limit, printable-ASCII, non-legacy) and certificate id
`exh-20260815T194831Z-6d09a756e8d1:c0002`.

This satisfies every stated requirement: the selection seed is removed from
execution ownership; the source scope and the certificate ownership are both
derived from the canonical execution id; the certificate becomes discoverable by
canonical-execution-id prefix; the cycle qualifier keeps the collision gate and
the certificate primary key satisfied; and campaign/execution/run/cycle binding
stays exact.

The alternative — threading a second, certificate-only execution identity
through `graduated_supply_front_door.py` and `eligible_token_supply.py` — was
rejected: it widens the blast radius into two additional canonical owners, still
requires a cycle qualifier on `certificate_id` to avoid the primary-key
collision, and gains nothing the prefix-bound identity does not already give.

## 5. Exact repair boundary

### 5.1 May change

| File | Change |
|---|---|
| `src/printer_v1/operator_cli/four_token_proof_integration.py` | add a 4th `diagnostics` field to `LaterCycleCandidateSupply`, defaulted so 3-positional construction stays valid |
| `src/printer_v1/operator_cli/later_cycle_graduated_supply.py` | add required keyword `execution_id`; derive the cycle-qualified canonical scope/execution identity from it; keep `selection_seed` as `cycle_seed` only; propagate `supply.diagnostics` on the blocked and successful returns |
| `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py` | `production_later_supply` passes the canonical `execution_id`; the later-cycle blocked terminalization routes through the existing `_graduated_supply_terminal_cause` |
| `tests/test_v2_9_8b_cycle2_exhaustion_reporting_canonical_execution_binding.py` | new focused regression test module |

### 5.2 Must not change

- `src/printer_v1/discovery/eligible_token_supply.py`
- `src/printer_v1/discovery/permanent_discovery_availability.py`
- `src/printer_v1/operator_cli/graduated_supply_front_door.py`
- `src/printer_v1/operator_cli/one_command_15m_factory.py`
- `src/printer_v1/operator_cli/pre_admission_discovery_attempt.py`
- `migrations/**` — no schema migration and no historical DB rewrite
- tracking/cooldown eligibility, reserve exclusion/removal, liquidity floors,
  source budgets, discovery algorithm, capacity, scoring/ranking/confidence,
  retry/automation

### 5.3 Exact repair shape

**Defect 1.**

```python
def build_later_cycle_graduated_supply(
    db_path, *, campaign_id, campaign_run_id, authoritative_factory_run_id,
    proposed_cycle_id, proposed_cycle_ordinal, evaluated_at,
    execution_id,          # NEW — canonical execution identity
    selection_seed,        # selection input only
    ...
):
    cycle_execution_identity = f"{execution_id}:c{proposed_cycle_ordinal:04d}"
    scope = build_campaign_source_request_scope(
        execution_id=cycle_execution_identity, ...
    )
    kwargs.update({..., "execution_id": cycle_execution_identity, ...})
    supply = build_graduated_supply(db_path, cycle_seed=selection_seed, ...)
```

`execution_id` is validated non-empty and fails closed with a stable blocker
code (`CANONICAL_EXECUTION_ID_REQUIRED`), consistent with the module's existing
`LaterCycleGraduatedSupplyError` vocabulary.

The caller `production_later_supply`
(`authoritative_live_operational_campaign.py` line 2849) supplies
`execution_id=selection_seed` **from the enclosing `run_operational` scope** —
that outer `selection_seed` is the canonical execution identity of the V2-9.8B
command, as the comment at lines 3086-3088 states and as the Cycle-1 path at
line 3091 already uses. The later-cycle composite arrives separately as
`context["selection_seed"]` and is passed through unchanged as the selection
input.

**Defect 2.**

```python
@dataclass(frozen=True)
class LaterCycleCandidateSupply:
    candidates: tuple[LaterCycleDiscoveryCandidate, ...]
    source_evidence: tuple[LaterCycleSourceEvidence, ...]
    terminal_cause: str | None
    diagnostics: Mapping[str, Any] = field(default_factory=dict)
```

The adapter returns `dict(supply.diagnostics)` on both the blocked return and
the successful return.

The blocked terminalization consults the existing mapping owner, preserving
current behaviour whenever the adapter supplied no classification:

```python
diagnostics = dict(getattr(supply, "diagnostics", {}) or {})
if diagnostics.get("shortage_classification"):
    cause = _graduated_supply_terminal_cause(supply)
else:
    cause = supply.terminal_cause or "NO_EXACT_PAIR"
```

`_graduated_supply_terminal_cause` already reads
`getattr(supply, "diagnostics", {})`, so a `LaterCycleCandidateSupply` carrying
diagnostics is accepted verbatim with no signature change and no second mapping
implementation. `TRACKING_STATE_CAPACITY_BLOCKED` therefore returns
`tracking_terminal_cause` or `COOLDOWN_REOPEN_REQUIRED`; a
`TRUE_MARKET_SUPPLY_SHORTAGE` or an absent classification retains the historical
insufficient-pool conclusion; every other class keeps its categorical name.

## 6. Money-usefulness contribution

Printer only becomes money-useful if it grows clean memory, and it only grows
clean memory if operator decisions about *why* a campaign produced no tokens are
true. Today every later-cycle shortage is reported as a market conclusion. An
operator reading the host artifacts concludes "the Solana memecoin market was
thin" and either burns another scarce one-shot authorization against an
unchanged internal condition, or abandons a supply route that was never actually
empty — in the observed run, liquidity-proven reserve tokens existed and were
withheld by internal tracking state.

This repair makes the durable, already-correct classification visible at the
point of decision, at zero authorization cost. It stops the wasted-proof loop and
points the next lane at the real, addressable, internal condition instead of at
an imagined market.

## 7. What improves

- The Cycle-2 exhaustion certificate becomes discoverable from the canonical
  execution id, restoring the convention used by the 11 prior certificates and
  unbreaking any tooling keyed on execution id.
- The selection seed stops silently owning execution identity, source-request
  scope, and certificate identity.
- `LaterCycleCandidateSupply` carries the diagnostics the design contract
  requires, on both the blocked and successful paths.
- `TRACKING_STATE_CAPACITY_BLOCKED` reaches the existing truthful mapping, so
  the pre-admission attempt, the factory `stop_reason`, `terminal-summary.json`
  and `child-terminal.json` record `COOLDOWN_REOPEN_REQUIRED` (or the exact
  `tracking_terminal_cause`) instead of an insufficient-pool market conclusion.
- `exhaustion_certificate` and `shortage_classification` become non-null through
  the existing projection whenever the adapter supplies them.
- The fix is unconditional on the later-cycle path, so it corrects *every* future
  later-cycle shortage class, not only this run's condition.

## 8. What remains locked

Unchanged and still locked: authorization creation or consumption, four-token
proof execution or rerun, campaign start, six-token proof and capacity widening,
`WINDOW_1H` / `WINDOW_12H` / `WINDOW_24H` activation, discovery/source fetching,
runtime, authoritative DB mutation, memory generation, schema migration and
historical DB rewrite, tracking/cooldown eligibility changes, reserve
exclusion/removal changes, liquidity floors, source budgets, discovery algorithm,
capacity, scoring/ranking/confidence/weighted logic, retry/automation,
retrieval, paper decisions, BUY/SELL/HOLD, positions, trade events, paper
audits, PnL, wallets, private keys, real funds, live execution, paid APIs,
embeddings and vectors. Solana memecoin-only and paper-only remain in force.

The tracking-state / reserve-exclusion audit (including the 10
`PERSISTED_GRADUATED` / `LIQUIDITY_PROVEN` rows observed `EXCLUDED` / `REMOVED`)
remains a separate later lane and is not begun here. Those exclusions are not
assumed defective.

## 9. Minimum proof needed

Offline, source-free, DB-free-except-`tmp_path` focused TDD. RED first, then the
minimal implementation.

Required assertions:

1. the canonical `execution_id` reaches the governed source-scope construction
   and the `build_graduated_supply` `execution_id` kwarg, cycle-qualified;
2. `selection_seed` is preserved separately and reaches only `cycle_seed`;
3. the composite selection seed no longer appears in the scope or execution
   identity;
4. a blocked later-cycle supply preserves `shortage_classification` and
   `exhaustion_certificate` diagnostics across the carrier boundary;
5. the successful path preserves diagnostics;
6. 3-positional `LaterCycleCandidateSupply(candidates, evidence, cause)`
   construction remains valid (it is relied on by four existing test modules);
7. `TRACKING_STATE_CAPACITY_BLOCKED` carried by the adapter reaches
   `_graduated_supply_terminal_cause` and yields `COOLDOWN_REOPEN_REQUIRED` /
   the exact `tracking_terminal_cause`, never
   `BLOCKED_INSUFFICIENT_ELIGIBLE_CANDIDATE_POOL` or
   `BLOCKED_INSUFFICIENT_GRADUATED_POOL`;
8. `_project_supply_exhaustion_certificate` is non-null for adapter-supplied
   diagnostics;
9. absent diagnostics preserve the existing terminal-cause behaviour exactly.

Plus the nearest directly affected regression module
(`tests/test_v2_9_8b_pre_admission_later_cycle_callback.py`), compile/import
checks for the three touched modules, and diff/static inspection.

No broad suite. Verification stays inside the Risk-Based Verification Policy
band for a narrow code change.

## 10. Functionality Risks / Setbacks / Efficiency Blockers

| Risk / blocker | Consequence | Control |
|---|---|---|
| Binding the Cycle-2 scope to the bare canonical execution id | `CAMPAIGN_SOURCE_REQUEST_SCOPE_ALREADY_EXISTS` blocks Cycle-2 supply before its first provider request, and `certificate_id` collides on the primary key | Cycle-qualified canonical identity `<execution_id>:c<ordinal:04d>` (§4.3), proven against the collision gate and the 046 schema |
| Changing the request-key root changes Cycle-2's `_source_lineage` window | Cycle-2 evidence linkage could capture the wrong requests | Root stays cycle-exclusive; `_source_lineage` continues to filter by `scope.request_key_root`; no Cycle-1 key can start with the Cycle-2 root |
| Historical certificates keep the old composite identity | A canonical-id query still misses pre-repair Cycle-2 rows | Accepted and explicit: no historical rewrite, no migration. Documented as historical evidence |
| Adding a 4th dataclass field | Existing 3-positional construction could break | Defaulted field; four existing test modules exercise the 3-positional form and are run as regression |
| `diagnostics` makes the frozen dataclass unhashable | A caller hashing the carrier would fail | Static inspection found no caller that hashes or sets `LaterCycleCandidateSupply`; only equality/`isinstance` are used |
| Routing the blocked cause through the mapping owner | Could change causes for supplies with no classification | Guarded: the mapping is consulted only when the adapter supplied a classification; otherwise the exact existing behaviour is preserved and asserted |
| The truthful cause becomes the factory `stop_reason` | A different terminal string reaches host artifacts | Intended and required by the committed contract; no lifecycle, retry, or cleanup behaviour is keyed on the old string |
| Certificate still not durably projected into the later-cycle host artifact | `report.exhaustion_certificate` can remain null for Cycle-2 unless the campaign report is fed by the adapter's diagnostics | Out of this boundary: the pre-admission attempt table carries only a cause string, and a durable certificate column would require a locked schema migration. Recorded as a follow-on question in §11 |
| Scope creep into the reserve-exclusion question | Would merge two lanes and delay both | Explicitly deferred; not assumed defective |
| Repair reduces urgency of the real internal condition | Truthful labelling could be mistaken for resolution | The classification is a diagnosis, not a fix; the follow-on exclusion audit remains required before any authorization |

## 11. Open question for a later lane (not this one)

Whether the Cycle-2 exhaustion certificate should also be projected durably into
the campaign terminal report requires either an approved schema addition to
`printer_pre_admission_discovery_attempts` or an approved in-memory hand-back
from the later-cycle callback into the campaign report assembler. Both exceed
this repair boundary. This design deliberately stops at making the truthful
classification reach the terminal cause and making the certificate available at
the carrier boundary.

## 12. Next step after this design

Narrow TDD implementation on this branch: RED focused tests first, then the
minimal repair, then focused verification and an independent closeout. No
authorization #7, no four-token rerun, no campaign, no DB mutation.
