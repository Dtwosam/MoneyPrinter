# V2-9.8B auth fec30eaa pre-holder duplicate measured-transport forensic closeout

## 1. Execution and application identity

| Field | Value |
| --- | --- |
| Verdict | `V2_9_8B_AUTH_FEC30EAA_PRE_HOLDER_DUPLICATE_MEASURED_TRANSPORT_FORENSIC_CLOSEOUT_PASS` |
| Authorized repository binding / audited HEAD | `376f9fe1a952c7aadd5e3a1c17e574fd3dc822b1` |
| Authorization | `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260903T215031Z_fec30eaa` |
| Frozen authorization SHA-256 | `a3747c27779881823e2475bac8b155eeee43f189bb7d824037b996ee13031b78` |
| Execution / campaign / run / Cycle 1 | `20260903T220426Z-d312c7b4308f` / `20260903T220426Z-d312c7b4308f-campaign` / `20260903T220426Z-d312c7b4308f-campaign-run` / `20260903T220426Z-d312c7b4308f-cycle` |
| Wrapper child | PID `34383`; exit `1`; `CHILD_EXITED_NONZERO` |
| Terminal classification | `OPERATIONAL_COMMAND_BLOCKED`, phase `CAMPAIGN_PRE_LIFECYCLE`, `HolderBudgetError:PRE_HOLDER_DUPLICATE_MEASURED_TRANSPORT_IDENTITY` |
| Wrapper counters | `source_calls=12`, `scheduler_runtime_calls=0`, `database_writes=6`, `lifecycle_started=null`, cleanup complete, lease released, marker consumed |

This is a read-only post-run reconstruction.  The consumed authorization remains permanently non-reusable irrespective of the nonzero child exit.

## 2. Exact 12-call source timeline

The durable `source_request` relation contains exactly 12 rows for this execution, with 12 distinct request IDs and 12 distinct request keys.  This exactly corroborates the wrapper's `source_calls=12`.

The first eleven request keys are under the typed canonical campaign root
`v2-9-8b-window15m-20260903T220426Z-d312c7b4308f`.  Request `4811` is instead under the bare temporal refresh root `20260903T220426Z-d312c7b4308f-refresh-1-...`.  Thus every row is durably attributable to the same execution/campaign, but **not** every row is owned by the current typed campaign request-key root: 11 are under that root and the twelfth is under the bare temporal root.

`K#` below expands to the canonical measured-transport tuple:
`(stage_family, source, request_kind, method_or_endpoint, within_request_ordinal, target_category, target_identity)`.

| # | source request / request key | source, method/endpoint, logical stage / sequence | request timestamp; response or failure; terminal / quality | response SHA; normalized rows; measured transports |
| --- | --- | --- | --- | --- |
| 1 | `4800` / `v2-9-8b-window15m-20260903T220426Z-d312c7b4308f-locator` | `dexscreener`; `GET /token-profiles/latest/v1` plus pair lookup; initial discovery / 1 | `22:04:27.311232Z`; response `4386`; complete / clean | `1fc1ce4c59d5175623ce932bd39aea84a25d66d283cdb641482e02ce0619a9a6`; 20; 2 (`K1`, `K2`) |
| 2 | `4801` / `...-migration-page-live-tail` | `solana_rpc`; `getSignaturesForAddress`; direct Pump nomination / initial sequence 1 | `22:04:28.822024Z`; response `4387`; complete / clean | `4dddaf8d41d5d8e68d986fc40f641cb278e1b1f1c1bc5257503ed9f9ccc4064c`; 0; 1 (`K3`) |
| 3 | `4802` / `...-gt-new-pools` | `geckoterminal`; `GET /api/v2/networks/solana/new_pools`; fresh-pool nomination / 1 | `22:04:29.552368Z`; response `4388`; complete / clean | `56db01f26f2d5a62731aefc9fd3265febe503b5e21eba564352d33e2a30c1472`; 20; 1 (`K4`) |
| 4 | `4803` / `...-liq-backup-geckoterminal-gccLs46L-54Yx2ZpP` | `geckoterminal`; `GET /api/v2/networks/solana/tokens/{mint}/pools`; unknown-liquidity backup / 1 | `22:04:30.432263Z`; response `4389`; complete / clean | `49abf10a42129a8b0ede260626dd30674e6126770a002e3b6ee43cd740dbfa86`; 1; 1 (`K5`) |
| 5 | `4804` / `...-liq-backup-geckoterminal-5zLj8k5j-...` | `geckoterminal`; same endpoint; unknown-liquidity backup / 2 | `22:04:31.340255Z`; response `4390`; complete / clean | `505785b4b6c5473f221bd6631c7488c72863cd85ba21b9d685e002a1eb2283e6`; 1; 1 (`K6`) |
| 6 | `4805` / `...-liq-backup-geckoterminal-9v2ygfKu-...` | `geckoterminal`; same endpoint; unknown-liquidity backup / 3 | `22:04:32.604021Z`; response `4391`; complete / clean | `f145c787d666a5a152727d0cdaba1c98237d492eb35b82780689d6a339f9ccad`; 1; 1 (`K7`) |
| 7 | `4806` / `...-liq-backup-geckoterminal-APYUbpY2-...` | `geckoterminal`; same endpoint; unknown-liquidity backup / 4 | `22:04:33.573547Z`; response `4392`; complete / clean | `0e82e74852bba188b394a6501ae0182436fe2318b9d36d2c728c4a98f05effe6`; 1; 1 (`K8`) |
| 8 | `4807` / `...-liq-backup-geckoterminal-AcysC2rT-4LQbSRsU` | `geckoterminal`; same endpoint; unknown-liquidity backup / 5 | `22:04:34.486321Z`; failure `414` at `22:04:34.990722Z`, `geckoterminal_rate_limited`; stale / stale-data | none; 0; 0 |
| 9 | `4808` / `...-liq-backup-geckoterminal-AsPNmktT-6gPp5SQy` | `geckoterminal`; same endpoint; unknown-liquidity backup / 6 | `22:04:34.992324Z`; failure `415` at `22:04:35.551258Z`, `geckoterminal_rate_limited`; stale / stale-data | none; 0; 0 |
| 10 | `4809` / `...-protocol-1` | `solana_rpc`; `getMultipleAccounts`; protocol confirmation / 1 | `22:04:35.557067Z`; response `4393`; complete / clean | `1854b0a2c1b7a57420c6b491163535d93182062258db9b2f09d438db0c5be9ce`; 15; 1 (`K9`) |
| 11 | `4810` / `...-mint-batch-r1` | `dexscreener`; `GET /tokens/v1/solana/{mints}`; market discovery / round 1 | `22:04:36.162836Z`; response `4394`; complete / clean | `ae97351d051cba2466383389f67a54f1c1281fc52bce8e0abfea7245897d9012`; 1; 1 (`K10`) |
| 12 | `4811` / `20260903T220426Z-d312c7b4308f-refresh-1-pump-migration-page-live-tail` | `solana_rpc`; `getSignaturesForAddress`; direct Pump nomination refresh / sequence 2 | `22:14:27.304005Z`; response `4395`; complete / clean | `4dddaf8d41d5d8e68d986fc40f641cb278e1b1f1c1bc5257503ed9f9ccc4064c`; 0; 1 (`K3`, duplicate) |

The colliding responses have the exact same full SHA-256 shown in the table.  The remaining canonical keys are:

| Key | Canonical identity tuple and target |
| --- | --- |
| `K1` | `DEXSCREENER_DISCOVERY`, `dexscreener_profiles`, `dexscreener_fresh_profiles`, `GET /token-profiles/latest/v1`, ordinal 1, `fresh_profiles`, null |
| `K2` | `DEXSCREENER_DISCOVERY`, `dexscreener_pair`, `dexscreener_fresh_profiles`, `GET /tokens/v1/solana/{mints}`, ordinal 2, `token_pairs`, null |
| `K3` | `DIRECT_PUMP_NOMINATION`, `solana_rpc`, `restored_pump_migration_signature_page`, `getSignaturesForAddress`, ordinal 1, `pump_migration_withdraw_authority_page`, `27m9co5M6RLMFdHXzJz6ktUvN9Dm3GAmttmNrqvnEnjN|before=HEAD` |
| `K4` | `FRESH_POOL_NOMINATION`, `geckoterminal`, `geckoterminal_new_pool_discovery`, `GET /api/v2/networks/solana/new_pools`, ordinal 1, `fresh_solana_pools`, null |
| `K5`–`K8` | `MINT_MARKET_BATCH`, `geckoterminal`, `candidate_market_batch`, `GET /api/v2/networks/solana/tokens/{mint}/pools`, ordinal 1, `mint_pool_reconciliation`, respectively `gccLs46LvPfoKxvfqYR3Quj6mcDq54q5hB3UEdGpump`, `5zLj8k5jN2WsYbV1HQWt3mCnsBH43t7LyU5vVxHtpump`, `9v2ygfKuP9fUpUoC9kNQcXzCjer2upMmrasCkXMapump`, `APYUbpY2ADMNSVKPHTHukwMSsHNhgUJFr4tzyTezpump` |
| `K9` | `PROTOCOL_CONFIRMATION`, `solana_rpc`, `pumpswap_pool_account_batch`, `getMultipleAccounts`, ordinal 1, `pumpswap_pool_batch`, durable normalized target `5M2GCe6gTDuKxnRMyYeREzDkN9G2eeKzuE64b4R2xGrt,9tbdxKNvAXz9FnsQ6xMMoPDgaJ2dw5WCnpjPytxorUKH,EBt9vHYKdgAFjr9naCaQi5KSPZ7yvd3V7fufbLAFU6Rb,5CUk3C2Kb7MFwauoH4Hmoe2a6jwcC9PiF2UY4V9PPrum,D9QQa3hqeUpxDJGxHLMd9tWVPTTAkb6cN799RWYZnBfx,6YqXaDGjUHJq9cEZ6fdoU2FnMA6r2kUYAKN8bckxGa7B,2EZS2o3RsnPfnfMSjnaP9NAaEHAcdQwhEB8ETTVFdven,6mzcNGCnGAqyYEy9DxyHpaj79KoPK5iU36px8ZyfhFBM...(+7)` |
| `K10` | `MINT_MARKET_BATCH`, `dexscreener_pair`, `candidate_market_batch`, `GET /tokens/v1/solana/{mints}`, ordinal 1, `due_mints`, `12u9FULaUfHD8uHHe98Fz5gdhg8qeX6DyV93B3Dtpump,2XzK878GKk8TaiVakJWrvDKgdBDTqxW2X8iG3Xuwpump,3zh9CTwPf8vvPrM5xBWmdkzpWRbmRJyvYo46fZBVpump,5iRB5xMpnxvuwvfgkFffQ6V7ToLRhbtGtt3BYjpkpump,AQi9C9ak1TKTse3kSFKANybEhZmaVpTab1ukhsEhpump,AkYnWBir16eq79PR21Xr3n2d2Q6aasGAofTKyfZVpump,Av2cD8GQT5dnCiC2cav2X37hs9z2mbBSxAMGkRbwkdt2,CrR3AB6W9v2RV9btV9Egqsdij3jXNUSJba9dqKAqpump,DqLouq9H8qafpeQUxmma5ZhxRrnFFQvHShrzD31pump,FWAXQDB3jsKqTMbFmsXBTYeCvfMjPskSMw5DJT9Ddz8,UUdfUfhkqWEQK9wqADgQTQSbE4qpNkNaeCZdjPPpump,kvNhejuJ9cG8fSiaLfdNff1c4RZPHfQwbNWSk6Vpump` |

## 3. Exact duplicate identity pair

The exact collision is `K3`:

```text
(DIRECT_PUMP_NOMINATION, solana_rpc,
 restored_pump_migration_signature_page, getSignaturesForAddress, 1,
 pump_migration_withdraw_authority_page,
 27m9co5M6RLMFdHXzJz6ktUvN9Dm3GAmttmNrqvnEnjN|before=HEAD)
```

| Occurrence | Request / response | request key; stage / sequence | source payload and relation |
| --- | --- | --- | --- |
| first | `4801` / `4387` | typed canonical root `...-migration-page-live-tail`; direct Pump nomination / initial 1 | `solana_rpc`, `getSignaturesForAddress`, ordinal 1, target above; `22:04:28.822024Z`; response SHA `4dddaf8d...`; `cursor_before=null`, `cursor_used=false`, `signature_count=0`, empty signatures |
| second | `4811` / `4395` | bare refresh root `20260903T220426Z-d312c7b4308f-refresh-1-pump-migration-page-live-tail`; direct Pump nomination refresh / 2 | same source, method, ordinal, target, response SHA, and transport payload; `22:14:27.304005Z` |

There are exactly two occurrences.  They are different durable source requests and different durable response IDs, but byte-identical responses with the same response SHA.  They are different stage sequences, not the same request or response represented twice.  The request keys differ, which does not make their canonical transport identities different.

## 4. Pre-holder accounting reconstruction

The production path was:

```text
campaign discovery
-> stage evidence / action-local measured-transport observer
-> CampaignSixUnitOwner.ingest_stage_evidence
-> source-request reconciliation and manifest construction
-> campaign and action-local measured transport sets
-> build_pre_holder_budget_snapshot
-> HolderBudgetError
```

At the audited HEAD, the relevant owners are:

| Responsibility | Owner at audited HEAD |
| --- | --- |
| Canonical transport identity | `src/printer_v1/discovery/measured_transport.py:170-228`, `canonical_measured_transport_identity` |
| Direct Pump source request and transport observation | `src/printer_v1/discovery/direct_migration_discovery.py:939-967,1008-1027,1043-1067` |
| Source-request reconciliation / manifest | `src/printer_v1/discovery/permanent_discovery_availability.py:4680-4782,4895-4980,5270-5538` |
| Action-local aggregation | `src/printer_v1/operator_cli/operational_memory_factory_command.py:3735-3762` |
| Six-unit owner ingestion | `src/printer_v1/discovery/campaign_six_unit_accounting.py:560-790` |
| Pre-holder projection and snapshot call | `src/printer_v1/operator_cli/operational_memory_factory_command.py:3422-3440,4503-4582` |
| Snapshot duplicate check / raise | `src/printer_v1/discovery/holder_reliability_budget_control.py:233-246,292-436` |

The source manifest under the typed canonical root had 11 governed request rows, 10 successful measured identities, and no duplicate identity.  The successful action-local observer had 11 raw transport entries but only 10 unique keys because it received `K3` twice.  `CampaignSixUnitOwner` atomically rejected the second stage ingestion before committing it, so its retained ledger had 10 unique transports.  The pre-holder snapshot received that unique campaign set plus the raw action-local set; `_exact_transport_keys` correctly raised on the raw action-local duplicate.

This is not a manifest concatenation, retained-evidence recount, or snapshot-created duplication.  The duplicate existed in a second provider transport before snapshot assembly.

## 5. First incorrect owner

The first incorrect owner is the initial temporal-refresh owner binding in
`src/printer_v1/operator_cli/operational_memory_factory_command.py:1854-2015`, specifically the initial composition call at `2009-2015`.

It supplied bare `execution_id` as `owner_request_key_prefix` to the initial Cycle-1 temporal refresh owner, rather than the typed canonical root derived for the campaign.  In `src/printer_v1/discovery/pre_lifecycle_refresh_composition.py:197-295,447-506`, `cycle_pump_live_tail_head_already_completed` consequently searched the bare root.  At refresh time that root had no prior Pump response: request `4801` belonged to the typed root.  The helper returned false and the direct Pump producer made request `4811`.

The production chain is therefore:

```text
initial temporal-refresh owner uses bare execution-id root
-> completed Pump HEAD transport is invisible to the refresh guard
-> direct Pump producer performs request 4811
-> K3 is observed a second time
-> six-unit owner rejects second ingestion; raw action-local evidence remains duplicate
-> pre-holder duplicate guard blocks the campaign
```

## 6. Historical duplicate comparison

Disposition: `PARTIAL_MECHANISM_RELATION`.

It is not the Sep-1 `MINT_MARKET_BATCH` cooperative-resume replay: this run duplicated a Pump signature-page transport, not a due-mint market batch.  It has the same high-level Pump `before=HEAD` replay shape as the Sep-3 Cycle-2 incident, but it occurred in initial Cycle-1 temporal-refresh composition.  The Sep-3 repair's completed-tail check was reached here as generic code, but its lookup was given the wrong initial-cycle root.  This is neither proof of a regression in the repaired Cycle-2 path nor live proof of that path.

## 7. Holder guard verdict and budget distinction

Verdict: `PRE_HOLDER_DUPLICATE_GUARD_CORRECT`.

The error is `DUPLICATE_ACCOUNTING_INTEGRITY_BLOCK`, not `HOLDER_CONTEXT_BUDGET_EXHAUSTED`.  Snapshot construction stopped at the duplicate check; no holder campaign-operation ledger was constructed.

| Accounting value | Reconstructed value |
| --- | --- |
| All durable governed source requests | 12 |
| Typed-root request count passed to pre-holder reconciliation | 11 |
| Raw action-local measured transports before duplicate check | 11 |
| Unique measured transports | 10 |
| Retained six-unit transports | 10, unique |
| Manifest transports | 10, unique |
| Zero-transport validation charge | 9 |
| Snapshot reservations | 2 and 4 |
| Hypothetical remaining capacity absent the integrity block | `45 - (10 + 9) - 2 - 4 = 20` |

`CampaignSixUnitOwner` disposition is `SIX_UNIT_LEDGER_UNIQUE__DUPLICATE_INTRODUCED_LATER`: the second real transport reached the independent action-local measurement path, but six-unit ingestion rejected it atomically rather than retaining a duplicate.  No guard relaxation, silent deduplication, identity mutation, or ceiling change is justified.

## 8. Provider causality

Requests `4807` and `4808` recorded GeckoTerminal rate-limit failures, each with zero measured transports.  They are real provider limitations but did not cause the terminalization.

The colliding Pump calls were both actual governed `solana_rpc` calls.  The second was an avoidable replay, its request key differed, its payload was `BYTE_IDENTICAL` (and therefore semantically identical), and it had no cursor/change or protocol-real new meaning.  Provider disposition: `PROVIDER_LIMITATION_PRESENT_BUT_NOT_CAUSAL`.

## 9. Recent-repair live-exercise disposition

The four-token 118 repair was `NOT_LIVE_EXERCISED_THIS_RUN`: lifecycle did not start, `scheduler_runtime_calls=0`, no lifecycle factory run or step was created, and no pre-4H token-ceiling enforcement was reached.

The Cycle-2 Pump refresh repair was also `NOT_LIVE_EXERCISED_THIS_RUN` in its required Cycle-2 sense: no Cycle 2 was created, admitted, or refreshed.  Its reusable helper was invoked during Cycle 1, but that is not Cycle-2 live proof and exposed this distinct initial-root propagation gap.

## 10. Campaign objective outcome

Cycle-1 discovery started and generated the 12 calls.  The record does not establish a frozen four-candidate observation universe; no holder stage, freeze, Cycle-1 admission, Cycle-2 attempt, lifecycle window, token slot, or lifecycle scheduler work was created.

One pre-lifecycle discovery-refresh scheduler job (`3763`) existed and terminalized failed with `PRE_LIFECYCLE_REFRESH_INTERNAL_INVARIANT:SIX_UNIT_STAGE_EVIDENCE_DUPLICATE_TRANSPORT:DUPLICATE_TRANSPORT_IDENTITY`.  It is not lifecycle Scheduler runtime work.  There are no campaign memory, episode, or fingerprint rows attributable to an admitted lifecycle, and no hidden lifecycle progress.

## 11. Cleanup and canonical zero-state

Read-only canonical zero-state projection after terminalization reported zero active Scheduler jobs, factory runs, factory steps, campaigns/runs/cycles, campaign Scheduler work, discovery work, pre-admission attempts, pre-lifecycle waits/work, campaign supervision, proof supervision, and unreleased acquisition/campaign leases.  Attempt-specific counts for windows, slots, campaign objects, factory runs, and steps are also zero.

The terminal historical rows remain retained; none were deleted or changed.  The child-reported cleanup completion and lease release are independently consistent with the durable canonical projection.

## 12. Consumed authorization and non-reuse

The external one-shot marker is present and binds this exact authorization and frozen SHA.  Its SHA-256 is
`e79ea08080ecc66f2b7eda17ee5fe7cedb7f5a311f5d40bbf13a7f617af8d1c8`.

The marker records one allowed invocation and consumption at `2026-09-03T22:04:23.181640+00:00`, with automatic retry, manual rerun, resume, restart, and successor all false.  The authorization is `CONSUMED`, `NON_REUSABLE`, `MARKER_PRESENT`, `NO_RETRY`, `NO_RERUN`, `NO_RESUME`, `NO_RESTART`, and `NO_SUCCESSOR`.

The frozen authorization's authoritative prior non-reuse root contains 60 IDs.  Future derivation must include this consumed `fec30eaa` ID as well, yielding an expected 61-ID future root; that count is a derived governance result, not manually forced.

## 13. DB integrity and identity

Before this read-only audit, the authoritative DB SHA-256 was
`9ac31309c4f7a6233bc9f5d77944f88cd15a16a1659f98db665524f18dcb7a23` and its size was `162635776` bytes, matching the child's immediate post-run report.  SQLite was opened read-only for reconstruction.  `PRAGMA integrity_check` returned `ok` and `PRAGMA foreign_key_check` returned no rows.

The SHA and size were remeasured after the audit and remained exactly the same.  There is no DB identity drift and no audit-caused mutation.

## 14. Primary classification

`UPSTREAM_TRUE_DUPLICATE_TRANSPORT_PRODUCER_DEFECT`

The defect is not provider scarcity, a canonical identity defect, manifest aggregation, or a pre-holder accounting-design defect.  It is the initial owner-to-refresh-guard scope propagation error that allowed a second actual provider transport with no new meaning.

## 15. Repair feasibility — audit only

`NARROW_REPAIR_FEASIBLE`

| Question | Forensic answer |
| --- | --- |
| First incorrect owner | Initial temporal refresh composition in `operational_memory_factory_command.py` |
| Minimum production file | `src/printer_v1/operator_cli/operational_memory_factory_command.py` |
| Existing durable state reusable | Yes: current typed campaign source-request root and completed source-request/response evidence |
| Schema change | No |
| Source Governor change | No |
| Scheduler change | No |
| CampaignSixUnit change | No |

The bounded design must propagate the typed canonical campaign request root into the initial Cycle-1 temporal refresh owner so the existing completed-tail proof suppresses the second production call.  It must preserve the canonical identity and the fail-closed holder guard.

## 16. Exact next lane

`PRE-HOLDER DUPLICATE MEASURED TRANSPORT REPAIR — DESIGN / SPECIFICATION`

This closeout does not authorize implementation, a new authorization, an application marker, a rerun, a retry, a resume, a restart, a successor, Printer execution, providers/RPC/WebSockets, or Scheduler operation.
