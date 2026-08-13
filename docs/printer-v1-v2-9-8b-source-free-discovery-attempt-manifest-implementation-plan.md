# V2-9.8B Source-Free Discovery Attempt Manifest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement only the deterministic, source-free exact two-token discovery-attempt manifest required by the ratified source-free discovery-capacity design.

**Architecture:** Factor request-plan facts from the existing execution owners instead of creating a second policy model. The new proof-only manifest composes Pump origin, active secondary discovery branches, and the holder safety request plan into one immutable exact-pair attempt shape. It performs no source, Scheduler, DB, lifecycle, callback, or admission work.

**Tech Stack:** Python 3, pytest, existing Printer V1 source/operational owner modules.

## Global Constraints

- Baseline branch: `agent/v2-9-8b-four-token-bounded-capacity-proof-integration-implementation`.
- Baseline HEAD: `f651d5d3aac3057d7f272de3d2a9b69b7069ffd5`.
- Use the active Printer V1 source stack plus `docs/printer-v1-v2-9-8b-source-free-discovery-capacity-authority-design.md`.
- Solana-only, Solana memecoin-only, paper-only.
- Public `TOKEN_CAPACITY == 2` remains unchanged.
- No source fetching, Scheduler execution, DB mutation, lifecycle execution, callback invocation, cycle-2 admission, memory, authorization, proof run, retrieval, paper decisions, positions, trades, audits, PnL, or 12h/24h activation.
- No parsing `OperationalSourceContract.operation_budget` prose.
- No copied provider/rate/request ceilings when an existing machine-readable owner exists.
- No provider-capacity/recheck implementation in this seam.
- Preserve untracked operator authorization artifacts.

---

### Task 1: RED — Exact source-free manifest contract

**Files:**
- Create: `tests/test_v2_9_8b_source_free_discovery_attempt_manifest.py`

**Interfaces:**
- Consumes existing Pump, secondary-discovery, holder-budget, and live-composition owners.
- Specifies a future pure manifest builder for exactly two selected targets.

- [ ] **Step 1: Write the failing contract tests**

Require the future manifest to prove:

1. `target_count == 2`.
2. Pump request requirements are derived from `pumpfun_origin.REQUEST_CEILINGS`, using the existing Pump source identity and request kinds.
3. Secondary requirements match the branches the live `LiveSecondaryDiscoveryAdapter.enrich(...)` path can execute:
   - Gecko trending;
   - conditional Gecko active-pool enrichment reserved when that branch can occur;
   - DexScreener fresh profiles;
   - Solana Tracker only when existing free-key/configuration evidence enables it.
4. Holder safety requirements expose GoPlus, conditional primary Solana RPC holder evidence, and conditional one-shot Helius Free backup.
5. Holder-plan totals reconcile exactly to `HOLDER_WORST_CASE_GOVERNED_REQUESTS == 3` and `HOLDER_WORST_CASE_TRANSPORT_OPERATIONS == 5` under the existing worst-case contract.
6. No paid/prohibited source appears.
7. Constructing the manifest performs zero DB/source/Scheduler activity.

The RED must fail because the manifest/helper does not yet exist, not because of malformed test setup.

- [ ] **Step 2: Run only the new focused test and capture the exact RED**

Run:

```bash
pytest -q tests/test_v2_9_8b_source_free_discovery_attempt_manifest.py
```

Expected: focused failure for missing source-free manifest/helper behavior.

- [ ] **Step 3: Commit the valid RED**

Commit only the test file with a message equivalent to:

```text
Add RED source-free discovery attempt manifest contract
```

---

### Task 2: GREEN — Factor the holder safety request plan

**Files:**
- Modify only the smallest existing safety/preclose owner needed to expose the current holder request-plan facts.
- Prefer the owner that currently performs `_collect_preclose_context(... include={"safety"})`; do not create a second holder policy module.
- Test: `tests/test_v2_9_8b_source_free_discovery_attempt_manifest.py`

**Interfaces:**
- Produces one pure immutable/read-only holder request plan.
- The plan identifies source name, request kind, conditionality, governed-request contribution, and worst-case transport contribution for:
  - GoPlus `safety_reference`;
  - primary Solana RPC `holder_concentration_reference` when GoPlus holder concentration is unknown;
  - one Helius Free `holder_concentration_reference` backup only after an eligible transient primary failure.

- [ ] **Step 1: Factor existing literals/conditions into one pure plan helper**

The runtime collection path and the read-only helper must consume the same named request/source facts where practical. Do not change collection order, fallback eligibility, source execution, pacing, or budgets.

- [ ] **Step 2: Prove aggregate parity**

The focused test must assert that the pure plan reconciles to the existing holder worst-case aggregate contract. If the real provider/request-kind split cannot reconcile without inventing a transport count, stop and report the exact blocker; do not force the totals.

---

### Task 3: GREEN — Compose the proof-only discovery manifest

**Files:**
- Create: `src/printer_v1/operator_cli/source_free_discovery_capacity.py`
- Modify, only if needed to eliminate an existing hard-coded runtime literal: `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`
- Modify, only if needed to expose a named existing request identity used by the live path: `src/printer_v1/sources/secondary_discovery.py`
- Test: `tests/test_v2_9_8b_source_free_discovery_attempt_manifest.py`

**Interfaces:**
- Produces immutable records equivalent to:
  - `DiscoveryAttemptRequirement`
  - `LaterCycleDiscoveryAttemptManifest`
- Produces a pure builder for exactly one later-cycle two-token attempt.
- Inputs may include only configuration evidence necessary to determine existing optional branches, such as whether the already-supported free Tracker path is enabled.

- [ ] **Step 1: Compose Pump requirements from `pumpfun_origin.REQUEST_CEILINGS`**

Import the canonical source name/request-kind identities and ceilings. Do not copy Pump numeric limits into the new module.

- [ ] **Step 2: Compose active secondary requirements from existing live owner facts**

Use the current live composition, not historical/fixture-only branches. If the live DexScreener request kind is currently a hard-coded literal, extract it once into the existing owner and make the runtime callsite and manifest use that same fact.

- [ ] **Step 3: Compose the holder plan from Task 2**

Preserve conditional fallback semantics conservatively. A branch that may lawfully execute under current configuration remains reserved.

- [ ] **Step 4: Validate the manifest fail-closed**

The builder must reject:

- target count other than 2;
- unknown/unregistered request kinds;
- any paid/prohibited source requirement;
- inconsistent holder aggregate parity;
- incomplete owner/configuration evidence needed to determine an optional branch.

It must not call the Source Governor's execution path; validation may use pure registry/request-kind contracts only.

- [ ] **Step 5: Run focused GREEN verification**

Run:

```bash
pytest -q tests/test_v2_9_8b_source_free_discovery_attempt_manifest.py
pytest -q tests/test_v2_9_8b_four_token_controller_readiness.py tests/test_v2_9_8b_four_token_proof_integration.py
python -m py_compile src/printer_v1/operator_cli/source_free_discovery_capacity.py
python -m py_compile src/printer_v1/operator_cli/authoritative_live_operational_campaign.py src/printer_v1/operator_cli/one_command_15m_factory.py

git diff --check
```

Run only touched-module compile checks; omit an unchanged file from `py_compile` if it was not touched.

- [ ] **Step 6: Commit minimum GREEN**

Commit only the manifest implementation and exact supporting parity helpers with a message equivalent to:

```text
Add source-free discovery attempt manifest
```

---

## Completion Gate

This seam passes only if:

- the RED was valid and committed separately;
- the manifest is deterministic and source-free;
- every numeric request ceiling comes from existing machine-readable authority;
- holder provider/request-kind parity is exact;
- optional paths are configuration-bound and conservative;
- no provider-capacity/recheck logic was added;
- no source/Scheduler/DB/runtime/callback/admission capability was activated;
- focused tests and `git diff --check` pass.

Stop after GREEN. The next approved seam is provider-reaching attempt detail in `sources/budget_accounting.py`, not admission-health projection yet.
