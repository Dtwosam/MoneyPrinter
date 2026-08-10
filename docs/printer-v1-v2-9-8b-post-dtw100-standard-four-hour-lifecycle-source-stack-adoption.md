# Printer V1 V2-9.8B Post-DTW100 Standard Four-Hour Lifecycle Source-Stack Adoption

## Adoption scope

This record accompanies:

- `docs/printer-v1-v2-9-8b-post-dtw100-standard-four-hour-lifecycle-current-state-audit.md`
- `docs/printer-v1-v2-9-8b-post-dtw100-standard-four-hour-lifecycle-policy-campaign-integration-design.md`

The approved amendment is narrow:

1. otherwise-valid activated tokens are observed through the 4h checkpoint;
2. 15m and 1h outcome/behavior/learning-need labels do not qualify continuation;
3. all exact identity, evidence quality, freshness, provenance, safety, continuity, Source Governor, Central Scheduler, campaign-health, cancellation, and bounded-resource gates remain fail-closed;
4. automatic continuation stops at 4h;
5. 12h/24h remain selective and locked;
6. `WINDOW_5M_MICRO_EVENT` remains support-only;
7. 4h real collection remains disabled until the later campaign-integration implementation, focused proof, closeout, and explicit operational rereadiness/activation gate pass.

## Current source-stack files to amend

- `AGENTS.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`
- `docs/printer-v1-assistant-active-build-order-anchor.md`

The Clean Master Spec does not impose the superseded selective 1h->4h rule and requires no change in this adoption.

Historical V2-9.7C/V2-9 designs, proofs, and closeouts are preserved as historical evidence and must not be rewritten to imply this later policy existed earlier.

## Non-unlock statement

This documentation adoption does not authorize implementation, change `WINDOW_4H.enabled_for_real_collection`, create Scheduler work, contact sources, mutate the authoritative DB, generate operational memory, create or consume an authorization, activate retrieval, create paper decisions, unlock BUY/SELL/HOLD, create positions/trades/audits/PnL, or add wallet/private-key/signing/real-funds/live-execution capability.

## Static acceptance gate

Adoption passes only if the four current policy/assistant anchors agree that:

- first-four-hour observation is standard only after hard gates pass;
- 4h is the automatic-stop boundary;
- 12h/24h remain selective/locked;
- real 4h collection is still separately locked;
- all permanent V1 restrictions remain unchanged.
