# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 — DTW-50 Holder Request Scope Propagation Audit

Date: 2026-08-07

Linear: `DTW-50`

Verdict:

`V2_9_8B_WINDOW_15M_CHECKPOINT_8_DTW50_HOLDER_REQUEST_SCOPE_PROPAGATION_AUDIT_CONFIRMED`

## Consumed proof evidence

The post-DTW49 one-shot proof `C8_REPROOF_AFTER_DTW49_20260807` at authorization/proof HEAD `432821130796729f7b0276f9800363ab3e61bf28` is immutable and may not be retried, resumed, restarted, or reused.

Frozen evidence SHA-256: `78e352d0596d027d3c4fb016411a29672e03d535a9c903cea84b0d23a5feaa6b`.

The attempt honestly stopped before lifecycle with `CAMPAIGN_SOURCE_REQUEST_RECONCILIATION_MISMATCH`. Network attempts were zero, replay was zero-work, DB integrity was `ok`, foreign-key violations were zero, cleanup and lease release completed, and all downstream capability/long-window locks remained zero.

## Exact reconciliation defect

The final reconciliation proves:

- stage-reported request IDs: `1..16`;
- manifest request IDs: `1..16`;
- exact transport identity completeness: `OK`;
- transport identity blockers: none;
- transport identity count: `20`;
- strict durable campaign-scope IDs: only `1..12`.

Holder request IDs `13,14,15,16` are real persisted GoPlus `safety_reference` requests with complete holder transport identities, but they are outside the canonical campaign request scope.

Exact categories:

- `CURRENT_STAGE_REQUEST_OUTSIDE_CAMPAIGN_SCOPE` for `13,14,15,16`;
- `MANIFEST_REQUEST_NOT_DURABLE` for `13,14,15,16`.

This is not a 16-request-versus-20-transport defect. Governed request count and underlying transport-operation count remain intentionally independent.

## Root cause

The canonical permanent campaign request scope is already built and validated in `AuthoritativeLiveOperationalCampaignOwner.run_operational()` from exact invocation identities. Its `request_key_root` is supplied to discovery/front-door work and later reused by strict reconciliation.

The holder funnel does not receive that root.

`AuthoritativeLiveOperationalCampaignOwner._evaluate_holder_eligibility()` calls `_collect_preclose_context()` with a synthetic step containing:

- `run_id = command.run_id`;
- `step_key = holder_eligibility_<ordinal>`.

`one_command_15m_factory._collect_preclose_context()` then hardcodes:

`request_prefix = f"{step['run_id']}:{step['step_key']}:context"`

and persists holder requests below that unrelated namespace.

The fixed backup owner `execute_solana_rpc_holder_backup()` independently hardcodes the same legacy run/step namespace for its request key, so a repair must cover both primary holder collection and the sole permitted backup without weakening fallback law.

The frozen rows reproduce this exactly. Discovery/front-door IDs `1..12` begin with the canonical root `v2-9-8b-window15m-20260807T203017Z-6fa6b33284fd`, while holder IDs `13..16` begin with `20260807T203017Z-6fa6b33284fd-campaign-run:holder_eligibility_<n>:context:safety`.

## Correct ownership boundary

The campaign-scope owner remains the already-built validated `CampaignSourceRequestScope`. Reconciliation must not be widened after the fact and holder IDs must not be whitelisted.

The repair must propagate the existing canonical request-key root into holder request construction before each governed holder call. Legacy/default `_collect_preclose_context()` callers must preserve their existing run/step keys unless an explicit campaign root is supplied.

## Money-usefulness contribution

Exact holder provenance can then remain inside the same campaign ownership boundary as discovery and market evidence, allowing truthful holder context to reach the 15-minute lifecycle gate without weakening evidence or accounting rules.

## What this lane improves

- exact durable campaign ownership for holder source requests;
- request/stage/manifest set equality at the pre-lifecycle gate;
- fallback-safe holder provenance under the same campaign root.

## What this lane does not unlock

No new C8 attempt, operational `WINDOW_15M` memory growth, `WINDOW_1H+`, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL.

## Required proof before completion

Deterministic offline RED must reproduce that a permanent holder request created by the current code falls outside the exact `CampaignSourceRequestScope`. GREEN must prove primary GoPlus and the sole holder backup both use request keys inside the canonical root, strict reconciliation reports exact durable/stage/manifest equality and exact transport completeness, and existing non-campaign preclose callers retain their legacy key contract.

## Functionality Risks / Setbacks / Efficiency Blockers

1. Changing reconciliation or widening prefix matching would hide ownership defects and is forbidden.
2. Reconstructing a second campaign root inside holder code risks drift; propagate the existing validated root instead.
3. The backup seam has an independent request-key builder and must receive the same propagated root.
4. A later C8 attempt may expose another downstream blocker; this audit does not pre-authorize unrelated repairs.
