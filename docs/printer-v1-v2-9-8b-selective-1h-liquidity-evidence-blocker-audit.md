# Printer V1 V2-9.8B Selective-1h Liquidity Evidence Blocker Audit

## Verdict

`V2_9_8B_SELECTIVE_1H_LIQUIDITY_EVIDENCE_AUDIT_PASS`

PASS means that the root cause of execution `20260728T202147Z-3c2735e39266` is proven from committed code, retained artifacts, and read-only database evidence. It authorizes neither implementation nor another operational proof.

## Scope and baseline

- Repository: `/Users/Dtwo1/Developer/MoneyPrinter`
- Required and inspected HEAD: `1edb5e9f0dae6499b6e51b404780f26fddb7d17f`
- Branch: `master`
- Starting worktree: clean
- Execution: `20260728T202147Z-3c2735e39266`
- Reported first terminal cause: `BLOCKED_INSUFFICIENT_GRADUATED_POOL`
- Inspection method: static source and contract inspection, retained artifact inspection, and SQLite opened read-only only
- No source call, discovery, Scheduler, campaign runtime, proof, retry, restart, successor, cleanup, migration, or database mutation was performed.

The active source stack was used, including `AGENTS.md`, the Clean Master Spec, the V2 memory-growth build order, the Python Builder Guide and its mandatory blocker-classification procedure, the V2-9.8B selective-1h audit/design/implementation/proof-command/operator-readiness closeouts, the first successful bounded-memory-growth closeout, the graduated-front-door and eligible-token-supply contracts, and the earlier insufficient-graduated-pool audit.

## Executive finding

The action failed closed at the correct safety boundary: Printer did not admit any candidate without fresh exact-pool liquidity evidence, did not start lifecycle or Scheduler work, and did not use earlier values as if they were current. That safety behavior is expected.

The reported explanation is not truthful enough. All 24 exact-pool liquidity operations failed in transport with the same retained error, `<urlopen error [Errno 65] No route to host>`. Those failures were durably linked to their source requests, but the eligible-supply owner did not count front-door liquidity failures as provider failures or mark `dexscreener_exact_pool_market` unavailable. The exhaustion certificate therefore recorded `provider_failures=0`, `channels_unavailable=[]`, and `BUDGET_EXHAUSTION`; the activation owner then reduced the result to `BLOCKED_INSUFFICIENT_GRADUATED_POOL`.

This is a mixed defect with one primary classification:

- **Expected fail-closed behavior:** rejecting candidates whose current exact-pool liquidity could not be established.
- **Reporting defect:** candidate reports discard the specific liquidity reason and source status and expose only `LIQUIDITY_UNPROVEN`.
- **Persistence defect:** request/response/failure rows are linked to each other, but neither the candidate evidence object nor floor/reserve state stores the relevant IDs; the exhaustion certificate also lacks its campaign/run/cycle/execution ownership in this execution.
- **Committed code defect (primary):** provider-failure and unavailable-channel aggregation ignores liquidity-stage failures, so source unavailability is classified and terminalized as insufficient graduated supply.

The operational trigger was a transport outage. The blocker that prevents an honest operational conclusion is `COMMITTED_CODE_DEFECT`.

## Retained execution evidence

The retained terminal summary and report establish:

- 24 candidates observed and validated;
- all 24 had confirmed PumpSwap pool identities;
- all 24 were rejected with `LIQUIDITY_UNPROVEN` and null report liquidity;
- 30 governed source requests and zero Scheduler calls;
- `run_status=NOT_STARTED` and no lifecycle start;
- no restart and no successor;
- 4h, 12h, and 24h remained locked.

The pre-campaign backup ends at source request 1364, response 1283, and failure 81. The retained post-execution database ends at request 1394, response 1285, and failure 109. The execution therefore added exactly 30 requests, two responses, and 28 failures.

### Exact source-operation ledger

| Request IDs | Count | Operation | Durable result |
|---|---:|---|---|
| 1365 | 1 | DexScreener fresh-profile locator | response 1284 |
| 1366 | 1 | PumpPortal migration collection, round 0 | response 1285 |
| 1367-1368 | 2 | PumpPortal migration collection, rounds 1-2 | failures 82-83, `pumpportal_no_valid_solana_events` |
| 1369-1370 | 2 | PumpSwap/Solana RPC graduation verification attempts | failures 84-85, `pumpswap_rpc_transport_error` |
| 1371-1394 | 24 | DexScreener exact-pair market snapshot, one per candidate | failures 86-109, `dexscreener_transport_failure` |

Only the last 24 operations are the per-candidate liquidity-enrichment calls. Together, the locator, discovery, verification, and exact-pair calls account for all 30 governed source operations.

The request rows themselves show the Source Governor decision as `COMPLETE/CLEAN_DATA`. That is not proof that an adapter call succeeded: the adapter response or failure is separately recorded after the governed request is admitted. The linked response/failure row is the authoritative source-operation outcome.

## Exact source-call and persistence path

1. `eligible_token_supply.py` invokes the committed combined graduated front door and supplies the shared campaign operation ledger/budget.
2. `graduated_liquidity_front_door.py` locates candidates, gathers PumpPortal evidence, verifies graduated pool identity through the committed verifier, and calls `enrich_pool_liquidity()` for each exact mint/pool.
3. `enrich_pool_liquidity()` creates a governed DexScreener `pair_market_snapshot` request containing chain, mint, and pool. It does not call the adapter outside Source Governor.
4. `execute_source_request_with_governor()` persists `printer_source_requests`, releases the database write lock for transport, calls the adapter, then persists either `printer_source_responses` or `printer_source_failures` with `source_request_id`.
5. The front door receives a `GovernedSourceExecutionResult`, extracts exact-pair liquidity if possible, constructs `LiquidityEvidence`, and upserts `printer_graduated_market_floor_state`.
6. The front door collects request IDs in the local `stage_request_ids` list, but `_dexscreener_ledger()` reduces them to request/response/failure counts before returning the front-door report.
7. `eligible_token_supply.py` converts front-door candidates, updates `printer_eligible_token_reserve`, creates an exhaustion certificate if capacity is unmet, and returns diagnostics.
8. The authoritative campaign owner sees fewer than two graduated candidates and emits the pre-lifecycle terminal `BLOCKED_INSUFFICIENT_GRADUATED_POOL`. Unified terminal reporting converts candidates again and writes only generic liquidity status/rejection information.

### Durable data locations

| Evidence | Current durable location | Missing ownership/lineage |
|---|---|---|
| Governed request | `printer_source_requests` | no request payload; no candidate, pool, action, campaign, run, or cycle columns |
| Normalized success/partial response | `printer_source_responses.source_request_id` | no direct candidate/action ownership |
| Failure | `printer_source_failures.source_request_id` | no direct candidate/action ownership |
| Latest floor attempt | `printer_graduated_market_floor_state` | no request/response/failure ID, failure reason, or campaign ID |
| Last reserve evidence and current eligibility | `printer_eligible_token_reserve` | no request/response/failure ID for the new validation attempt |
| Exhaustion conclusion | `printer_discovery_exhaustion_certificates` | this row has null campaign, execution, run, and cycle IDs |
| Terminal artifact | retained campaign report/terminal summary | no source request/response/failure IDs and no liquidity failure detail |

The source ledger does preserve request-to-response/failure linkage. Candidate linkage can be reconstructed here only because the request-key convention includes the mint and the floor/registry tables preserve the exact pool. That is not a visible or categorical action-local lineage contract.

## Source outcome categorization contract

| Source outcome | Adapter/governed persistence | Front-door liquidity category |
|---|---|---|
| Exact success | response row; exactly one Solana pair must match both mint and pool and carry a finite, non-negative USD liquidity value | `LIQUIDITY_PROVEN` at or above USD 3,000; otherwise `LIQUIDITY_BELOW_SELECTION_FLOOR` |
| Rate limit/stale source | normalized stale result and linked failure metadata | `LIQUIDITY_UNPROVEN`, detailed reason `LIQUIDITY_STALE_SOURCE` |
| Transport/auth/provider failure | linked failure row with the adapter failure type/message | `LIQUIDITY_UNPROVEN`, detailed reason `LIQUIDITY_SOURCE_<failure_type>` |
| Empty or partial provider result | partial response or normalized missing-field failure | `LIQUIDITY_UNPROVEN`; partial source status or missing critical fields remains fail closed |
| No exact pair / wrong chain / mint mismatch / pair mismatch / ambiguous pair | response may be technically successful, but exact identity extraction rejects it | `LIQUIDITY_UNPROVEN` with `LIQUIDITY_NO_EXACT_PAIR` or the exact mismatch/ambiguity reason |
| Parse/malformed payload | adapter-normalized failure such as `dexscreener_malformed_payload`, `dexscreener_malformed_fixture`, or missing-critical-fields failure | `LIQUIDITY_UNPROVEN`, detailed source-failure reason |

No fallback may use a different pair, a mint-wide aggregate, stale values, or a prior amount as current proof. That is the correct money-safety contract.

## Candidate-level evidence lineage

All 24 request/failure pairs below have failure type `dexscreener_transport_failure`, failure message `<urlopen error [Errno 65] No route to host>`, latest floor status `LIQUIDITY_UNPROVEN`, and null latest floor amount. Exact mint/pool identity is reconstructed by joining the request-key mint to the durable floor/registry identity.

| Request | Failure | Mint | Exact PumpSwap pool |
|---:|---:|---|---|
| 1371 | 86 | `2RL5JTQLLyee9a1FCkfN4iketJ68ErkWWExGbLf9pump` | `E4fjibQDYcT3RwPogD8mS21CvvGkT5zHS85WA1WPTAtG` |
| 1372 | 87 | `5o2WFRY9VeP5KJPbrwSnRqFFHMdh7ysUQzQkbr6apump` | `9hT4XDxyzTCgiiDEYmMMMRtn2sgDVAFBKBgNfTGZhXYZ` |
| 1373 | 88 | `12u9FULaUfHD8uHHe98Fz5gdhg8qeX6DyV93B3Dtpump` | `ECobcS1MSzzAnnzz89xjwRSEYsHAChB7DMbd3G25gwgc` |
| 1374 | 89 | `3dTTtUbXcc5h4Au5qJGihSrTANjUVhDwJtjSJtELYWiv` | `CmoZuGU2F3FpUYemmuAFhbsrJuu1w5jSSMeVBNX8GBqW` |
| 1375 | 90 | `FQmF2CL24Fnc8aGJmnJz9LPNqiqpNJTdqQuCftjEpump` | `DbDdSi2Z77Rw3DnBQ9SHQA8XHiQLpKfBGrFfNkH4NNT5` |
| 1376 | 91 | `2vLNEm6uNTPdAPWxG3sH88yG4ASExkHW5Q3VxF7rpump` | `7dWPGBBco1TogJeGZqsrMjYd9Pbwzq5v7FCfmZ6U8Baz` |
| 1377 | 92 | `2C3CURT1uZUdqxoxFcMGwbVevom1ETu6FNDcaaByDR7A` | `AR4eDzUGi3wfPJGwXSJMAXLN3Y49oBAD2srexBCorV59` |
| 1378 | 93 | `3BTSRa1YCd5FJsqBLckPokW6q7CfsqX8KjCHH7tQpump` | `5E8RamC5kqJZfHd7bpurjhdJDBhkK58tWAxr7g6fiy86` |
| 1379 | 94 | `AQi9C9ak1TKTse3kSFKANybEhZmaVpTab1ukhsEhpump` | `DoLYhEhEEuyXEMnLCAfCvou81Ymji2ouaYsm4AZMrchk` |
| 1380 | 95 | `EgjSyM3uYPW6kSxKHqFPW68qE2hE5n3mqCguNQBApump` | `Cj82tbMoHS9EhucEJuk2VKu48W6MghLQAeL27mhKFYFR` |
| 1381 | 96 | `Av2cD8GQT5dnCiC2cav2X37hs9z2mbBSxAMGkRbwkdt2` | `REUdyzJNhNYJbgxAWfjiicvcTsfSJhyd61oN1JhhJXo` |
| 1382 | 97 | `5iRB5xMpnxvuwvfgkFffQ6V7ToLRhbtGtt3BYjpkpump` | `DLV5eiRSvEESE5ZMPBgmZ7vSnK3igBZZvZDWhgHt9Bj2` |
| 1383 | 98 | `3sfFdfE3YmmCUjgKNqrsV2bKcUM1iAHAhB9GVDcYpump` | `8a3yNYDUpZeJBpRxrSVzgo9gyic18tz3VEgob5YRYaW9` |
| 1384 | 99 | `aQVkmuasVQoZoHurni4S3SvZS6MHc8LdyLhUV8spump` | `2nTeUoWwjooDLuiL7u3VTcGstnPmhMsfXtkzEx4KnJMn` |
| 1385 | 100 | `DqLouq9H8qafpeQUxmma5ZhxRrnFFQvHShrzD31pump` | `7vQ1QiN2UTerAEnh5GSWEeb8xRquKfAmYVkFakU7aQ7X` |
| 1386 | 101 | `ASmoyDqsuLedJHfUePWokcmitFmRGfx8gaNfT2dtpump` | `GukzrHwaobccHvjJNZ5chbq2L9FWF1URZLrjJ7TSAiUe` |
| 1387 | 102 | `23Z8qs4DhbEGk4qnQ8LQsWQ8RGy18VcFQgKYWgHvpump` | `6NgeXgkHr6YFsjit6KvC2H4USkFvPWPYbHXBATcz3jTu` |
| 1388 | 103 | `oFSAgcwQzVdhViiqdDm7K2Ri3d1KFTYeTg64p9Cpump` | `5t4LJ4HGPW2n8MSrtyw3XQ5xgRgBFyRsEMmRexp8t3eM` |
| 1389 | 104 | `CrR3AB6W9v2RV9btV9Egqsdij3jXNUSJba9dqKAqpump` | `A2MoynsjruNQqDjdRQKMq8xDbFtAecE198KjuVrMBeWu` |
| 1390 | 105 | `UUdfUfhkqWEQK9wqADgQTQSbE4qpNkNaeCZdjPPpump` | `7PZL3Fo1bHSkKiSymZsRHjhX4swn1n9WHvupQ4qQcnFR` |
| 1391 | 106 | `FWAXQXDB3jsKqTMbFmsXBTYeCvfMjPskSMw5DJT9Ddz8` | `7qTdcaGCwFEWpvjJxrfFLik4EjbfixQVx5FAyYM7oe4Z` |
| 1392 | 107 | `7S4XmHSx1NzNgZLzvNyppkk5AT8cG6GXVkzWoWeVpump` | `BDBBbdCfShqeP5vHqhadt6ng6dWbJwiE34mM3LTUBbpa` |
| 1393 | 108 | `4TtBLhik85ho3Yb8CHpLuDs1tyXaPu9GXqEQvci8pump` | `Hj4Q2VMJMFsH9inR41KDFa5gRhXW7cnYu9USPjot7BLj` |
| 1394 | 109 | `kvNhejuJ9cG8fSiaLfdNff1c4RZPHfQwbNWSk6Vpump` | `Ck3KcPz6JcHXWore7nLkPYuTJyDBdzBSYaEnU47gsHs8` |

## Why action-local lineage is not visible

The lineage is lost in three reductions:

1. `stage_request_ids` is used only to calculate the front-door count ledger. The IDs are not attached to `LiquidityEvidence` or returned candidates.
2. `_candidate_from_front_door_item()` retains `liquidity_status` and `liquidity_usd` but drops `LiquidityEvidence.reason` and `source_status`.
3. blocked-supply reporting emits the generic rejection `LIQUIDITY_UNPROVEN`; it has no schema fields for source request, response, failure, failure type, or failure message.

Consequently, the terminal artifact cannot distinguish transport failure from missing pair, malformed payload, stale evidence, ambiguity, or genuinely observed below-floor liquidity. The evidence is recoverable only through a forensic join across the source ledger and state tables.

## Floor and reserve state transitions

### Why all 24 floor rows ended as `LIQUIDITY_UNPROVEN`

Before the campaign, the affected floor-state population was:

- six mints with no floor-state row;
- ten with `LIQUIDITY_BELOW_SELECTION_FLOOR`;
- eight with `LIQUIDITY_PROVEN`.

For every evaluated mint, the exact-pair call returned a governed failure. `enrich_pool_liquidity()` therefore produced current-attempt evidence `LIQUIDITY_UNPROVEN`, amount null, with a detailed transport reason. `record_market_floor_state()` uses a mint-keyed upsert that replaces the current status, amount, last-check time, cooldown, and update time. It inserted the six missing rows and overwrote the other 18 rows. The result was 24 current floor rows at `2026-07-28T20:21:47.325894+00:00`, all unproven with null amounts.

This latest-attempt floor behavior is fail closed, but the state row itself does not explain why the new attempt was unproven or link to its source failure.

### Why three reserve rows retain proven values while being removed

The three reserve rows that were `ELIGIBLE_FRESH` before the action were:

| Mint | Retained last-proven USD | Last successful validation | New eligibility | New exclusion |
|---|---:|---|---|---|
| `12u9FULaUfHD8uHHe98Fz5gdhg8qeX6DyV93B3Dtpump` | 3,133.28 | `2026-07-28T17:47:36.058228+00:00` | `REMOVED` | `LIQUIDITY_UNPROVEN` |
| `2RL5JTQLLyee9a1FCkfN4iketJ68ErkWWExGbLf9pump` | 6,978.41 | `2026-07-28T17:47:36.058228+00:00` | `REMOVED` | `LIQUIDITY_UNPROVEN` |
| `5o2WFRY9VeP5KJPbrwSnRqFFHMdh7ysUQzQkbr6apump` | 9,532.85 | `2026-07-28T17:47:36.058228+00:00` | `REMOVED` | `LIQUIDITY_UNPROVEN` |

The eligible-supply owner first marks prior eligible reserve rows stale for the new campaign, then revalidates them. `mark_reserve_status()` changes eligibility status, exclusion reason, and update time only. It intentionally does not rewrite the last successful liquidity status, amount, or validation timestamp when the new attempt fails. The rows therefore mean: “last successful evidence was proven at the recorded amount, but the token is not currently eligible because fresh revalidation is unproven.” They do not mean that the cooldown was silently reactivated or that the old value counted toward current capacity.

The floor table and reserve table therefore express different axes:

- floor state: latest attempted liquidity result;
- reserve evidence: last successful liquidity fact plus current eligibility decision.

That distinction is safe but insufficiently explicit in the retained report.

## Freshness and expiry finding

Prior values were intentionally invalidated for current admission, but not by a measured general liquidity TTL.

- The graduated-front-door contract requires fresh, current-cycle, exact-pool liquidity evidence.
- Eligible supply marks every prior eligible reserve row stale at campaign start and requires revalidation before it may count toward the two-token capacity.
- The one-hour cooldown is a separate optimization for an observed `LIQUIDITY_BELOW_SELECTION_FLOOR` state. All cooldowns on the ten prior below-floor rows had expired before this execution, so those candidates could lawfully be checked again.
- Prior `LIQUIDITY_PROVEN` floor values have no committed “still fresh until” timestamp used to bypass campaign revalidation.

Therefore, no evidence-expiry bug explains the 24 exclusions. Freshness policy correctly refused to promote historical values after current transport failure. The defect is the missing lineage and false terminal classification, not the fail-closed freshness rule.

## Exhaustion certificate and terminal truthfulness

The retained exhaustion certificate is `exh-2d329240dfc4`. It records:

- required capacity 2, eligible reserve 0;
- 24 unique tokens, 24 fresh market checks, 24 rejections for `LIQUIDITY_UNPROVEN`;
- 30 operations used, zero remaining;
- five discovery rounds;
- `provider_failures=0`;
- `channels_unavailable=[]`;
- `shortage_classification=BUDGET_EXHAUSTION`;
- null campaign, execution, run, and cycle IDs.

The zero-provider-failure assertion contradicts failures 86-109. Static tracing explains it: `eligible_token_supply.py` increments `provider_failures` only when the discovery collection status equals `PROVIDER_FAILURE` and then identifies only `pumpportal_migration_stream` as unavailable. It never consumes the front door's `liquidity_failures`, individual `LiquidityEvidence.reason`, or source status when classifying shortage. Because the holder budget was spent on 24 failed exact-pool calls, the later budget override wins and the activation layer emits the generic insufficient-pool terminal.

`BLOCKED_INSUFFICIENT_GRADUATED_POOL` therefore does **not** truthfully distinguish source failure from actual insufficient liquidity in this execution. The evidence proves neither that the 24 pools were below USD 3,000 nor that the graduated market lacked two eligible tokens. It proves only that current liquidity could not be established before the governed source-operation budget was exhausted because the DexScreener route was unavailable.

First-terminal-cause preservation after the wrong classification worked correctly; terminal reconciliation did not rewrite it. The defect occurs before terminal persistence, where the categorical cause is chosen.

## Minimum safe next step

The next permitted lane is a documentation/design-only repair specification for the proven liquidity-evidence categorization and lineage defect, followed by an explicitly authorized narrow implementation lane using mocks and temporary databases only.

The minimum contract to design is:

1. carry canonical request/response/failure IDs, detailed liquidity reason, and source status from each exact-pair operation through candidate evidence and blocked reporting;
2. bind exhaustion evidence to campaign/execution/run/cycle ownership;
3. aggregate liquidity-stage provider failures and unavailable channels in the eligible-supply owner;
4. distinguish source availability failure, genuinely observed below-floor liquidity, exact-pair absence/ambiguity, stale evidence, parse failure, budget exhaustion, and true supply exhaustion without loosening fail-closed admission;
5. preserve the shared Source Governor, shared budget ledger, Central Scheduler boundary, current-cycle exact-pair requirement, and zero lifecycle start on insufficient current evidence.

No retry, live proof, provider substitution, stale-value reuse, migration, or manual state repair is justified by this audit.

## Money-usefulness contribution

The current fail-closed gate protects money usefulness by refusing to treat unknown exit liquidity as proven liquidity. That prevents dirty memory and unrealistic paper-profit evidence.

The categorization defect harms money usefulness and operational efficiency because a source outage is presented as a market-supply conclusion. It can cause an operator to misread infrastructure reachability as evidence about actual token liquidity, spend an entire governed holder budget without actionable evidence, and make candidate coverage statistics look economically meaningful when they are not. Precise lineage and categorical terminal causes are required before bounded memory growth can produce trustworthy operational evidence.

## What remains locked

This audit does not unlock or authorize:

- another selective-1h proof or any live source call;
- discovery, Scheduler, campaign, lifecycle, retry, restart, or successor execution;
- 1h runtime expansion, 4h or later windows;
- memory generation or promotion from this blocked action;
- retrieval, paper decisions, BUY/SELL/HOLD, positions, trade events, paper audits, or PnL;
- wallet, private-key, signing, transaction, or live-trading capability;
- paid sources, scoring, ranking, confidence, weighted logic, embeddings, or vectors;
- migration changes, historical-row cleanup, or mutation of `data/printer_v1.sqlite3`.

## Functionality Risks / Setbacks / Efficiency Blockers

- The terminal cause can currently misstate a provider outage as insufficient graduated supply.
- Candidate-level source lineage is not visible in action artifacts and requires forensic request-key/database joins.
- `printer_source_requests` does not retain the request payload, so exact pool ownership cannot be proven from that table alone.
- Floor state overwrites the last attempted value without preserving its source-failure ID or reason.
- Reserve state safely preserves last successful evidence but combines it with a later eligibility removal in a way that can be misread without a two-axis explanation.
- The exhaustion certificate is durable but action-orphaned here because all four ownership IDs are null.
- The operation spent the entire 30-call holder budget despite the same route-level failure recurring across all 24 liquidity calls. This audit does not authorize retries, circuit breaking, or budget-policy changes; any efficiency response requires its own approved design.
- Until the categorical repair is designed, implemented, and mock-proven, another live proof would remain unable to distinguish market shortage from source availability failure and is not permitted.

## Audit checks

- Confirmed exact baseline HEAD and clean starting worktree.
- Inspected retained terminal summary and campaign report.
- Compared the retained pre-campaign backup with the current database using read-only SQLite connections.
- Reconciled all 30 request IDs, two response IDs, and 28 failure IDs.
- Reconstructed all 24 mint/pool/request/failure lineages.
- Verified pre/post floor-state distribution and the three reserve-state transitions.
- Traced Source Governor, adapter normalization, evidence categorization, floor/reserve persistence, exhaustion classification, activation terminalization, and unified reporting statically.
- Confirmed zero Scheduler/lifecycle start and no restart/successor from retained artifacts.

No runtime or network-bearing check was executed.
