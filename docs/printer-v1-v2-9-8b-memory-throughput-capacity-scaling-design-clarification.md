# Printer V1 V2-9.8B Capacity Scaling Design Clarification

This clarification is additive to `docs/printer-v1-v2-9-8b-memory-throughput-capacity-scaling-design.md` and does not change its approved architecture.

## Exact clarification

The design's `3 cycles / 6 tokens` ceiling is a **simultaneous through-4h concurrency ceiling**, not the total number of cycles one 24-hour intake session may ever admit.

For the approved first 24-hour throughput target:

```text
simultaneously active two-token cycles <= 3
simultaneously active through-4h tokens <= 6
whole-session two-token cycle admissions <= 15
whole-session new-token admissions <= 30
```

Completed cycles remain immutable historical/audit evidence but no longer consume the simultaneous active-cycle ceiling. While intake remains open, their released pair capacity may be reused by later monotonically identified cycles.

The existing `CampaignCeilings.cycle_count` is a finite **whole-session** ceiling. It must not be misused as the simultaneous active-cycle limit when the operational coordinator is generalized. A 24-hour session targeting up to 30 new tokens may therefore have `cycle_count=15` while a separate scaling policy permits no more than three of those cycles to be active at once.

The session enters bounded drain when either:

- the requested intake deadline is reached; or
- the whole-session cycle-admission ceiling is consumed.

Drain never creates another cycle even if simultaneous capacity becomes free.

## Ownership constraint confirmed during implementation review

The current campaign run has one authoritative factory-run binding. Therefore multi-cycle concurrency must **not** be implemented by starting independent two-token lifecycle runners/factory runs for each active cycle under the same campaign run.

The implementation must generalize the existing single factory-run service loop/ownership mapping to carry several cycle-scoped token identities, while preserving one campaign, one campaign run, one authoritative factory run, one Central Scheduler, one Source Governor, and one supervised command process.

This clarification does not authorize runtime capacity above two, any live proof, 12h/24h runtime, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, PnL, paid APIs, retries, provider-ceiling changes, or independent campaign processes.