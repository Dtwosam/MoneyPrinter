# Printer V1 Post-RC Jupiter Paper Quote Realism Readiness Plan

## Status

This is a planning-only Post-RC document.

This is not Lane 7.
This is not a source adapter implementation.
This is not live quote collection.
This is not a paper decision task.

## Current Anchors

- `594eb42` — Add missing context source candidate evaluation
- `138adff` — Add fresh context validation report
- `0269bcd` — Fix clean context blocker review
- `5fffa5d` — Add Lane 6 longer window activation readiness

## Current Problem

Printer still has no clean memory.

Lane 7 remains blocked because:

- `clean_memory_count`: 0
- clean eligible memory: 0
- retrieval is blocked
- paper decisions are blocked
- paper positions remain 0
- paper trade events remain 0

## Remaining Context Blockers

The current unresolved blockers are:

- `chain_heat_label`: `SOLANA_UNKNOWN`
- `market_regime_label`: `UNKNOWN`
- `safety_status_label`: `SAFETY_UNKNOWN`
- `entry_realism_label`: `ENTRY_UNKNOWN`
- `exit_realism_label`: `EXIT_UNKNOWN`
- `flow_direction_label`: `FLOW_UNKNOWN`
- `flow_pressure_label`: `FLOW_UNKNOWN`

This document focuses only on:

- `entry_realism_label`
- `exit_realism_label`

## Why Jupiter Is Being Considered

Jupiter may help Printer understand whether a paper entry or paper exit is realistic.

It may help answer:

- Was there a route to buy?
- Was there a route to sell?
- Was slippage too high?
- Was price impact too dangerous?
- Was the route unavailable?
- Was the quote stale or failed?

This matters because Printer should not treat a paper result as realistic if the system could not realistically enter or exit.

## What Jupiter Can Help With

Jupiter may later help with:

- entry route availability
- exit route availability
- slippage realism
- price impact realism
- quote freshness
- route depth
- quote failure detection
- no-route detection

## What Jupiter Cannot Help With

Jupiter cannot solve:

- token safety/rug evidence
- Solana chain heat
- broad market regime
- buy/sell pressure by itself
- live execution
- wallet/private-key safety
- real fund movement

## Required Quote Evidence Later

Before implementation, Printer would need to know which Jupiter fields are available.

Candidate evidence fields may include:

- input mint
- output mint
- input amount
- output amount
- route availability
- route plan presence
- slippage basis points
- estimated price impact
- quote timestamp
- quote source status
- failed quote reason
- no-route reason
- quote freshness label
- token_id
- pair_id
- snapshot_id
- evidence window identity
- quote direction: entry or exit
- quote purpose: paper-only realism check

Exact field names must be verified against Jupiter documentation before implementation.

## Entry Realism Mapping

Jupiter may later help move:

- `ENTRY_UNKNOWN`

into safer categorical labels such as:

- `ENTRY_ROUTE_AVAILABLE`
- `ENTRY_ROUTE_UNAVAILABLE`
- `ENTRY_REALISM_CAUTION`
- `ENTRY_REALISM_UNKNOWN`

These must remain labels, not scores.

No confidence percentages, weighted logic, ranking, or buy score should be added.

## Exit Realism Mapping

Jupiter may later help move:

- `EXIT_UNKNOWN`

into safer categorical labels such as:

- `EXIT_ROUTE_AVAILABLE`
- `EXIT_ROUTE_UNAVAILABLE`
- `EXIT_REALISM_CAUTION`
- `EXIT_REALISM_UNKNOWN`

These must remain labels, not scores.

Exit realism should help Printer judge paper result realism. It must not imply live execution.

## Source Governor Requirements

Any future Jupiter quote request must go through Source Governor.

Future requirements:

- source request recorded
- source response recorded
- source failure recorded
- stale quote labeled
- failed quote labeled
- no-route result labeled
- quote linked to token/pair/snapshot/window
- quote marked paper-only
- memory engine must not call Jupiter directly
- paper decision engine must not call Jupiter directly
- no engine may create its own quote loop

## Central Scheduler Requirements

Any future Jupiter quote collection must go through Central Scheduler.

Future requirements:

- bounded quote request
- operator-approved manual proof first
- no continuous loop
- no runtime expansion unless roadmap-approved
- no source spam
- no direct paper decision unlock
- no direct BUY unlock

## Clean-Memory Gate Preservation

Jupiter quote evidence alone cannot make memory clean.

It can only help with entry/exit realism.

Clean memory must still require all critical context to be known and clean.

Unknown safety, market, chain, or flow context must still block clean memory.

Dirty memory must not enter retrieval.

No paper decision, BUY, position, or PnL is allowed without valid clean-memory-backed gates.

## Test Readiness Checklist

Before any Jupiter implementation, future tests should prove:

- route available fixture produces route-available labels
- no-route fixture produces route-unavailable labels
- stale quote fixture remains audit-only
- failed quote fixture remains audit-only
- missing quote remains unknown
- entry realism becomes known only from fresh linked quote evidence
- exit realism becomes known only from fresh linked quote evidence
- quote evidence alone does not unlock clean memory
- quote evidence alone does not unlock retrieval
- quote evidence does not create paper decisions
- quote evidence does not create paper positions
- quote evidence does not create trade events
- quote evidence does not create PnL
- dirty quote evidence remains blocked

## Non-Goals

This task does not:

- implement a Jupiter adapter
- call Jupiter
- fetch live quote data
- mutate the database
- create snapshots
- create context rows
- build memory windows
- run retrieval
- create paper decisions
- create paper positions
- create trade events
- create PnL
- unlock BUY
- start Lane 7

## Verdict

Jupiter is a valid future candidate for paper-only entry/exit realism evidence.

It should not be implemented yet.

Lane 7 remains blocked because clean memory still does not exist.

## Recommended Next Safe Task

The next safe task should be fixture-only schema/readiness design for paper quote evidence.

That task should define how quote evidence would be represented, linked, audited, and blocked when stale or failed.

It should not fetch live Jupiter data or implement the adapter yet.
