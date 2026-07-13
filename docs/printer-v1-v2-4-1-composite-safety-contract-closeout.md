# Printer V1 V2-4.1 Composite Safety Contract Closeout

Status: `DESIGN GATE STOPPED`

Verdict: `V2_4_1_COMPOSITE_SAFETY_CONTRACT_BLOCKED`

This lane remained inside V2-4.1. It performed static design verification only.
It did not begin V2-5, modify runtime code, add a migration, fetch a source,
mutate a database, or run a proof.

## Scope Read

The audit used the active Printer source stack, the V2-4.1 memory-quality and
safety closeouts, and the relevant local Solana Builder modules for Source
Governor evidence, Solana RPC, transaction parsing, SPL Token, Token-2022,
Pump.fun bonding-curve behavior, and PumpSwap pool confirmation.

Unsupported provider and pool semantics are recorded as
`UNKNOWN_REQUIRES_RESEARCH`.

## Bounded Composite-Provenance Design

A future implementation may add one versioned safety composite per exact
token, pair, snapshot, and memory window. The representation must be bounded
to the approved safety sources and contain:

- exact `token_id`, mint, `pair_id`, pair address, snapshot ID, memory-window
  ID, evaluation time, and policy version;
- one contribution per governed source, with source name, request kind,
  request ID, response ID or failure ID, requested and received timestamps,
  source status, data-quality label, freshness result, and exact fields used;
- a field-binding map that identifies the contribution responsible for every
  normalized safety field;
- a conflict list, missing-evidence list, and final categorical policy result;
- a fixed source/contribution ceiling so the structure cannot become an
  unbounded evidence graph.

Every referenced response must belong to its referenced request and source.
Every field must match the exact mint, and pair-specific evidence must also
match the exact selected pair. A missing trace, identity mismatch, stale or
failed mandatory contribution, or unsupported field claim fails closed.

Sources do not silently overwrite one another. If two fresh exact-target
sources produce incompatible categorical evidence, the composite records
`SAFETY_EVIDENCE_CONFLICT` and blocks clean promotion. A partial source failure
does not discard valid independent evidence, but it leaves every field owned
by the failed contribution unresolved.

## Holder-Concentration Design

The approved existing paths can support holder evidence:

- GoPlus may provide the live `holders` shape plus `total_supply`;
- governed Solana RPC may provide `getTokenLargestAccounts` plus
  `getTokenSupply` as the fallback.

The calculation must validate the exact requested mint, a finite positive
supply, non-negative holder balances, and fresh complete provenance. It then
computes the sum of the ten largest balances divided by validated supply. The
existing categorical boundaries remain unchanged:

- below 55 percent: `HOLDER_CONCENTRATION_HEALTHY`;
- 55 percent through 80 percent: `HOLDER_CONCENTRATION_CONCENTRATED`;
- above 80 percent: `HOLDER_CONCENTRATION_EXTREME`;
- invalid, incomplete, failed, stale, or mismatched evidence:
  `HOLDER_CONCENTRATION_UNKNOWN`.

The RPC path is a fallback when GoPlus cannot establish the field. If both
fresh exact-mint paths are available and disagree categorically, the result is
a blocking conflict. Known concentrated or extreme evidence remains blocking
under the requested unified contract.

## Provider Risk And Unified Safety Policy

Explicit provider risk flags must retain their exact source field, value, and
governed contribution trace. Missing provider coverage remains unknown; an
explicit known risk remains blocking.

The shared resolver and first-memory review must own one effective safety
contract before E2Q and Lane K run. E2Q and Lane K must consume the resulting
window quality rather than reinterpret safety. Mandatory authority, supply,
token-program, freshness, trace, and target failures remain blocking. Optional
unavailable evidence remains honestly unknown. Genuine chart
`CHART_CONTEXT_DO_NOT_TRAIN` remains an independent blocker.

## Exact-Pool LP Design Blocker

Gate 1 requires one pool type with authoritative proof rules for
`LP_LOCKED`, `LP_BURNED`, `LP_UNLOCKED`, and `LP_STATE_UNKNOWN`.

No approved local source contract currently meets that requirement:

- PumpSwap confirmation proves the exact pool account owner and exact base
  mint, but its full account layout, including the LP-mint field, remains
  `UNKNOWN_REQUIRES_RESEARCH`;
- the Pump.fun bonding-curve contract describes launch and migration behavior,
  not an exact post-migration LP custody or burn contract;
- the SPL Token and Token-2022 modules intentionally do not adopt transfer,
  burn, custody, or lock interpretation for pool LP tokens;
- the live GoPlus pool fields do not have an adopted exact-pair semantic
  contract, and unmatched token-level pool IDs cannot prove LP state;
- no approved Raydium or Orca exact-pool LP layout and authority contract is
  present in the active source stack.

Without a verified LP mint, exact pool attribution, custody or locker account,
burn destination, and unlock-authority rule, the four states cannot be
distinguished safely. Treating `burn_percent`, `locked_percent`, UI labels, or
unmatched pool IDs as proof would invent undocumented provider semantics.

All current pool types therefore remain `LP_STATE_UNKNOWN`. This is the exact
Gate 1 blocker.

## Gate Outcome

Because no supported pool type can be adopted from the approved source stack,
Gate 1 did not pass. Gates 2 and 3 were not entered. No code, tests, migrations,
source calls, scheduler work, proof databases, memory, retrieval, or financial
rows were created.

The smallest safe next V2-4.1 lane is an operator-approved, source-authority
research and design lane for one exact pool type. It must pin an authoritative
pool layout and define LP-mint identity, lock custody, burn proof, unlock
authority, freshness, exact-pair attribution, and governed evidence recording.
Only after that contract passes may the composite provenance, holder fallback,
LP normalization, and unified safety consumers be implemented together.

V2-5 remains blocked.
