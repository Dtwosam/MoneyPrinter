# Printer V1 — WINDOW_15M Checkpoint 3 Repair Design

Issue: `DTW-29`

Audit verdict: `V2_9_8B_WINDOW_15M_CHECKPOINT_3_AUDIT_CONFIRMED_THREE_BLOCKERS`

RED commit: `e4d7fac36c14a3a42669f5fc097d38fbf1b4dc11`

## Goal

Repair only the three deterministic blockers proven by the Checkpoint 3 RED suite while preserving ordinary `WINDOW_15M` discovery, selection, Source Governor, Central Scheduler, two-slot atomicity, ceilings, zero automatic retries, and all locked capabilities.

## Repair 1 — exact existing-pair binding

Owner: `CombinedPumpfunCampaignExecutor._handoff_one_slot`.

When `pair_address` already exists, read `id`, `token_id`, and `base_token_mint`. Accept it only when both `token_id == selected token_id` and `base_token_mint == selected mint`. Otherwise raise `CombinedDiscoveryError("PAIR_TOKEN_IDENTITY_MISMATCH")` before tracking queue claim, first-15m Scheduler enqueue, slot insertion, or selection-link persistence.

No pair reassignment, mutation, deletion, or alternate-pair search is allowed.

## Repair 2 — request-before-failure causality

Owner: `CombinedPumpfunCampaignExecutor._run_direct_lane`.

For an injected direct-provider failure, create the governed source request first, then persist the source failure, then link both identities to the discovery work and terminalize the work as failed.

The repair adds no transport, response, retry, fallback, source call, or new accounting owner. It changes ordering only.

## Repair 3 — delimiter-bound campaign source scope

Owner: `request_key_belongs_to_root` in `permanent_discovery_availability.py`.

A request belongs to the root only when:

- `request_key == request_key_root`; or
- `request_key` starts with `request_key_root + "-"`.

Adjacent-prefix siblings such as `<root>shadow` fail closed. Existing canonical child keys remain valid because the current source-request key vocabulary derives children with `-` delimiters.

## Test-first contract

The existing Checkpoint 3 RED suite must turn GREEN without weakening assertions:

1. exact pair mismatch returns `PAIR_TOKEN_IDENTITY_MISMATCH` and leaves zero slots, queue rows, and first-15m jobs;
2. direct failure observes one governed request before failure persistence and retains exact request/failure linkage;
3. root and hyphen-delimited children pass while adjacent-prefix siblings fail.

Nearest sufficient regressions:

- graduation-native activation / atomic handoff;
- combined discovery executor source-failure and Scheduler claim coverage;
- permanent discovery source-scope/accounting tests;
- Python compilation and diff checks.

All tests and proof databases must be disposable. Do not run Printer, providers, authorization, or the authoritative database.

## Acceptance gate

PASS requires:

- the three RED tests GREEN;
- nearest affected regressions GREEN or unrelated pre-existing failures reproduced and documented;
- no new source request, Scheduler, retry, fallback, or capability path;
- branch ancestry from the exact baseline;
- closeout report and Linear closeout recorded.

## Stop conditions

Stop and report BLOCKED if any repair requires schema change, provider access, authoritative-database mutation, broad architecture changes, weakened identity/evidence rules, raised ceilings, retries, or Checkpoint 4 work.

## Money-usefulness contribution

The repair keeps future clean-memory inputs tied to the correct mint/pair and makes source/accounting evidence auditable rather than inflated or ambiguously ordered.

## What this lane improves

Exact handoff identity, causal source accounting, invocation-local request ownership, and terminal diagnosis.

## What this lane still does not unlock

Memory generation, retrieval, decisions, BUY/SELL/HOLD, positions, trades, audits, PnL, live execution, wallets, private keys, paid APIs, scoring/ranking/confidence/weighted logic, embeddings/vectors, `WINDOW_1H`, or Checkpoint 4.

## Functionality Risks / Setbacks / Efficiency Blockers

- Existing corrupt pair identity must block, never be silently repaired.
- Failure ordering must remain transactionally atomic with its request/link rows.
- Scope delimiter tightening must not reject valid canonical child request keys.
- Verification must stay narrow and disposable; broad runtime proof is prohibited.

## Design verdict

`V2_9_8B_WINDOW_15M_CHECKPOINT_3_NARROW_REPAIR_DESIGN_PASS`