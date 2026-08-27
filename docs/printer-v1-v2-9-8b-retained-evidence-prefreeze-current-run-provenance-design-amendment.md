# V2-9.8B Retained-Evidence Pre-Freeze Current-Run Provenance Design Amendment

**Amendment verdict:** `V2_9_8B_RETAINED_EVIDENCE_PREFREEZE_CURRENT_RUN_PROVENANCE_DESIGN_AMENDMENT_PASS`

**Classification:** `CONTRACT_DRIFT` + `DESIGN_GAP`

**Base repair HEAD under review:** `ccea7f4d3a5745e899c9cfad83d1b92bbc702bc9`

**Base repair stack:**

```text
484f56c
-> c1bc193
-> 55def2b
-> ccea7f4
```

**Governing triage:** `V2_9_8B_RETAINED_EVIDENCE_ROLE_MISSING_INDEPENDENT_TRIAGE_AUDIT_PASS`

**Base design file (preserved, not overwritten):**

`docs/printer-v1-v2-9-8b-retained-evidence-role-completeness-before-freeze-repair-design.md`

This amendment does **not** replace the approved base repair invariants. It
corrects an unapproved relaxation that allowed current-run
manifest/transport/provenance qualification to remain final-validator-only.

---

## 1. Proven remaining gap

The current pre-freeze qualifier proves candidate-local role validity:

- request exists
- response exists
- response belongs to request
- `COMPLETE` / `CLEAN_DATA`
- source-name consistency
- role/source/request-kind compatibility
- candidate mint/pool payload binding
- candidate expiry

It does **not** establish before freeze:

- current campaign ownership
- current run ownership
- current cycle ownership
- measured manifest membership
- measured transport-identity ownership
- retained response/payload hash identity where required by the activation
  contract

The qualifier does not receive `campaign_id`, `run_id`, `cycle_id`, measured
manifest, or measured transport-identity set.

Therefore a prior campaign's otherwise-valid request/response for the same
mint/pool can potentially pass the pre-freeze gate and only fail after seeded
selection at the final manifest/transport validator.

That recreates select-then-reject at the provenance layer.

The committed base design introduced an architectural relaxation that treated
manifest/transport as final-validator-only because those sets are currently
reassembled after freeze. That relaxation was not separately approved and is
treated here as `CONTRACT_DRIFT` plus `DESIGN_GAP`.

---

## 2. Current production ordering (actual)

Permanent operational path (authoritative):

```text
1. build CampaignSourceRequestScope
   (execution_id, campaign_id, run_id, cycle_id, request_key_root)

2. discovery / market / protocol / liquidity source calls
   - request_key under request_key_root
   - logical_stage_id = campaign|run|cycle|STAGE|seq
   - transport identities measured during calls
   - response rows + response_hash persisted

3. pre_holder assemble_and_reconcile_campaign_source_requests(...)
   - durable IDs filtered by request_key_root
   - campaign_source_request_manifest with logical_stage_id + transport keys
   - pre_holder_budget_snapshot.measured_transport_identity_keys

4. holder evaluation
   - additional holder request/response rows under same request_key_root

5. observation_rows construction

6. retained-role completeness filter   <-- current gate (missing provenance)

7. freeze_eligible_reserve_for_campaign(...)
   - four-candidate depth; two selected; two report-only alternates

8. post-freeze assemble_and_reconcile_campaign_source_requests(...)
   - includes holder-stage requests as well as pre-holder discovery requests

9. _build_frozen_memory_activation_set(...)
   - uses post-freeze manifest + measured transport keys

10. final validate_memory_activation_set(...)
    - campaign/run/cycle ownership on RetainedEvidenceReference
    - manifest membership
    - transport binding
    - response_hash / payload binding
```

### When each fact becomes knowable

| Fact | First knowable | Notes |
|---|---|---|
| source request ID | at governed source call (step 2/4) | durable row |
| source response ID | at successful response persist | durable row |
| response_hash | at response persist | already selected by qualifier SQL but currently unused |
| observation / requested_at | at request/response persist or liquidity envelope | knowable before freeze |
| campaign/run/cycle identities | at campaign/scope construction (step 1) | available throughout |
| request_key_root ownership | at request persist via `request_key` | enforceable by `request_key_belongs_to_root` |
| logical_stage_id ownership | at stage coverage emission (step 2) | `campaign\|run\|cycle\|STAGE\|seq` |
| measured transport identity | at transport measurement (step 2/4) | observed live |
| measured manifest membership | at recon (step 3 already; step 8 again) | **already available before freeze** for pre-holder evidence |

### Semantic vs incidental

For retained roles used by freeze/activation (`MARKET_OBSERVATION`,
`ORIGIN_LINEAGE`, `PUMPSWAP_CONFIRMATION`), the evidence is produced in
discovery/market/protocol stages **before** holder and **before** freeze.

The post-freeze recon is needed to include holder-stage requests in the full
campaign accounting/manifest. It is **not** a semantic necessity for first
proving current-run ownership of discovery/market/protocol retained roles.

Therefore "manifest only exists after freeze" is **incidental ordering for those
roles**, not a semantic barrier. Pre-holder recon already constructs the
candidate-relevant measured ownership set before freeze.

---

## 3. Exact current-run provenance authority

Authoritative owners already present in production:

1. **`CampaignSourceRequestScope`**
   - fields: `scope_version`, `request_key_root`, `execution_id`, `campaign_id`,
     `run_id`, `cycle_id`
   - builder: `build_campaign_source_request_scope(...)`
   - validator: `validate_campaign_source_request_scope(...)`

2. **`request_key_belongs_to_root(request_key, request_key_root)`**
   - durable DB proof that a `printer_source_requests.request_key` belongs to
     the exact current invocation root
   - prior campaigns use a different execution-id root and fail this check

3. **Stage coverage / campaign source-request manifest**
   - produced by `assemble_and_reconcile_campaign_source_requests(...)`
   - each entry requires: `source_request_id`, `source_name`, `request_kind`,
     `logical_stage_id`, `terminal_status`, `transport_identity_count`,
     `normalized_member_count`, `transport_identity_keys`

4. **`logical_stage_id`**
   - format owned by `build_campaign_stage_id(...)` /
     permanent-discovery stage emitters:
     `campaign_id|run_id|cycle_id|STAGE_KIND|sequence`
   - must prefix-match the exact current campaign/run/cycle

5. **Measured transport identity keys**
   - observed at measurement time; owned per request in the manifest
   - final validator already requires exact request ownership / non-empty keys
     for completed requests

6. **`printer_source_responses.response_hash`**
   - durable payload identity available as soon as the response row exists

These are authoritative. String guessing, provenance labels, registry hashes,
or mint/pool coincidence are not substitutes.

---

## 4. Chosen design option

**Chosen: OPTION A, with a narrow OPTION C ordering clarification.**

### OPTION A — use already-assembled measured ownership before freeze

Before the retained-role completeness gate, pass the already-available
pre-holder measured ownership surfaces into qualification:

- `CampaignSourceRequestScope` (or exact campaign/run/cycle + request_key_root)
- `pre_holder_source_request_reconciliation.campaign_source_request_manifest`
- `pre_holder_budget_snapshot.measured_transport_identity_keys`
  (and/or the exact per-request transport keys on the manifest)

No new source activity. No new schema. No second selector.

### OPTION C clarification — split final activation recon from first provenance proof

Keep post-freeze recon for holder-inclusive campaign accounting and activation
construction.

Do **not** treat that later recon as the first moment current-run provenance is
knowable for discovery/market/protocol retained roles.

Required order after amendment:

```text
source calls complete (discovery/market/protocol/liquidity)
-> measured request/transport ownership assembled (pre-holder recon; already exists)
-> candidate retained-role qualification INCLUDING current-run provenance
-> neutral freeze (exactly 4 depth / 2 selected / 2 report-only alternates)
-> post-freeze recon (may include holder rows)
-> selected activation construction
-> final retained-role validator (defense in depth)
```

### Rejected for this amendment

- **OPTION B alone** — `request_key_root` is necessary but not sufficient without
  measured manifest/transport ownership for the same truth contract as final
  validation.
- **OPTION D** — blocked only if measured ownership were unknowable before
  freeze. Production already builds it at pre-holder recon.

---

## 5. Amended pre-freeze qualifying predicate

A required role is pre-freeze complete only when **both** are true:

### 5.1 Candidate-local / role-valid (already implemented; preserve)

- request/response IDs present
- request row exists
- response row exists
- response belongs to request
- no failure presented as success
- `COMPLETE` / `CLEAN_DATA`
- source-name consistency
- role/source/request-kind binding allowed
- mint/pool payload binding
- candidate evidence not expired

### 5.2 Current-run measured provenance (new mandatory)

For the same request/response pair:

1. **Current-run durable ownership**
   - `printer_source_requests.request_key` belongs to the exact current
     `CampaignSourceRequestScope.request_key_root`
   - prior-campaign roots fail closed

2. **Measured manifest membership**
   - `source_request_id` is present in the current pre-freeze measured
     campaign source-request manifest

3. **Logical-stage ownership**
   - manifest `logical_stage_id` starts with
     `{campaign_id}|{run_id}|{cycle_id}|`
   - mismatch fails closed

4. **Transport identity ownership**
   - for completed manifest entries, transport identity keys must be present
     and non-empty under the existing exact-binding rule
   - each declared key must be owned by that request in the measured set
   - missing/mismatched transport identity fails closed

5. **Response/payload identity**
   - `response_hash` must be present and non-empty on the durable response row
   - the qualifier already loads this field and must use it rather than ignore it
   - observation/requested time remains available from durable rows /
     liquidity envelopes; preserve existing expiry and observation binding
     rules without inventing a weaker substitute

A prior campaign's otherwise-valid request/response for the same mint/pool must
never satisfy 5.2 and therefore must never qualify a current freeze slot.

---

## 6. Manifest ownership rule

Pre-freeze qualification must consume the **already assembled** measured
manifest from the pre-holder reconciliation path:

- `supply.diagnostics["pre_holder_source_request_reconciliation"]`
- fields: `campaign_source_request_manifest`, `durable_campaign_request_ids`

If that recon is missing or not `OK`, fail closed before freeze. Do not invent
manifest rows.

Post-freeze recon remains for holder-inclusive accounting/activation. It does
not authorize postponing current-run provenance proof for retained freeze roles.

---

## 7. Transport identity rule

Reuse existing transport-identity truth:

- per-request `transport_identity_keys` on the measured manifest entry
- existing final-validator rules for completed requests requiring owned keys
- no acceptance of counts without keys
- no cross-request shared key ownership

Pre-freeze must apply the same ownership checks for the candidate's required
role request IDs against the pre-freeze measured set.

---

## 8. Response hash / timestamp rule

- `response_hash` is knowable at response persist and must be checked before
  freeze (non-empty durable hash).
- Request `requested_at` / payload observation times are knowable before freeze;
  candidate `evidence_expires_at` remains mandatory.
- Do not SELECT hash/time fields and ignore them.

---

## 9. Source/kind ownership decision

Keep a single composed binding registry owned by:

`printer_v1.discovery.memory_observation_activation`

Function family:

- `retained_evidence_role_source_kind_bindings()`
- `retained_evidence_role_source_kind_allowed(...)`

Rules for this amendment:

1. Bindings must be derived from production producer constants/contracts.
2. Prefer imports of canonical constants over string literals.
3. The remaining hardcoded PumpSwap verify pair must be sourced from the
   existing discovery producer constants
   (`VERIFY_SOURCE` / `VERIFY_REQUEST_KIND` in
   `direct_migration_discovery`) rather than free-floating literals.
4. This registry is an explicit ownership surface, not a second competing
   semantic matrix. Producer contract changes require updating this registry
   in the same lane.

Preserve current accepted role families already proven by producer contracts:

- ORIGIN_LINEAGE — direct Pump / Pumpfun origin transaction refs on `solana_rpc`
- PUMPSWAP_CONFIRMATION — `pumpswap_pool_account_batch` and
  `pumpswap_signature_pool_resolution`
- MARKET_OBSERVATION — DexScreener / GeckoTerminal market observation kinds

---

## 10. Expected implementation file scope

Documentation:

- this amendment file
- base design remains preserved

Likely product owners for a later separately approved implementation lane:

- `src/printer_v1/discovery/memory_observation_activation.py`
- `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`
- focused repair tests

Potential constant-import cleanup only:

- `src/printer_v1/discovery/direct_migration_discovery.py`
  (export/use existing VERIFY constants; no behavior expansion)

No migration expected. No new source activity. No authorization. No Printer run
in the design lane.

---

## 11. Cases P–T future bounded-proof design

These are design-required proofs for the later implementation correction lane.
They are not authorized to run by this amendment alone.

### CASE P — PRIOR-CAMPAIGN SAME TOKEN

Insert/complete a valid request/response for the same mint/pool whose
`request_key` belongs to a different execution/campaign root.

Pre-freeze must exclude it. It must not reach seeded freeze.

### CASE Q — REQUEST NOT IN CURRENT MEASURED MANIFEST

Valid durable request/response for current root semantics is absent from the
current measured manifest.

Pre-freeze must exclude. Candidate must not reach seeded freeze.

### CASE R — TRANSPORT IDENTITY MISMATCH

Request is in the current measured manifest, but required transport identity
ownership is missing/mismatched.

Pre-freeze must exclude. Candidate must not reach seeded freeze.

### CASE S — CURRENT PROVENANCE VALID

Exact current-run governed request/response with matching root, logical-stage
ownership, measured manifest membership, transport ownership, and response hash
qualifies and may reach neutral selection normally.

### CASE T — FINAL DEFENSE

Force a provenance-invalid selected candidate past the early gate in a
controlled test.

Existing final validator must still fail closed
(`RETAINED_REQUEST_NOT_IN_MANIFEST`,
`RETAINED_TRANSPORT_IDENTITY_MISSING`,
`RETAINED_OWNERSHIP_MISMATCH`, or exact current canonical equivalent).

Preserve Cases A–O from the base repair.

---

## 12. Preserved previous repair behavior

This amendment preserves:

- missing/empty/unknown admission authority fail-closed; no DIRECT_PUMP default
- admission_authority as canonical required-role owner
- claims contradiction fail-closed
- role/source/request-kind mismatch fail-closed
- cross-role reuse fail-closed
- request/response existence and linkage
- COMPLETE/CLEAN_DATA
- mint/pool binding
- expiry handling
- incomplete candidates filtered before freeze
- four-candidate freeze depth
- neutral seeded selector
- exactly two selected
- two report-only alternates
- no alternate substitution / no second selector
- narrow alternate soft handling
- final retained-role validator remains fail closed
- Cycle-1 ordinal repair
- Cycle-2 historical-disjointness
- Source Governor / Central Scheduler ownership
- all permanent V1 locks
- no retrieval/financial unlock
- consumed authorization permanently non-reusable

---

## 13. Risks / concerns

1. Pre-holder measured manifest excludes later holder-stage requests by design.
   That is acceptable because retained freeze roles do not use holder
   safety/mint-account requests. Implementation must not accidentally require
   holder IDs for MARKET/ORIGIN/PUMPSWAP completeness.

2. If a future producer starts creating retained MARKET/ORIGIN/PUMPSWAP
   evidence only after holder, the pre-freeze measured set would need an
   explicit refresh before the gate. Current production does not do that.

3. Implementation must thread scope/manifest/transport into the qualifier
   without scraping the whole DB by mint alone.

4. Do not weaken final validation after adding pre-freeze provenance checks.

---

## 14. Classification

Primary: `CONTRACT_DRIFT`

Secondary: `DESIGN_GAP`

Not:

- expected operational blocker
- missing schema / migration requirement
- need for new provider/RPC capability

---

## 15. Non-goals

This amendment does not authorize:

- implementation
- bounded proof execution
- Printer runs
- provider/RPC/WebSocket calls
- Scheduler ticks
- authorization create/consume
- authoritative DB writes
- weaker pre-freeze contracts
- alternate promotion
- scoring/ranking/confidence

---

## 16. Next permitted action

```text
CURRENT-RUN PROVENANCE IMPLEMENTATION CORRECTION
— SEPARATE APPROVAL REQUIRED
```

PASS of this amendment does not authorize that implementation lane by itself.
