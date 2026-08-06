# Printer V1 V2-9.8B WINDOW_15M DexScreener Orientation Binding Repair Closeout

## Verdict

`V2_9_8B_WINDOW_15M_DEXSCREENER_ORIENTATION_BINDING_REPAIR_PASS`

This is an implementation and disposable-proof closeout only. No authorization
was created, renewed, applied, or consumed. No memory lifecycle, discovery run,
Source Governor work, Central Scheduler work, campaign, retry, or provider
contact occurred. The authoritative database and all prior failed-run evidence
remain unchanged.

## Baseline and branch

| Item | Value |
| --- | --- |
| Required baseline branch | `agent/v2-9-8b-window-15m-exact-market-member-binding-repair` |
| Required full starting HEAD | `4d28255d565b9cac827dcba6532b82f68284d41e` |
| Repair branch | `agent/v2-9-8b-window-15m-dexscreener-orientation-binding-repair` |
| Commit subject | `Repair WINDOW_15M DexScreener orientation binding` |
| Consumed authorization (preserved, not reused) | `V2_9_8B_WINDOW_15M_AUTH_20260805T224959Z` |
| Failed execution evidence (preserved, not mutated) | `20260805T225258Z-63f2d6d9da75` |

The starting tracked tree and index were clean. Existing untracked operator-run
evidence packages were preserved and were not staged.

## Exact root cause

The prior exact same-member market matcher treated DexScreener `candidate_mint`
as an accepted base-token identity without consulting orientation status.

The DexScreener normalizer can emit a pair where the requested token is only the
quote side:

```text
base_mint = OTHER_TOKEN
token_mint = OTHER_TOKEN
quote_mint = TARGET_TOKEN
candidate_mint = TARGET_TOKEN
candidate_pair_orientation_status = FAIL
candidate_pair_orientation_reason = BASE_QUOTE_ORIENTATION_MISMATCH
```

Because `candidate_mint` was added to base identities unconditionally, a
quote-only target could still satisfy exact-member mint+pool binding and pass
retained market activation.

## Actual normalized DexScreener failure shape

From `normalize_dexscreener_fixture_result` in `src/printer_v1/sources/dexscreener.py`:

- `token_mint` / `base_mint` always come from `baseToken.address`
- when a requested mint list is present, `candidate_mint` may equal the quote
  mint if only the quote side matched the request
- orientation is then set to:
  - `PASS` only when `candidate_mint == base_mint`
  - otherwise `FAIL` with reason `BASE_QUOTE_ORIENTATION_MISMATCH`

The retained matcher must honor that orientation contract and must not promote a
FAIL `candidate_mint` into base identity.

## Corrected orientation authority rules

Applied only to the normalized DexScreener contract:

1. Explicit base identities remain authoritative when they agree:
   - `base_mint`
   - `token_mint`
   - `baseToken.address`
   - legacy single-member `mint` where present
2. `candidate_mint` is accepted as base only when all hold:
   - `candidate_pair_orientation_status == "PASS"`
   - `candidate_mint` is non-empty
   - `candidate_mint` equals the explicit base identity
   - `candidate_mint` is not quote-only
3. When orientation is `FAIL`, missing, empty, or non-PASS:
   - do not add `candidate_mint` to base identities
   - if the target is present as quote on the matching pool, return
     `MARKET_RESPONSE_TARGET_IS_QUOTE_ONLY`
4. Fail closed with `MARKET_RESPONSE_ORIENTATION_CONFLICT` when:
   - `PASS` but `candidate_mint` differs from explicit base
   - explicit base fields disagree with each other
   - target appears in both base and quote positions on the same member
   - `PASS` while reason indicates mismatch
   - `PASS` without an agreeing explicit base identity

GeckoTerminal members do not require DexScreener orientation fields and continue
to use explicit base/quote field extraction only.

## Typed fail-closed blockers

| Condition | Blocker |
| --- | --- |
| Quote-only target, including FAIL orientation candidate_mint on quote | `MARKET_RESPONSE_TARGET_IS_QUOTE_ONLY` |
| Contradictory orientation / base field authority | `MARKET_RESPONSE_ORIENTATION_CONFLICT` |
| No exact same-member mint+pool base match | `MARKET_RESPONSE_NO_EXACT_MEMBER_MATCH` |
| Exact mint+pool member missing Solana (market-nominated) | `MARKET_ADMISSION_SOLANA_CONFIRMATION_MISSING` |
| Duplicate exact same-member matches | `MARKET_RESPONSE_CONFLICTING_MEMBER_MATCHES` |
| Unsupported payload shape | `MARKET_RESPONSE_UNSUPPORTED_SHAPE` |
| WSOL / USDC / USDT selected mint | `INFRASTRUCTURE_MINT_EXCLUDED` |

## Preserve all prior repairs

Confirmed preserved:

- exact same-member mint/pool/Solana binding
- `MARKET_PRESENT_POOL` / `DIRECT_PUMP_PUMPSWAP`
- conditional retained-evidence roles
- market/market, Pump/Pump, mixed two-slot support
- WSOL/USDC/USDT exclusion via `SOLANA_INFRASTRUCTURE_MINTS`
- exact request/response hashes, transport ownership, campaign/run/cycle
  ownership, freshness checks, zero-new-source-row reconciliation
- Source Governor and Central Scheduler ownership

Confirmed still absent:

- universal PumpSwap registry membership after selection
- `SELECTED_MINT_NOT_IN_REGISTRY` (zero production/test matches)
- post-selection registry lookup
- Pump origin requirements for DexScreener / GeckoTerminal candidates
- synthetic migration / graduation / registry evidence
- scoring, ranking, confidence, weighting, or source preference

## Files changed

Implementation:

- `src/printer_v1/discovery/memory_observation_activation.py`

Tests:

- `tests/test_v2_9_8b_window_15m_dexscreener_orientation_binding_repair.py` (new)

Documents:

- this closeout

No schema migration was required or added.

## Focused tests and results

All runtime tests used disposable temporary databases and fixture payloads.
No provider was contacted.

| Proof | Result |
| --- | --- |
| 1. FAIL orientation quote-side candidate_mint is quote-only | PASS |
| 2. `BASE_QUOTE_ORIENTATION_MISMATCH` quote-side case is quote-only | PASS |
| 3. Valid base-oriented PASS orientation member passes | PASS |
| 4. PASS candidate disagreeing with explicit base → orientation conflict | PASS |
| 5. Disagreeing explicit base fields fail closed | PASS |
| 6. Target in both base and quote fails closed | PASS |
| 7. Explicit base without candidate_mint still passes | PASS |
| 8. Failed-run-shaped DexScreener candidate still passes | PASS |
| 9. Valid GeckoTerminal member unchanged | PASS |
| 10. Valid direct Pump candidate unchanged | PASS |
| 11. Cross-member / Solana-missing / duplicate / unsupported still fail | PASS |
| 12. WSOL / USDC / USDT exclusions remain active | PASS |
| 13. No registry lookup, registry row, or new source row | PASS |

Commands/results:

- new orientation tests + prior exact-member + source-specific admission +
  retained-evidence exactness:
  `60 passed in 14.29s`;
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

This closes a quote-side orientation loophole that could admit a market member
whose only target hit was the quote mint plus a FAIL `candidate_mint`. WINDOW_15M
memory activation now requires DexScreener base authority to be orientation-true:
either an agreeing explicit base identity, or a PASS `candidate_mint` that matches
that base. Quote-side and contradictory orientation rows fail closed before any
retained market role is accepted.

## What this improves

- DexScreener base/quote orientation is now binding authority, not decorative
  metadata;
- FAIL orientation can no longer promote quote-side `candidate_mint` into base
  identity;
- contradictory PASS / base / quote field combinations fail closed with a typed
  blocker;
- GeckoTerminal and prior exact-member repairs remain intact.

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
| Risk that historical Dex fixtures without orientation metadata regress | Mitigated: explicit base fields remain sufficient; nearest exact-member and source-specific tests still pass |
| Risk that GeckoTerminal is over-constrained by Dex orientation fields | Mitigated: orientation handling is DexScreener-scoped only |
| Residual operator risk | Fresh one-use `WINDOW_15M` authorization must not be created until operator inspection of this commit |

## Exact next step

Operator inspection of the actual repair commit on branch
`agent/v2-9-8b-window-15m-dexscreener-orientation-binding-repair` before any
fresh one-use `WINDOW_15M` authorization.
