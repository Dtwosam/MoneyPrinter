# Printer V1 V2-9.7E.41 — Graduation-Only Selection and Mixed-Channel Discovery Closeout

## Verdict

`V2_9_7E_41_GRADUATION_ONLY_MIXED_DISCOVERY_PASS`

The graduation-only tracking law is implemented and proved offline: the
900-second gate is absent from FULL_PILOT and intact in SNAPSHOT_READINESS, no
ungraduated token can enter active selection, exact PumpSwap graduation is
mandatory, latest-only selection is prevented when non-latest candidates exist,
every adopted/permitted channel is wired, unavailable channels remain honestly
`SKIPPED_BLOCKED_CONTRACT`, and the focused offline proof passes.

## Starting commit

`00355fea8ae1093dd981b97d487094116b53be36` (`Close continuous full-pilot session
at attempt ceiling`).

## Ending commit

This closeout + repair (`Repair graduation-only mixed discovery admission`). No
tag.

## Frozen product law

**PRINTER V1 GRADUATION-ONLY TRACKING LAW.** Printer may discover and retain
source evidence about a Pump.fun token before graduation, but must never select,
activate, track, create a lifecycle for, or generate memory about it while it
remains on the bonding curve. A token becomes selection-eligible only after exact
governed evidence confirms graduation and binds its exact mint to one valid
post-graduation PumpSwap market identity. There is no minimum token-age or
post-graduation waiting period. Age is context; graduation is mandatory
eligibility.

## Money-usefulness contribution

Printer's value is a clean memory corpus of *tracked, tradeable* Solana
memecoins. Before E.41 the operational full pilot could admit and track
pre-graduation bonding-curve tokens by age alone — tokens with no AMM market,
which cannot be realistically entered or exited and would poison the corpus with
unrealistic setups. E.41 makes graduation (a real, confirmed PumpSwap market)
mandatory for tracking, so every candidate that reaches a memory window is a
token that actually trades on a confirmed post-graduation venue. That is a direct
improvement to the realism and cleanliness of the money-machine's memory, and it
removes a class of fake/fragile setups at the source.

## What this repair improves

- FULL_PILOT admits candidates by exact PumpSwap graduation, not by age. A
  one-second-old confirmed graduated token is eligible; a bonding-curve token of
  any age is not.
- The executor selection authority (`LIFECYCLE_MARKET` gate + `_select`) fails
  closed on every discovery-only lifecycle state, so no ungraduated token can be
  selected, activated, tracked, or generate memory.
- PumpSwap confirmation is per-mint and rebinds the tracking market identity to
  the confirmed post-graduation pool (exact `base_mint == mint`, owner == adopted
  program, unique-or-fail).
- The persistent pool separates pending-discovery origins (never selectable) from
  a graduation-gated pilot export.
- A frozen categorical two-slot rule prevents latest-only concentration without
  any scoring, ranking, weighting or popularity.
- Blocked graduated-discovery channels remain honest and visible; none is
  silently activated; no paid dependency is added.

## Exact operational discovery channels (after this repair)

| Channel | Operational state |
|---|---|
| PumpSwap on-chain confirmation (`pumpswap`) | **OPERATIONAL** — graduation confirmation authority (confirmation-only; needs a migration signature / locator) |
| Direct Pump.fun on-chain (`solana_rpc`, `LATEST_PUMPFUN`) | **OPERATIONAL for pending discovery only** — pre-graduation bonding-curve creates; never selectable |
| DexScreener (`dexscreener`) | **OPERATIONAL** for exact-market activity enrichment; cannot assert origin/graduation alone |
| GeckoTerminal trending/active | `SKIPPED_BLOCKED_CONTRACT` (fixture-only contract not repaired) |
| Solana Tracker trending/top | `SKIPPED_BLOCKED_CONTRACT` (free-REST contract not adopted) |
| PumpPortal migration feed | `SKIPPED_BLOCKED_CONTRACT` (requires incompatible wallet/funds state) |
| Persisted graduated candidates | OPERATIONAL owner, currently empty (no graduated evidence persisted yet) |

## What remains unavailable

No channel currently supplies **already-graduated** Pump.fun tokens for fresh
live discovery without a migration-signature locator. The direct channel is
pre-graduation; the trending/top graduated-discovery channels remain blocked by
their own contracts (BL-41-04). Consequently a cold-start live FULL_PILOT honestly
blocks with `BLOCKED_INSUFFICIENT_GRADUATED_POOL`. When confirmed graduation
evidence is supplied (an adopted graduated-discovery channel with live origin +
PumpSwap verification, or an operator migration-signature locator), the executor's
verification machinery admits and selects lawful graduated candidates and the
lifecycle proceeds — proved offline by the executor/driver/operational suites
running on graduated candidates.

## Functionality Risks / Setbacks / Efficiency Blockers

- **Risk:** graduated-candidate supply is not yet operational for fresh
  discovery; the correct behavior is an honest block, but no memory is produced
  until a graduated-discovery contract is adopted or a locator supplied.
- **Setback:** the E.40 persistent-pool maturity mechanism is superseded; its age
  export no longer feeds selection. This is intended — it was supplying unlawful
  ungraduated candidates.
- **Efficiency blocker:** PumpSwap confirmation needs a migration signature to
  resolve the pool; without an adopted migration-event feed (PumpPortal blocked),
  graduated discovery depends on operator-supplied locators.
- **Risk:** the categorical two-slot rule only diversifies when non-latest
  graduated categories are genuinely available; with a single category it
  degrades honestly (reported, not fabricated).

## Tests and proof

New: `tests/test_v2_9_7e_41_graduation_only_mixed_discovery.py` (16 tests) proves
the 18 required properties — graduation classification (1s graduated eligible;
bonding-curve ineligible at 1s/900s/1h/any age; migration-observed-without-
confirmation, ambiguous, wrong-owner, mint-mismatch fail closed); selection
graduation-only defense-in-depth; valid post-graduation market identity;
categorical two-slot (no two latest-only; deterministic seeded uniform; round-
robin non-latest; multi-channel duplicate no boost; single-category honest
degrade); SNAPSHOT_READINESS 900s intact; FULL_PILOT graduation-only terminal
with the maturity symbol removed; blocked channels visible; no forward WINDOW_15M
substitution; FK/integrity ok; zero forbidden-capability deltas.

Updated (directly affected): `test_v2_9_7e_40_full_pilot_admission.py`,
`test_v2_9_7e_40b_persistent_candidate_pool.py`,
`test_v2_9_7d_7b_4d_combined_discovery_executor.py`,
`test_v2_9_7d_7b_4d_1_atomic_two_slot_handoff.py`,
`test_v2_9_7d_7b_5_isolated_combined_discovery_proof.py`,
`test_v2_9_7e_8_origin_to_lifecycle_integration.py`,
`test_v2_9_7e_11_authoritative_live_operational_campaign.py` — all now exercise
lawful graduated candidates.

Regressions run (all pass): E.41 (16), E.40 admission + persistent pool (13),
combined discovery 7B.4d (9) / 7B.4d.1 (8) / 7B.5 (11 + 3 subtests), E.36–38
snapshot maturity (16 + subtests), E.5 pump origin, E.6 create classification,
PumpSwap confirmation suites, E.8 origin-to-lifecycle (14), E.14 pilot-runner
safe-stop (13), E.11 authoritative operational.

## Zero-unlock verification

No retrieval, paper decision, position, trade event, trade audit, episode, or
memory window is created by any blocked full pilot; foreign-key and integrity
checks pass; all forbidden-capability deltas are zero. No BUY/SELL/HOLD, no PnL,
no wallet/keys/signing/funds, no paid API, no scoring/ranking/confidence/weighted
logic, no embeddings/vectors, no Source Governor or Central Scheduler bypass. The
5m window remains support-only. No live pilot, live source, pilot authorization,
or persistent-DB mutation occurred in this lane.

## Readiness for another continuous full-pilot session

- **Correctness:** ready — the graduation-only law is enforced end-to-end and
  proved offline. A cold-start pilot will block honestly instead of tracking
  unlawful bonding-curve tokens.
- **Productivity:** NOT ready to produce a tracking pilot from fresh discovery —
  no operational graduated-discovery channel supplies confirmed graduated
  candidates (BL-41-04). A productive session requires either (a) an adopted
  graduated-discovery channel with live origin + PumpSwap verification, or (b) an
  operator-supplied migration-signature locator feeding confirmed graduation into
  `run_operational(graduation_proofs=...)`.
- **Exact next action:** an operator decision — authorize a graduated-discovery
  contract adoption lane (GeckoTerminal repair / Solana Tracker free-REST /
  PumpPortal re-evaluation) or a migration-signature locator path, then a fresh
  full-pilot session. No further live pilot is started under this prompt.

## Permanent locks preserved

Solana-only; Solana memecoin-only; paper-only; no wallet/keys/signing/funds/
execution; no paid APIs; no scoring/ranking/confidence/weighted decisions; no
embeddings/vectors; no Source Governor or Central Scheduler bypass; 5m
support-only; no retrieval; no paper decisions; no BUY/SELL/HOLD; no positions/
trade events/paper audits/PnL; no live pilot in this prompt; no V2-9.7F / V2-9.8
or later work.
