# Printer V1 V2-9.8B WINDOW_15M Exact Market Member Binding Repair Closeout

## Verdict

`V2_9_8B_WINDOW_15M_EXACT_MARKET_MEMBER_BINDING_REPAIR_PASS`

This is an implementation and disposable-proof closeout only. No authorization
was created, renewed, applied, or consumed. No memory lifecycle, discovery run,
Source Governor work, Central Scheduler work, campaign, retry, or provider
contact occurred. The authoritative database and all evidence from the prior
failed execution remain unchanged.

## Baseline and branch

| Item | Value |
| --- | --- |
| Required baseline branch | `agent/v2-9-8b-window-15m-source-specific-admission-retained-evidence-repair` |
| Required full starting HEAD | `2faea63b265edae105197da52608948920bcce59` |
| Repair branch | `agent/v2-9-8b-window-15m-exact-market-member-binding-repair` |
| Commit subject | `Repair WINDOW_15M exact market member binding` |
| Consumed authorization (preserved, not reused) | `V2_9_8B_WINDOW_15M_AUTH_20260805T224959Z` |
| Failed execution evidence (preserved, not mutated) | `20260805T225258Z-63f2d6d9da75` |

The starting tracked tree and index were clean. Existing untracked operator-run
evidence packages were preserved and were not staged.

## Exact root cause

Retained `MARKET_OBSERVATION` validation used whole-payload recursive
membership:

```text
mint exists somewhere in the response
AND
pool exists somewhere in the response
AND
Solana exists somewhere in the response
```

That does not prove the exact mint, exact pool, and Solana network belong to
the same normalized response member. A multi-member payload could therefore
contain:

```text
member A: target mint + another pool
member B: another mint + target pool
```

and incorrectly pass activation.

Separately, activation-boundary infrastructure-mint exclusion used a partial
local set that covered WSOL and USDC but omitted USDT.

## Old unsafe matching behavior

1. `_payload_matches_target` walked the entire JSON tree and accepted any mint
   leaf plus any pool leaf, regardless of member boundary.
2. `_payload_confirms_solana` walked the entire JSON tree and accepted any
   chain/network leaf labelled Solana, including values on unrelated members.
3. Those two independent whole-payload checks were combined for market
   admission, so cross-member composition was enough to pass.
4. Infrastructure exclusion at the activation boundary was incomplete relative
   to the canonical Solana infrastructure-mint set.

## Source-specific exact member shapes supported

### DexScreener

Match within one exact pair/member object from the normalized `pairs` list.

Accepted same-member field locations:

| Binding | Accepted fields |
| --- | --- |
| Pool / pair | `pair_address`, `pairAddress`, `pool`, `pool_address` |
| Target mint (base only) | `base_mint`, `token_mint`, `candidate_mint`, `mint`, `baseToken.address` |
| Quote mint (not target) | `quote_mint`, `quoteMint`, `quoteToken.address` |
| Solana identity | `chain`, `chainId`, `network` equal to `solana` / `solana-mainnet` / `sol` |

### GeckoTerminal

Match within one exact pool/member object from the normalized `pairs` list, or
from a supported `data` list/object carrying attributes and relationships.

Accepted same-member field locations:

| Binding | Accepted fields |
| --- | --- |
| Pool / pair | top-level `pairAddress` / `pair_address` / `pool` / `address`; `attributes.address` and peer pool fields |
| Target mint (base only) | `base_mint`, `token_mint`, `candidate_mint`, `mint`, `baseToken.address`, `attributes.base_token_address`, `relationships.base_token.data.id` (with optional `solana_` prefix strip) |
| Quote mint (not target) | `quote_mint`, `quoteToken.address`, `attributes.quote_token_address`, `relationships.quote_token.data.id` |
| Solana identity | top-level / attribute chain keys; `relationships.network.data.id`; resource `id` prefix `solana_` |

### Single-member retained envelope

Historical retained fixtures that store one already-bound identity object
without a `pairs` key remain accepted only when that one object itself carries
pool and mint identity fields. This is still exact same-member binding, not
recursive whole-response search.

## Exact fail-closed rules

| Condition | Blocker |
| --- | --- |
| No supported member simultaneously binds exact mint + exact pool | `MARKET_RESPONSE_NO_EXACT_MEMBER_MATCH` |
| Exact mint+pool member lacks Solana confirmation (market-nominated) | `MARKET_ADMISSION_SOLANA_CONFIRMATION_MISSING` |
| More than one exact same-member mint+pool(+Solana) hit | `MARKET_RESPONSE_CONFLICTING_MEMBER_MATCHES` |
| Unsupported source or non-contract payload shape | `MARKET_ADMISSION_SOURCE_UNSUPPORTED` / `MARKET_RESPONSE_UNSUPPORTED_SHAPE` |
| Target mint appears only as quote/infrastructure asset on the matching pool | `MARKET_RESPONSE_TARGET_IS_QUOTE_ONLY` |
| Selected mint is WSOL, USDC, or USDT | `INFRASTRUCTURE_MINT_EXCLUDED` |

No fallback to recursive whole-response mint/pool searching remains for
`MARKET_OBSERVATION`. Non-market retained roles still use the existing
whole-payload recursive helper only for their own non-market contracts.

## Infrastructure-mint exclusion source

Activation now imports and uses the canonical constant:

`printer_v1.discovery.permanent_discovery_availability.SOLANA_INFRASTRUCTURE_MINTS`

Covered addresses:

- WSOL `So11111111111111111111111111111111111111112`
- USDC `EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v`
- USDT `Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB`

No broader token-classification system was introduced.

## Preserve the successful prior repair

Confirmed absent / not reintroduced:

- universal PumpSwap registry membership after selection;
- `SELECTED_MINT_NOT_IN_REGISTRY` (zero production/test matches);
- post-selection registry query;
- Pump origin requirements for DexScreener or GeckoTerminal candidates;
- synthetic migration, origin, graduation, or PumpSwap evidence;
- source preference, ranking, scoring, confidence, or weighting.

Preserved:

- `MARKET_PRESENT_POOL` and `DIRECT_PUMP_PUMPSWAP` admission authorities;
- conditional retained-evidence roles;
- market/market, Pump/Pump, and mixed two-slot support;
- exact transport ownership;
- request/response hash validation;
- campaign/run/cycle ownership;
- observation-time validation;
- zero-new-source-row reconciliation;
- Source Governor and Central Scheduler ownership.

## Files changed

Implementation:

- `src/printer_v1/discovery/memory_observation_activation.py`

Tests:

- `tests/test_v2_9_8b_window_15m_exact_market_member_binding_repair.py` (new)

Documents:

- this closeout

No schema migration was required or added.

## Tests and results

All runtime tests used disposable temporary databases and fixture payloads.
No provider was contacted.

| Proof | Result |
| --- | --- |
| 1. DexScreener exact mint, pool, Solana in one pair passes | PASS |
| 2. GeckoTerminal exact mint, pool, Solana in one member passes | PASS |
| 3. Target mint in one member and target pool in another fails | PASS |
| 4. Target mint/pool together but Solana only in another member fails | PASS |
| 5. Target pool with target mint only as quote asset fails | PASS |
| 6. Conflicting duplicate matches fail closed | PASS |
| 7. Missing or unsupported member shape fails closed | PASS |
| 8. Existing valid failed-run-shaped DexScreener candidate passes | PASS |
| 9. Valid direct Pump candidate remains unchanged | PASS |
| 10. Market/market, Pump/Pump, and mixed activation still pass | PASS |
| 11. WSOL, USDC, and USDT each fail infrastructure exclusion | PASS |
| 12. No registry lookup or registry row creation | PASS |
| 13. No source rows created during retained activation | PASS |
| 14. Transport, response-hash, ownership, freshness remain fail-closed | PASS |

Commands/results:

- focused new tests + prior source-specific admission + retained-evidence
  exactness + clean-object integrity:
  `66 passed in 16.93s`;
- Python compilation of changed module: PASS;
- `git diff --check`: PASS;
- production/test search for `SELECTED_MINT_NOT_IN_REGISTRY`: zero matches.

## Authoritative DB identity before and after

| Field | Before | After |
| --- | --- | --- |
| size | `68366336` | `68366336` |
| SHA-256 | `5612556ce62074327524533ee8932203be129f19843afe4052da7dbb2f756e64` | `5612556ce62074327524533ee8932203be129f19843afe4052da7dbb2f756e64` |
| inode | `1230526` | `1230526` |
| mtime_ns | `1785970388921155893` | `1785970388921155893` |

Authoritative DB unchanged. Failed-run authorization and campaign evidence
packages remained untracked and untouched.

## Money-usefulness contribution

This repair prevents a false retained-market pass that would otherwise admit a
mint/pool pair never co-observed on Solana by the same source member. Activation
now only trusts market evidence when one exact DexScreener or GeckoTerminal
member simultaneously proves the target mint, the target pool, and Solana
identity. That keeps WINDOW_15M memory activation from building observation work
on cross-member coincidence and excludes infrastructure quote assets (including
USDT) at the same boundary.

## What this improves

- exact same-member market binding instead of recursive whole-payload search;
- source-contract-aware DexScreener and GeckoTerminal matching;
- clear typed fail-closed blockers for split, quote-only, conflicting,
  unsupported, and Solana-missing cases;
- complete canonical infrastructure-mint exclusion at activation.

## What remains locked

- no authorization create/apply/consume;
- no discovery, provider, Source Governor, or Central Scheduler execution;
- no campaign/memory lifecycle start;
- no registry-backed universal graduation assumption;
- no retrieval or financial capability unlock;
- no schema migration;
- no ranking, scoring, confidence, or source preference.

## Functionality Risks / Setbacks / Efficiency Blockers

| Item | Status |
| --- | --- |
| Risk that historical flat retained payloads without member identity fields fail | Mitigated by single-member identity-carrier envelope support; nearest retained/clean-object tests still pass |
| Risk that non-market retained roles regress | Non-market roles retain previous recursive helper; market roles only use exact member binding |
| Risk of circular import from infrastructure-mint constant | `SOLANA_INFRASTRUCTURE_MINTS` is imported from a module that only lazily imports activation helpers |
| Residual operator risk | Fresh authorization must not be created until operator inspection of this commit |

## Exact next step

Operator inspection of the actual repair commit on branch
`agent/v2-9-8b-window-15m-exact-market-member-binding-repair` before any fresh
authorization.
