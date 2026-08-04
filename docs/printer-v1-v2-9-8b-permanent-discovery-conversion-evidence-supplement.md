# V2-9.8B Permanent Discovery Conversion Evidence Supplement

Date: 2026-08-04

Lane: `V2-9.8B — Permanent Discovery Conversion Evidence Supplement`

Execution under audit: `20260804T141537Z-532b1da7ee51`

Audit mode: **read-only / static**. No production edits, providers, runtime, migrations, writes, discovery, Scheduler, or live attempts.

## Verdict

`V2_9_8B_PERMANENT_DISCOVERY_CONVERSION_EVIDENCE_SUPPLEMENT_PASS_ROOT_CAUSES_PROVEN`

All four conversion evidence gaps receive evidence-backed answers. One subordinate forensic detail remains: raw Pump `getTransaction` bodies were not retained after categorical rejection, so per-instruction mint counts cannot be re-decoded offline. The rejection rule, escalation path, and terminal classification defect are still proven without that body.

## Verified starting point

| Item | Value |
|---|---|
| Repository | `/Users/Dtwo1/Developer/MoneyPrinter` |
| Branch | `agent/v2-9-8b-post-rollover-2-exact-public-composition-scheduler-claim-coverage-audit` |
| Full HEAD | `c6b10ae9c57d9151271faaabfd20c2089e78ed17` |
| Short SHA | `c6b10ae` |
| Subject | `Close permanent discovery 15m attempt` |
| Tracked tree | clean |
| Untracked preserved | `operator-runs/v2-9-8b-authoritative-mig050/` (Migration-050 package) |
| `/private/tmp/mp-preclaim` | present; untouched |
| Authoritative migration head | `051_permanent_discovery_availability.sql` |

Gap source: the four unanswered conversion questions documented by the permanent-discovery WINDOW_15M attempt closeout for this execution (the named terminal-audit file path was not present on this HEAD; the closeout plus live artifacts supply the same four gaps).

## Evidence inventory and hashes

| Artifact | Path | SHA-256 |
|---|---|---|
| Terminal summary / child stdout | `/Users/Dtwo1/PrinterOperations/v2-9-8/20260804T141537Z-532b1da7ee51/terminal-summary.json` (identical content as wrapper `child-stdout.txt`) | `ac6e62f518a6a5bdaaa50e1ed24af2a97c2344d697a8c69b811c3816b511bd3d` |
| Campaign report | `.../reports/20260804T141537Z-532b1da7ee51-report.campaign-report.json` | `b9175a1b4bf235ab19856549790839b69b6911ac803d0bf802ad0cce81b5fa0d` |
| Authoritative DB (post-attempt) | `data/printer_v1.sqlite3` | `2a6184dc157431655e4b4bf757db78d368c27e317a35b6c2e75b864444494a56` |
| Wrapper terminal | `.../V2_9_8B_WINDOW_15M_AUTH_20260804T141128Z/wrapper-terminal.json` | `312b9bfdd5af4e994f7e0efe8c56e749dff46c6ba2b2b2394d413da824a21690` |
| Application marker | `.../application-marker.json` | `7b5111eabe55f5ed33d0327b216f6ec72c1c0cde983fbe709b147d12f6592f41` |
| Git provenance manifest | `.../git-provenance-manifest.json` | `53ec16558304f302c5b5170b01c55bfc9f244a2a9dabab012ffdbf212a0f1528` |
| Attempt closeout | `docs/printer-v1-v2-9-8b-permanent-discovery-window-15m-attempt-closeout.md` | (repo text) |
| Design / implementation | `docs/printer-v1-v2-9-8b-permanent-discovery-availability-design.md`, `...-closeout.md` | (repo text) |

Read-only DB access used URI `mode=ro`. Report/DB reconciliations:

| Fact | Report | DB |
|---|---:|---:|
| First terminal cause | `SOURCE_AVAILABILITY_FAILURE` | campaign/run/cycle `first_terminal_cause` same |
| Governed source requests | 12 | `printer_source_requests` ids 1877–1888 |
| Source failures | 2 | failures 197, 198 |
| CONTRACT_BLOCKED identities | 46 (closeout) | 46 exact-market rows |
| MARKET_READY reserve | 1 | 1 layer row |
| FULLY_ELIGIBLE reserve | 0 | 0 |
| Holder evidence attempts in window | 0 | 0 |
| Lifecycle / Scheduler | false / 0 | no factory run; no campaign windows |

## Chronological operation ledger

Flat discovery ceiling: **30**. Governed source-request accounting used by the exhaustion certificate: **12 used / 18 remaining**. Measured transport operations: **13** (DexScreener locator expands to two transports under one governed profile flow; transport ≠ request by contract).

Stage reservations (immutable, forward-only):

| Stage | Reserved |
|---|---:|
| intake | 3 |
| market_batching | 2 |
| reconciliation | 6 |
| protocol_confirmation | 7 |
| holder_safety | 8 |
| final_refresh_handoff | 4 |
| **total** | **30** |

### Ledger (chronological)

| Ord | Time (UTC) | Stage reservation charged | Request ID | Source / kind | Candidate identity | Op charged (request) | Flat rem after | Stage rem (reconstructed) | Transition / result | Lawful work still open after |
|---:|---|---|---:|---|---|---:|---:|---|---|---|
| 1 | 14:15:37.393 | intake | 1877 | dexscreener / `dexscreener_fresh_profiles` | fresh Solana profiles | 1 | 29 | intake 2/3 used→rem later | COMPLETE; broad nominations recorded `CONTRACT_BLOCKED` protocol-due | yes |
| 2 | 14:15:40.367 | intake (+1 synthetic in permanent intake block) + discovery ledger | 1878 | solana_rpc / `restored_pump_migration_signature_page` | Pump program `6EF8…F6P` | 1 | 28 | — | COMPLETE; 2 signatures nominated | yes |
| 3 | 14:15:41.176 | (discovery ledger; later stage-charged as protocol) | 1879 | solana_rpc / `restored_pump_migration_transaction` | sig `v5DuHZ…WTN3` | 1 | 27 | — | Transport complete; **validation FAIL** `exactly_one_migrate_instruction_required` → failure 197 | yes |
| 4 | 14:15:41.812 | (discovery ledger; later stage-charged as protocol) | 1880 | solana_rpc / `restored_pump_migration_transaction` | sig `2oVXpG…T3QS` | 1 | 26 | — | Transport complete; **validation FAIL** same rule → failure 198; channel `direct_pump_finalized_live_tail` marked unavailable | yes |
| 5 | 14:15:42.505 | intake | 1881 | geckoterminal / `geckoterminal_new_pool_discovery` | fresh Solana pools | 1 | 25 | intake full (3) | COMPLETE; more protocol-due broad rows | yes |
| 6 | 14:15:43.856 | market_batching | 1882 | dexscreener / `candidate_market_batch` | 30 due mints (batch) | 1 | 24 | market 1/2 | COMPLETE resp 1684; 1 market-ready, 13 below floor, 16 no-match, 6 alternate `POOL_CONTRACT_UNSUPPORTED` | yes |
| 7 | 14:15:50.819 | reconciliation | 1883 | geckoterminal / mint pools | `12u9FUL…pump` | 1 | 23 | recon 1/6 | COMPLETE | yes |
| 8 | 14:15:58.196 | reconciliation | 1884 | geckoterminal / mint pools | `23Z8qs…pump` | 1 | 22 | recon 2/6 | COMPLETE | yes |
| 9 | 14:16:05.333 | reconciliation | 1885 | geckoterminal / mint pools | `2vLNEm…pump` | 1 | 21 | recon 3/6 | COMPLETE | yes |
| 10 | 14:16:12.818 | reconciliation | 1886 | geckoterminal / mint pools | `3dQoup…Pump` | 1 | 20 | recon 4/6 | COMPLETE | yes |
| 11 | 14:16:19.707 | reconciliation | 1887 | geckoterminal / mint pools | `4G5y3x…pump` | 1 | 19 | recon 5/6 | COMPLETE | yes |
| 12 | 14:16:26.797 | reconciliation | 1888 | geckoterminal / mint pools | `4hi84N…pump` | 1 | 18 | recon 6/6 | COMPLETE; permanent round-1 market stage ends | yes (unexplored inventory + unused stages) |

After round 1, production charges `protocol_confirmation` with `max(0, discovery.source_requests - 1) = 2` and **advances** the stage cursor to `protocol_confirmation`.

Round 2 begins (`discovery_rounds` becomes 2) and attempts `stage_budget.advance("market_batching")`, which raises `BUDGET_STAGE_REWIND_FORBIDDEN`, caught as `DISCOVERY_OPERATION_BUDGET_EXHAUSTED`.

Shortage classifier then overrides to `SOURCE_AVAILABILITY_FAILURE` because `provider_failures=2` and `channels_unavailable=['direct_pump_finalized_live_tail']`.

### Terminal capacity snapshot

| Bucket | Value | Notes |
|---|---:|---|
| Flat used / remaining | 12 / 18 | certificate |
| Stage used (reconstructed) | 12 | intake3 + market1 + recon6 + protocol2 |
| Stage remaining | 18 | market1 + protocol5 + holder8 + handoff4 |
| Reserved but stranded behind cursor | 1 | unused `market_batching` unit (rewind-forbidden) |
| Reserved forward still on paper | 17 | protocol5 + holder8 + handoff4 |
| Reclaimable under approved forward-only policy | forward stages only; **not** prior-stage unused market unit without rewind repair | holder/handoff never entered |
| Queued but not executed | second mint-market batch; protocol confirmation of fresh nominations; holder/safety; final refresh/handoff | |
| Planner independent strand? | **Yes** — premature `protocol_confirmation` advance after first market batch forbids further `market_batching` despite remaining flat and stage capacity | |
| Shared terminal alone? | **Also yes** — even if market rounds continued, campaign terminalized on shortage and skipped holder because `graduated_candidate_count=1 < 2` | |

## A. Holder/safety activation trace

### Production path (static)

1. `run_persistent_eligible_token_supply` (permanent mode) builds market-ready survivors into the eligible/holder reserve; it does **not** call holder/safety.
2. Required permanent market-ready/eligible depth for supply readiness is `max(4, required_token_capacity)`.
3. `AuthoritativeLiveOperationalCampaignOwner` maps `holder_reserve_supply` → `graduated_candidates`.
4. **Hard gate** (`authoritative_live_operational_campaign.py`): if `len(graduated_candidates) < 2`, the campaign persists ledger, sets `holder_eligible_count=0`, and returns terminal **without** `_evaluate_holder_eligibility`.
5. Only when that gate passes does permanent mode call `_evaluate_holder_eligibility(... eligible_target=4)` and write `FULLY_ELIGIBLE` reserve rows.

### Market-ready mint/pool for this execution

| Field | Value |
|---|---|
| Mint | `12u9FULaUfHD8uHHe98Fz5gdhg8qeX6DyV93B3Dtpump` |
| Pool | `ECobcS1MSzzAnnzz89xjwRSEYsHAChB7DMbd3G25gwgc` |
| Exact state | `CURRENT_POOL_CONFIRMED` / `AT_OR_ABOVE_3000_FLOOR` |
| Liquidity | `$3192.3112` (request 1882 / response 1684) |
| Eligible reserve | `ELIGIBLE_FRESH`, campaign-bound |
| MARKET_READY layer | `ACTIVE`, reason `EXACT_POOL_CURRENT_AND_LIQUIDITY_FLOOR_PASS`, evidence expires `2026-08-04T14:45:37.381063+00:00` |
| FULLY_ELIGIBLE layer | **absent** |
| Holder attempts | **0** |
| `graduated_candidate_count` | **1** |
| `holder_eligible_count` | **0** |
| Stage reached (report) | `MARKET_ELIGIBLE` (not holder) |

### Exact condition that prevented evaluation

`len(graduated_candidates) < 2` with `graduated_candidates` drawn from the single market-ready/eligible survivor. Holder/safety was never invoked.

### Does code wait for four market-ready before evaluating any?

**No.** Proven behavior:

- Supply tries to **accumulate** four market-ready/eligible rows before declaring supply ready, evaluating market facts as they arrive inside the mint-batch path.
- Holder/safety is a **post-supply** campaign stage.
- The campaign gate is **two** graduation-confirmed candidates, not four.
- Permanent holder target of four applies only **after** the two-candidate gate opens.

So the one market-ready mint was not held back by a “wait for four before any holder eval” latch; it was blocked by the pre-holder two-candidate admission gate after supply returned shortage with depth 1.

### Classification

`EXPECTED_BY_APPROVED_DESIGN` for not reaching fully eligible selection without four survivors **and** for terminalizing without holder when supply already reports honest shortage.

`PROVEN_CODE_DEFECT` (composition, secondary): design text says holder/safety is called for market-ready survivors and continues until four fully eligible **or honest terminal**. The campaign’s hard `<2` gate means a solitary market-ready survivor never receives holder evaluation even when stage budget still reserves eight holder units and flat capacity remains. That is stricter than “call for market-ready survivors” and left the single survivor unevaluated.

Primary practical blocker for this execution remains insufficient market-ready depth (1 of 4) plus early terminalization, not a missing holder implementation module.

## B. Pump migration response analyses

### Shared request/response identities

| Item | Response 1 | Response 2 |
|---|---|---|
| Signature (locator page 1878 / response 1682) | `v5DuHZDrWj1RytiADZ3gf79wP3b9HAgMtx7VVKwrpY8tqzX7bR38VdSXwi9CiKiJPh8LMs23EE8WCNh3q4cWTN3` | `2oVXpG7VjBgNmXijy28tXhSLtjtCk9KAUHWrMowLn3XG2h56e9rMadtJnfhF1tBhXc826mnHnzmhuzRcwDNdT3QS` |
| Slot (page) | 437190052 | 437190052 |
| Transaction request ID | **1879** | **1880** |
| Failure ID | **197** | **198** |
| Transport | `getTransaction` COMPLETE enough to measure **5900** / **5904** response bytes | same |
| Durable response row | **none** (no `printer_source_responses` row for 1879/1880) | same |
| Failure type | `direct_pump_migration_rejected_exactly_one_migrate_instruction_required` | same |
| Failure message | `transaction is not the exact pinned Pump migrate instruction` | same |

Signature page proves the two signatures were nominated from finalized `getSignaturesForAddress` on Pump program `6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P` with `normalized_rows=2`. They are valid **locator** nominations under the page contract; validity as **migrate transactions** is a separate decode step.

### Parser / contract rule (static; do not relax)

Owner: `decode_supported_pump_migration_transaction` in `src/printer_v1/sources/pump_contracts.py`, applied by `direct_pump_migration.py`.

- Scans **top-level and inner** instructions (`message.instructions` plus all `meta.innerInstructions`).
- Counts instructions where `program == PUMP_PROGRAM_ID` and first 8 data bytes equal `PUMP_MIGRATE_DISCRIMINATOR`.
- Requires `len(matches) == 1` and 25 accounts; otherwise returns `reason: exactly_one_migrate_instruction_required`.
- Failure surface: `direct_pump_migration_rejected_` + reason.

The exactly-one rule is retained. This audit does not authorize relaxing it.

### Raw transaction shapes / migrate instruction mint resolution

**Not recoverable from retained artifacts.** Failure `normalized_payload_json` stores only transport accounting (`response_bytes`, stage identity, `normalized_rows=0`). The raw RPC transaction object is discarded on rejection. Therefore this supplement **cannot** list per-instruction mint accounts, cannot count whether the expected mint appears zero/one/many times, and cannot distinguish “zero migrate instructions” from “two or more” beyond the composite `len(matches) != 1` rule.

### Per-rejection classification

| Rejection | Local classification | Shared-source classification |
|---|---|---|
| Request 1879 / failure 197 | **Valid candidate-local rejection** under pinned exactly-one migrate parser (transport OK, proof failed). Not a transport outage. Insufficient evidence to further split into wrong-signature vs multi-migrate vs zero-migrate. | Escalated to channel unavailability (see below) |
| Request 1880 / failure 198 | Same as 1879 | Same |

Neither rejection is a parser relaxation candidate. Neither is proven to be an attribution defect without the raw body. Both are **not** provider HTTP/RPC unavailability: bytes were returned and validation failed closed.

### Why they became shared `SOURCE_AVAILABILITY_FAILURE`

1. Failures 197/198 are durable Source-Governor failure rows joined to discovery request ids.
2. `run_persistent_eligible_token_supply` adds them to `provider_failure_facts` and appends channel `direct_pump_finalized_live_tail` to `channels_unavailable`.
3. Shortage precedence (after liquidity-source categories) includes:

   `provider_failures > 0 and channels_unavailable → SOURCE_AVAILABILITY_FAILURE`

4. That override beats the later stop reason `DISCOVERY_OPERATION_BUDGET_EXHAUSTED` and any market-depth shortage.

**Defect:** candidate-local migrate **validation** failures are counted as **shared source unavailability** for the entire direct-Pump channel, even though transport completed and other channels (Dex, Gecko) succeeded. Correct terminal distinctions available in the design vocabulary include keeping local migrate rejection separate (e.g. migration-evidence rejection / channel-local) rather than collapsing into campaign-wide `SOURCE_AVAILABILITY_FAILURE` while flat capacity and other channels remain healthy.

## C. Forty-six `CONTRACT_BLOCKED` identities

### Category summary (exact)

| Final classification | Count | Durable reason | What actually blocked them |
|---|---:|---|---|
| `PROTOCOL_CONFIRMATION_DUE` | 38 | `FRESH_AGGREGATOR_NOMINATION_REQUIRES_EXACT_PROTOCOL_PROOF` | Fresh Dex/Gecko mint+pool entered broad reserve only; pool/token programs unresolved; **no** on-chain protocol confirmation attempted this execution |
| `UNSUPPORTED_VENUE` | 2 | same durable reason, venue `meteora-damm-v2` | Fresh Gecko nomination on non-Pump venue; no lawful Pump/PumpSwap protocol path |
| `UNSUPPORTED_VENUE` (label/path) | 6 | `POOL_CONTRACT_UNSUPPORTED` | Non-historical alternate pools from mint batch 1882 with Dex venue label `pump-fun` ∉ supported set `{pumpswap, pumpfun, pump-amm}`; recorded via `reconcile_pool_identity(... supported_contract=False)` |
| `MARKET_PROOF_PENDING` | 0 | — | not used as durable state here |
| `UNKNOWN_POOL_PROGRAM` / `UNKNOWN_LAYOUT` / `UNKNOWN_QUOTE_VARIANT` / `ORIENTATION_MISMATCH` / `IDENTITY_CONFLICT` as terminal drivers | 0 among the 46 | — | programs remain `UNRESOLVED_*` placeholders on the 40 fresh rows rather than failed decode outcomes |
| Genuine post-protocol layout failure | 0 | — | protocol confirmation never ran on these rows |

**Do not leave “awaiting exact contract proof” as the only explanation:** for the 38 Pump-family fresh rows the next proof is exact on-chain protocol/pool confirmation; for 2 meteora rows the next step is none (unsupported venue); for 6 alternate `pump-fun` rows the block is venue-support / different-pool proof policy, not missing liquidity bytes.

One fresh row (`CyaM7…pump` / pool `F4JRY…`) carries quote mint USDC (`EPjF…`) at nomination time; after protocol proof it would additionally face quote-contract checks (`EXACT_POOL_QUOTE_CONTRACT_UNSUPPORTED` path exists for exact historical rows).

### Complete per-identity table

| # | mint | pool | nomination source | venue | pool program | base mint | quote mint | last state | state reason | required next proof | proof attempted | source cost | final classification |
|---:|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `DuwZV2DfejbAGDkCFSHqmv5esgKdLmkKEZ3QyTvNKDoU` | `GGLVsqcFDk193rbCPBzj2BqPTxQaodcxgJvdeA2btqV7` | geckoterminal:1881 | meteora-damm-v2 | `UNRESOLVED_POOL_PROGRAM` | `DuwZV2DfejbAGDkCFSHqmv5esgKdLmkKEZ3QyTvNKDoU` | `So11111111111111111111111111111111111111112` | CONTRACT_BLOCKED | FRESH_AGGREGATOR_NOMINATION_REQUIRES_EXACT_PROTOCOL_PROOF | NO_LAWFUL_SUPPORTED_VENUE_PATH | no | 0 incremental | UNSUPPORTED_VENUE |
| 2 | `J9LJkrvWFJVdn8qCD2FVMKejYxASeEcXzr8cd5kKEr1b` | `3jDphtezTFSsr1U7kVikCKNLuhZAWJ17XtkWRjjk7Uck` | geckoterminal:1881 | meteora-damm-v2 | `UNRESOLVED_POOL_PROGRAM` | `J9LJkrvWFJVdn8qCD2FVMKejYxASeEcXzr8cd5kKEr1b` | `So11111111111111111111111111111111111111112` | CONTRACT_BLOCKED | FRESH_AGGREGATOR_NOMINATION_REQUIRES_EXACT_PROTOCOL_PROOF | NO_LAWFUL_SUPPORTED_VENUE_PATH | no | 0 incremental | UNSUPPORTED_VENUE |
| 3 | `2F57pj55aaNdK7G93YmEkqVjsm5ZSdfmeqQKYHVbpump` | `3YCgSBPVuUuLnL97iqkPzGWmMYX2JAPxVu4X7FnccwXS` | geckoterminal:1881 | pump-fun | `UNRESOLVED_POOL_PROGRAM` | `2F57pj55aaNdK7G93YmEkqVjsm5ZSdfmeqQKYHVbpump` | `So11111111111111111111111111111111111111112` | CONTRACT_BLOCKED | FRESH_AGGREGATOR_NOMINATION_REQUIRES_EXACT_PROTOCOL_PROOF | EXACT_ONCHAIN_PROTOCOL_POOL_PROOF | no | 0 incremental | PROTOCOL_CONFIRMATION_DUE |
| 4 | `2S1vntcJN9rnedyBwZ5hq3vDeM3EQUeiByuP7aQgpump` | `AiwMZ3ENzscHB8MmNucorYFBkuebGFbKznjQderACo4n` | geckoterminal:1881 | pump-fun | `UNRESOLVED_POOL_PROGRAM` | `2S1vntcJN9rnedyBwZ5hq3vDeM3EQUeiByuP7aQgpump` | `So11111111111111111111111111111111111111112` | CONTRACT_BLOCKED | FRESH_AGGREGATOR_NOMINATION_REQUIRES_EXACT_PROTOCOL_PROOF | EXACT_ONCHAIN_PROTOCOL_POOL_PROOF | no | 0 incremental | PROTOCOL_CONFIRMATION_DUE |
| 5 | `396wyYGLVykx1sdnSft19zqNFsKCWiFi4yqSJNtFpump` | `2BFeJDPFBhhWhCytvP8Qmw5GkEAzJFJ3ps92XEyM3Hpi` | geckoterminal:1881 | pump-fun | `UNRESOLVED_POOL_PROGRAM` | `396wyYGLVykx1sdnSft19zqNFsKCWiFi4yqSJNtFpump` | `So11111111111111111111111111111111111111112` | CONTRACT_BLOCKED | FRESH_AGGREGATOR_NOMINATION_REQUIRES_EXACT_PROTOCOL_PROOF | EXACT_ONCHAIN_PROTOCOL_POOL_PROOF | no | 0 incremental | PROTOCOL_CONFIRMATION_DUE |
| 6 | `3L9denHJEaFy7FpSbvuRbsdjRRYQ7ikerPFPm4Hhpump` | `5XsM7HrR3bmTrmAEFi7yV1EZFhxhWVSt1cKoNVGi7Hg8` | geckoterminal:1881 | pump-fun | `UNRESOLVED_POOL_PROGRAM` | `3L9denHJEaFy7FpSbvuRbsdjRRYQ7ikerPFPm4Hhpump` | `So11111111111111111111111111111111111111112` | CONTRACT_BLOCKED | FRESH_AGGREGATOR_NOMINATION_REQUIRES_EXACT_PROTOCOL_PROOF | EXACT_ONCHAIN_PROTOCOL_POOL_PROOF | no | 0 incremental | PROTOCOL_CONFIRMATION_DUE |
| 7 | `5vp4Y4y4aZErGPBBHZyGdQ3HoTibEdVK2HYCDKpJpump` | `8s4iijNymChpArKTgUuTR9QfxucPe7UP8a3z1ZBGfofh` | geckoterminal:1881 | pump-fun | `UNRESOLVED_POOL_PROGRAM` | `5vp4Y4y4aZErGPBBHZyGdQ3HoTibEdVK2HYCDKpJpump` | `So11111111111111111111111111111111111111112` | CONTRACT_BLOCKED | FRESH_AGGREGATOR_NOMINATION_REQUIRES_EXACT_PROTOCOL_PROOF | EXACT_ONCHAIN_PROTOCOL_POOL_PROOF | no | 0 incremental | PROTOCOL_CONFIRMATION_DUE |
| 8 | `82oCAtWxxcV2WpbjMJFjBZ6f1iMgd5eTBudtUVENpump` | `9L2Qik59t44dcwQ343vm9oXikPFBGRZATmx4FPe1Az51` | geckoterminal:1881 | pump-fun | `UNRESOLVED_POOL_PROGRAM` | `82oCAtWxxcV2WpbjMJFjBZ6f1iMgd5eTBudtUVENpump` | `So11111111111111111111111111111111111111112` | CONTRACT_BLOCKED | FRESH_AGGREGATOR_NOMINATION_REQUIRES_EXACT_PROTOCOL_PROOF | EXACT_ONCHAIN_PROTOCOL_POOL_PROOF | no | 0 incremental | PROTOCOL_CONFIRMATION_DUE |
| 9 | `8eu8uJHU2uHZpYknZvYpFSH2cJanjkSnUbd2gmRNsoHp` | `4pTgpc1t7ytMNdEy1MZ4UmRZg1CbQyTVQMxXm3RYsfj1` | geckoterminal:1881 | pump-fun | `UNRESOLVED_POOL_PROGRAM` | `8eu8uJHU2uHZpYknZvYpFSH2cJanjkSnUbd2gmRNsoHp` | `So11111111111111111111111111111111111111112` | CONTRACT_BLOCKED | FRESH_AGGREGATOR_NOMINATION_REQUIRES_EXACT_PROTOCOL_PROOF | EXACT_ONCHAIN_PROTOCOL_POOL_PROOF | no | 0 incremental | PROTOCOL_CONFIRMATION_DUE |
| 10 | `A6fALeJYqR9aUdLNvvYAWmotLEU42xYACdkkU8Spu72N` | `BEpnTpH555EYDbG2F8XfZQjUQtxfo9sgwNufwuuVDUSw` | geckoterminal:1881 | pump-fun | `UNRESOLVED_POOL_PROGRAM` | `A6fALeJYqR9aUdLNvvYAWmotLEU42xYACdkkU8Spu72N` | `So11111111111111111111111111111111111111112` | CONTRACT_BLOCKED | FRESH_AGGREGATOR_NOMINATION_REQUIRES_EXACT_PROTOCOL_PROOF | EXACT_ONCHAIN_PROTOCOL_POOL_PROOF | no | 0 incremental | PROTOCOL_CONFIRMATION_DUE |
| 11 | `AMUVAEFGhuRZioSEc81zzsY5WYVFXR9s8kqzkT3gpump` | `8bDbsmcXVA3ZjjfvJ8hpgcMbXzsQimmB5xBKpmoMhQCA` | geckoterminal:1881 | pump-fun | `UNRESOLVED_POOL_PROGRAM` | `AMUVAEFGhuRZioSEc81zzsY5WYVFXR9s8kqzkT3gpump` | `So11111111111111111111111111111111111111112` | CONTRACT_BLOCKED | FRESH_AGGREGATOR_NOMINATION_REQUIRES_EXACT_PROTOCOL_PROOF | EXACT_ONCHAIN_PROTOCOL_POOL_PROOF | no | 0 incremental | PROTOCOL_CONFIRMATION_DUE |
| 12 | `APE98kUdT9fJbAsXweJBpEJPVCTcXPKKXZV2xTvxpump` | `4Q1brZRqACx6Zj2pMeRAqoGG1gmBXpvMpdutF8sed41e` | geckoterminal:1881 | pump-fun | `UNRESOLVED_POOL_PROGRAM` | `APE98kUdT9fJbAsXweJBpEJPVCTcXPKKXZV2xTvxpump` | `So11111111111111111111111111111111111111112` | CONTRACT_BLOCKED | FRESH_AGGREGATOR_NOMINATION_REQUIRES_EXACT_PROTOCOL_PROOF | EXACT_ONCHAIN_PROTOCOL_POOL_PROOF | no | 0 incremental | PROTOCOL_CONFIRMATION_DUE |
| 13 | `As8KsEFea6aEgvoSXYx8dpUT81ZsGrTDBn1BpLxipump` | `6jJrQTzZt8LxjJqAHbUJXDAJK5ruooCgcXYnwKPREFvt` | geckoterminal:1881 | pump-fun | `UNRESOLVED_POOL_PROGRAM` | `As8KsEFea6aEgvoSXYx8dpUT81ZsGrTDBn1BpLxipump` | `So11111111111111111111111111111111111111112` | CONTRACT_BLOCKED | FRESH_AGGREGATOR_NOMINATION_REQUIRES_EXACT_PROTOCOL_PROOF | EXACT_ONCHAIN_PROTOCOL_POOL_PROOF | no | 0 incremental | PROTOCOL_CONFIRMATION_DUE |
| 14 | `CyaM7GB7rXccn646jp5yQZUCynWY5SfvSURtzLTUpump` | `F4JRY6W2eXoB8AR6MyvA4ytzUuGYQdxc4h4e4JT5eyik` | geckoterminal:1881 | pump-fun | `UNRESOLVED_POOL_PROGRAM` | `CyaM7GB7rXccn646jp5yQZUCynWY5SfvSURtzLTUpump` | `EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v` | CONTRACT_BLOCKED | FRESH_AGGREGATOR_NOMINATION_REQUIRES_EXACT_PROTOCOL_PROOF | EXACT_PROTOCOL_PROOF_THEN_QUOTE_CONTRACT_CHECK | no | 0 incremental | PROTOCOL_CONFIRMATION_DUE (quote also non-WSOL → likely UNKNOWN_QUOTE_VARIANT after proof) |
| 15 | `EPLufw4YdVvmUeTdt51wgyGyqa5Bym4iiwTxLhEypump` | `CXTb5oH7qg4UJtBve416HoswCWygtUzWZSKDymiGkUn` | geckoterminal:1881 | pump-fun | `UNRESOLVED_POOL_PROGRAM` | `EPLufw4YdVvmUeTdt51wgyGyqa5Bym4iiwTxLhEypump` | `So11111111111111111111111111111111111111112` | CONTRACT_BLOCKED | FRESH_AGGREGATOR_NOMINATION_REQUIRES_EXACT_PROTOCOL_PROOF | EXACT_ONCHAIN_PROTOCOL_POOL_PROOF | no | 0 incremental | PROTOCOL_CONFIRMATION_DUE |
| 16 | `HZasbKHBxmdrJrPcHPNidmcWmVHLJEjaAiXmxGw7pump` | `AUXsK1Nsc453t7Udys8W36tSicZZBzQT24vGEuBMJv5` | geckoterminal:1881 | pump-fun | `UNRESOLVED_POOL_PROGRAM` | `HZasbKHBxmdrJrPcHPNidmcWmVHLJEjaAiXmxGw7pump` | `So11111111111111111111111111111111111111112` | CONTRACT_BLOCKED | FRESH_AGGREGATOR_NOMINATION_REQUIRES_EXACT_PROTOCOL_PROOF | EXACT_ONCHAIN_PROTOCOL_POOL_PROOF | no | 0 incremental | PROTOCOL_CONFIRMATION_DUE |
| 17 | `hbPiqgYcLzVqkx7mEmh1En9y3EhPXQjodNM7JTqpump` | `48gtGrfnb2LTtGErfuhNv1bK3nTE56CtdyDRzYCC1fPF` | geckoterminal:1881 | pump-fun | `UNRESOLVED_POOL_PROGRAM` | `hbPiqgYcLzVqkx7mEmh1En9y3EhPXQjodNM7JTqpump` | `So11111111111111111111111111111111111111112` | CONTRACT_BLOCKED | FRESH_AGGREGATOR_NOMINATION_REQUIRES_EXACT_PROTOCOL_PROOF | EXACT_ONCHAIN_PROTOCOL_POOL_PROOF | no | 0 incremental | PROTOCOL_CONFIRMATION_DUE |
| 18 | `24izfUUtLixxLmg3aje1WXy5f7444LyMtPj2YzyRpump` | `6LXy7cm6trg7f8tG1DCpdRyZArpZpnUazyTmaxDfzXeP` | dexscreener:1877 | pumpswap | `UNRESOLVED_POOL_PROGRAM` | `24izfUUtLixxLmg3aje1WXy5f7444LyMtPj2YzyRpump` | `So11111111111111111111111111111111111111112` | CONTRACT_BLOCKED | FRESH_AGGREGATOR_NOMINATION_REQUIRES_EXACT_PROTOCOL_PROOF | EXACT_ONCHAIN_PROTOCOL_POOL_PROOF | no | 0 incremental | PROTOCOL_CONFIRMATION_DUE |
| 19 | `2g4MMe3gzLzYLHugt81K5sQkmzUNmPC2STbFrnxbpump` | `4sDWk5jXqpNcqsz8Nv5qNAhF1UXWYFCReRjTKzdB5reL` | dexscreener:1877 | pumpswap | `UNRESOLVED_POOL_PROGRAM` | `2g4MMe3gzLzYLHugt81K5sQkmzUNmPC2STbFrnxbpump` | `So11111111111111111111111111111111111111112` | CONTRACT_BLOCKED | FRESH_AGGREGATOR_NOMINATION_REQUIRES_EXACT_PROTOCOL_PROOF | EXACT_ONCHAIN_PROTOCOL_POOL_PROOF | no | 0 incremental | PROTOCOL_CONFIRMATION_DUE |
| 20 | `2wbUoxZ8Die8XYuV8aDqzAaPzCfpQD3C2QbGBUEJpump` | `2DiuisAwDFPXmUjMHncF4ZuUgHm5CDWcuBrJxF9SbRR2` | dexscreener:1877 | pumpswap | `UNRESOLVED_POOL_PROGRAM` | `2wbUoxZ8Die8XYuV8aDqzAaPzCfpQD3C2QbGBUEJpump` | `So11111111111111111111111111111111111111112` | CONTRACT_BLOCKED | FRESH_AGGREGATOR_NOMINATION_REQUIRES_EXACT_PROTOCOL_PROOF | EXACT_ONCHAIN_PROTOCOL_POOL_PROOF | no | 0 incremental | PROTOCOL_CONFIRMATION_DUE |
| 21 | `3TaHyz4w9qhbd21EEyPWi8rTYrtqbCRsEKEt9H26pump` | `8jqeequyC9nwjmBAvgZQQooT1TzozdKqNTKeNKUzGShF` | dexscreener:1877 | pumpswap | `UNRESOLVED_POOL_PROGRAM` | `3TaHyz4w9qhbd21EEyPWi8rTYrtqbCRsEKEt9H26pump` | `So11111111111111111111111111111111111111112` | CONTRACT_BLOCKED | FRESH_AGGREGATOR_NOMINATION_REQUIRES_EXACT_PROTOCOL_PROOF | EXACT_ONCHAIN_PROTOCOL_POOL_PROOF | no | 0 incremental | PROTOCOL_CONFIRMATION_DUE |
| 22 | `3vWbMS1CfyM7LSBTTRi8T6eRvJ6v2CGzn5TA6z5Apump` | `87Cwa3roWPpt3de7f3vhM75spenshyFWVukF3tFxVuXo` | dexscreener:1877 | pumpswap | `UNRESOLVED_POOL_PROGRAM` | `3vWbMS1CfyM7LSBTTRi8T6eRvJ6v2CGzn5TA6z5Apump` | `So11111111111111111111111111111111111111112` | CONTRACT_BLOCKED | FRESH_AGGREGATOR_NOMINATION_REQUIRES_EXACT_PROTOCOL_PROOF | EXACT_ONCHAIN_PROTOCOL_POOL_PROOF | no | 0 incremental | PROTOCOL_CONFIRMATION_DUE |
| 23 | `6gF9L7Axy59i1VcVn4cD4ovaMHcjacPeV7Vc3nZ1pump` | `64FNB7uca2RRhzPKvmLkkVws7Ea3NK2AUrhQKTAg8q8a` | dexscreener:1877 | pumpswap | `UNRESOLVED_POOL_PROGRAM` | `6gF9L7Axy59i1VcVn4cD4ovaMHcjacPeV7Vc3nZ1pump` | `So11111111111111111111111111111111111111112` | CONTRACT_BLOCKED | FRESH_AGGREGATOR_NOMINATION_REQUIRES_EXACT_PROTOCOL_PROOF | EXACT_ONCHAIN_PROTOCOL_POOL_PROOF | no | 0 incremental | PROTOCOL_CONFIRMATION_DUE |
| 24 | `6orpg9pNFwTh1uYwXq5CeuYocm34NbJBwF93E2rCpump` | `CyBpudbbkMwvMVT5LRbLj7HMynTHquiZwjR6yondkSDf` | dexscreener:1877 | pumpswap | `UNRESOLVED_POOL_PROGRAM` | `6orpg9pNFwTh1uYwXq5CeuYocm34NbJBwF93E2rCpump` | `So11111111111111111111111111111111111111112` | CONTRACT_BLOCKED | FRESH_AGGREGATOR_NOMINATION_REQUIRES_EXACT_PROTOCOL_PROOF | EXACT_ONCHAIN_PROTOCOL_POOL_PROOF | no | 0 incremental | PROTOCOL_CONFIRMATION_DUE |
| 25 | `77aujYZykaUT9HqcpYWLU7FDyfJ7zpyNxBmHusKcpump` | `BvTmU5kQbV4Vqv7nDHAekib1Mw5oLCFH1btoDswz28XQ` | dexscreener:1877 | pumpswap | `UNRESOLVED_POOL_PROGRAM` | `77aujYZykaUT9HqcpYWLU7FDyfJ7zpyNxBmHusKcpump` | `So11111111111111111111111111111111111111112` | CONTRACT_BLOCKED | FRESH_AGGREGATOR_NOMINATION_REQUIRES_EXACT_PROTOCOL_PROOF | EXACT_ONCHAIN_PROTOCOL_POOL_PROOF | no | 0 incremental | PROTOCOL_CONFIRMATION_DUE |
| 26 | `84MbokjpF4T9NhyKmpTbpKjedwuKtYHRP8MNRvb5pump` | `G84ETJot2VbkHCqQLG7qRkXYgytEnXajqXZWFj4Mdht7` | dexscreener:1877 | pumpswap | `UNRESOLVED_POOL_PROGRAM` | `84MbokjpF4T9NhyKmpTbpKjedwuKtYHRP8MNRvb5pump` | `So11111111111111111111111111111111111111112` | CONTRACT_BLOCKED | FRESH_AGGREGATOR_NOMINATION_REQUIRES_EXACT_PROTOCOL_PROOF | EXACT_ONCHAIN_PROTOCOL_POOL_PROOF | no | 0 incremental | PROTOCOL_CONFIRMATION_DUE |
| 27 | `ABPwcWDheLbP8PysfEnWbpVnsYrKc9H8Z9P3uNUipump` | `5N4sBhaQn7bFawzawAskfpK6toyAordTMst1Gat4z6sX` | dexscreener:1877 | pumpswap | `UNRESOLVED_POOL_PROGRAM` | `ABPwcWDheLbP8PysfEnWbpVnsYrKc9H8Z9P3uNUipump` | `So11111111111111111111111111111111111111112` | CONTRACT_BLOCKED | FRESH_AGGREGATOR_NOMINATION_REQUIRES_EXACT_PROTOCOL_PROOF | EXACT_ONCHAIN_PROTOCOL_POOL_PROOF | no | 0 incremental | PROTOCOL_CONFIRMATION_DUE |
| 28 | `AEWXFt95HKofXLJsASLmeUzgj3A19EbCevCWzuc3pump` | `HruU9SsUhE2RuKCtekgGZneHpJEeGA39ZpjqTLjw6M7` | dexscreener:1877 | pumpswap | `UNRESOLVED_POOL_PROGRAM` | `AEWXFt95HKofXLJsASLmeUzgj3A19EbCevCWzuc3pump` | `So11111111111111111111111111111111111111112` | CONTRACT_BLOCKED | FRESH_AGGREGATOR_NOMINATION_REQUIRES_EXACT_PROTOCOL_PROOF | EXACT_ONCHAIN_PROTOCOL_POOL_PROOF | no | 0 incremental | PROTOCOL_CONFIRMATION_DUE |
| 29 | `D4nv9GZssmhAv1gLwQ3FHvtB6ocCDopdAofcmruupump` | `At4ChP3T79Q8zxstWBJdj1e6K1MXkipvQ2m3SWSLuGw5` | dexscreener:1877 | pumpswap | `UNRESOLVED_POOL_PROGRAM` | `D4nv9GZssmhAv1gLwQ3FHvtB6ocCDopdAofcmruupump` | `So11111111111111111111111111111111111111112` | CONTRACT_BLOCKED | FRESH_AGGREGATOR_NOMINATION_REQUIRES_EXACT_PROTOCOL_PROOF | EXACT_ONCHAIN_PROTOCOL_POOL_PROOF | no | 0 incremental | PROTOCOL_CONFIRMATION_DUE |
| 30 | `DfnCGzBjBrSGx4vm8hPc2zTfKEKzu8ebhFmQJjCNpump` | `4bxzJEyvAAzHBfFJ21BZ6qqbB27FYjQGTQcs6gm5kvPR` | dexscreener:1877 | pumpswap | `UNRESOLVED_POOL_PROGRAM` | `DfnCGzBjBrSGx4vm8hPc2zTfKEKzu8ebhFmQJjCNpump` | `So11111111111111111111111111111111111111112` | CONTRACT_BLOCKED | FRESH_AGGREGATOR_NOMINATION_REQUIRES_EXACT_PROTOCOL_PROOF | EXACT_ONCHAIN_PROTOCOL_POOL_PROOF | no | 0 incremental | PROTOCOL_CONFIRMATION_DUE |
| 31 | `DuwZV2DfejbAGDkCFSHqmv5esgKdLmkKEZ3QyTvNKDoU` | `8KJV2qfnzNsNkw3kY9pKAQbmxG7WY16YBxR7osxox49U` | geckoterminal:1881 | pumpswap | `UNRESOLVED_POOL_PROGRAM` | `DuwZV2DfejbAGDkCFSHqmv5esgKdLmkKEZ3QyTvNKDoU` | `So11111111111111111111111111111111111111112` | CONTRACT_BLOCKED | FRESH_AGGREGATOR_NOMINATION_REQUIRES_EXACT_PROTOCOL_PROOF | EXACT_ONCHAIN_PROTOCOL_POOL_PROOF | no | 0 incremental | PROTOCOL_CONFIRMATION_DUE |
| 32 | `ECq6ZaJsKTS2rHSQ6M7YLKZvoxZ9aaNKKiUSTQ5Kpump` | `Huzf7666tpGSXgyCaxd31uw7rU1oAtk7czz15C6AkvJH` | dexscreener:1877 | pumpswap | `UNRESOLVED_POOL_PROGRAM` | `ECq6ZaJsKTS2rHSQ6M7YLKZvoxZ9aaNKKiUSTQ5Kpump` | `So11111111111111111111111111111111111111112` | CONTRACT_BLOCKED | FRESH_AGGREGATOR_NOMINATION_REQUIRES_EXACT_PROTOCOL_PROOF | EXACT_ONCHAIN_PROTOCOL_POOL_PROOF | no | 0 incremental | PROTOCOL_CONFIRMATION_DUE |
| 33 | `EZnT3rk352HfhPjFEpJW4mdMhnRqzegXRpx28tkjgrok` | `6q4Y8uuVuJDg621c9th3BKWUF2qgkQ83v8YubLe2GLQb` | dexscreener:1877 | pumpswap | `UNRESOLVED_POOL_PROGRAM` | `EZnT3rk352HfhPjFEpJW4mdMhnRqzegXRpx28tkjgrok` | `So11111111111111111111111111111111111111112` | CONTRACT_BLOCKED | FRESH_AGGREGATOR_NOMINATION_REQUIRES_EXACT_PROTOCOL_PROOF | EXACT_ONCHAIN_PROTOCOL_POOL_PROOF | no | 0 incremental | PROTOCOL_CONFIRMATION_DUE |
| 34 | `FGXzMRL1XG1Jgtv4FmgRE8qYS5kXdVgZwL8odYJMpump` | `77CW3WvGEvGf5UCE383bSmEXCLpSwjtXP8E6URWiuwiP` | dexscreener:1877 | pumpswap | `UNRESOLVED_POOL_PROGRAM` | `FGXzMRL1XG1Jgtv4FmgRE8qYS5kXdVgZwL8odYJMpump` | `So11111111111111111111111111111111111111112` | CONTRACT_BLOCKED | FRESH_AGGREGATOR_NOMINATION_REQUIRES_EXACT_PROTOCOL_PROOF | EXACT_ONCHAIN_PROTOCOL_POOL_PROOF | no | 0 incremental | PROTOCOL_CONFIRMATION_DUE |
| 35 | `HAqNZqW9KC8JzP6cfinDby5rFXCvitnQBrCL4NW7pump` | `8AyiB9fpuBbwk31SpBv3QU8vrZSjJ66NbNxr6wFWy3dZ` | dexscreener:1877 | pumpswap | `UNRESOLVED_POOL_PROGRAM` | `HAqNZqW9KC8JzP6cfinDby5rFXCvitnQBrCL4NW7pump` | `So11111111111111111111111111111111111111112` | CONTRACT_BLOCKED | FRESH_AGGREGATOR_NOMINATION_REQUIRES_EXACT_PROTOCOL_PROOF | EXACT_ONCHAIN_PROTOCOL_POOL_PROOF | no | 0 incremental | PROTOCOL_CONFIRMATION_DUE |
| 36 | `HtkNiU9Lao3ooYSTojRvmLKhxRFd3XREAhErRRvnpump` | `CjCpzLvtLBt7Ew1DTQiN9b4GgZhPAyWn5mqyGnbkGivh` | dexscreener:1877 | pumpswap | `UNRESOLVED_POOL_PROGRAM` | `HtkNiU9Lao3ooYSTojRvmLKhxRFd3XREAhErRRvnpump` | `So11111111111111111111111111111111111111112` | CONTRACT_BLOCKED | FRESH_AGGREGATOR_NOMINATION_REQUIRES_EXACT_PROTOCOL_PROOF | EXACT_ONCHAIN_PROTOCOL_POOL_PROOF | no | 0 incremental | PROTOCOL_CONFIRMATION_DUE |
| 37 | `J9LJkrvWFJVdn8qCD2FVMKejYxASeEcXzr8cd5kKEr1b` | `Hu8YAbgVQxZWyzX52RpC2HRmUqsxGQnqzySgaQAJMq2K` | geckoterminal:1881 | pumpswap | `UNRESOLVED_POOL_PROGRAM` | `J9LJkrvWFJVdn8qCD2FVMKejYxASeEcXzr8cd5kKEr1b` | `So11111111111111111111111111111111111111112` | CONTRACT_BLOCKED | FRESH_AGGREGATOR_NOMINATION_REQUIRES_EXACT_PROTOCOL_PROOF | EXACT_ONCHAIN_PROTOCOL_POOL_PROOF | no | 0 incremental | PROTOCOL_CONFIRMATION_DUE |
| 38 | `ZzfW2ur19NBq2uGepqiQdG9V1Q6Ev9oJZCZBBBqpump` | `AfJbWSshDjXomy9F7GiboEUa86XWKkP3VjE2rCpg4pKM` | dexscreener:1877 | pumpswap | `UNRESOLVED_POOL_PROGRAM` | `ZzfW2ur19NBq2uGepqiQdG9V1Q6Ev9oJZCZBBBqpump` | `So11111111111111111111111111111111111111112` | CONTRACT_BLOCKED | FRESH_AGGREGATOR_NOMINATION_REQUIRES_EXACT_PROTOCOL_PROOF | EXACT_ONCHAIN_PROTOCOL_POOL_PROOF | no | 0 incremental | PROTOCOL_CONFIRMATION_DUE |
| 39 | `bJZkPdU3BEVUu8dzGqtxGhuuX6X4Z3u7KxBzP3Gpump` | `HaJQTtm1wTmLWTNbVnhzkjPq3tAseBNJM1MVRbM6F7T` | dexscreener:1877 | pumpswap | `UNRESOLVED_POOL_PROGRAM` | `bJZkPdU3BEVUu8dzGqtxGhuuX6X4Z3u7KxBzP3Gpump` | `So11111111111111111111111111111111111111112` | CONTRACT_BLOCKED | FRESH_AGGREGATOR_NOMINATION_REQUIRES_EXACT_PROTOCOL_PROOF | EXACT_ONCHAIN_PROTOCOL_POOL_PROOF | no | 0 incremental | PROTOCOL_CONFIRMATION_DUE |
| 40 | `hbPiqgYcLzVqkx7mEmh1En9y3EhPXQjodNM7JTqpump` | `EX49SxwHapYbEdpdRJmp4ZXFtrV6isQ6YwABQj3DQD49` | geckoterminal:1881 | pumpswap | `UNRESOLVED_POOL_PROGRAM` | `hbPiqgYcLzVqkx7mEmh1En9y3EhPXQjodNM7JTqpump` | `So11111111111111111111111111111111111111112` | CONTRACT_BLOCKED | FRESH_AGGREGATOR_NOMINATION_REQUIRES_EXACT_PROTOCOL_PROOF | EXACT_ONCHAIN_PROTOCOL_POOL_PROOF | no | 0 incremental | PROTOCOL_CONFIRMATION_DUE |
| 41 | `12u9FULaUfHD8uHHe98Fz5gdhg8qeX6DyV93B3Dtpump` | `2n8x3rP9E1qcehxETAUBsHxgMwmUPHUtfZvTuBvKfyZn` | dexscreener:1882 | pump-fun | `pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA` | `12u9FULaUfHD8uHHe98Fz5gdhg8qeX6DyV93B3Dtpump` | `So11111111111111111111111111111111111111112` | CONTRACT_BLOCKED | POOL_CONTRACT_UNSUPPORTED | NEW_POOL_PENDING_PROOF only if venue/program supported; else terminal unsupported | recorded during mint-batch alternate reconciliation; no on-chain protocol confirm | shared batch request 1882 | UNSUPPORTED_VENUE (Dex `pump-fun` label ∉ {pumpswap,pumpfun,pump-amm}; non-historical alternate pool) |
| 42 | `23Z8qs4DhbEGk4qnQ8LQsWQ8RGy18VcFQgKYWgHvpump` | `CLyAYRaEJZdZLftJP1XLZEjqRHANYZjGghWXABneyE9n` | dexscreener:1882 | pump-fun | `pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA` | `23Z8qs4DhbEGk4qnQ8LQsWQ8RGy18VcFQgKYWgHvpump` | `So11111111111111111111111111111111111111112` | CONTRACT_BLOCKED | POOL_CONTRACT_UNSUPPORTED | NEW_POOL_PENDING_PROOF only if venue/program supported; else terminal unsupported | recorded during mint-batch alternate reconciliation; no on-chain protocol confirm | shared batch request 1882 | UNSUPPORTED_VENUE (Dex `pump-fun` label ∉ {pumpswap,pumpfun,pump-amm}; non-historical alternate pool) |
| 43 | `2vLNEm6uNTPdAPWxG3sH88yG4ASExkHW5Q3VxF7rpump` | `2N4v7aiCimRB4YRD8RMquYqYvHgTAn3KWq7yFnSLPp8u` | dexscreener:1882 | pump-fun | `pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA` | `2vLNEm6uNTPdAPWxG3sH88yG4ASExkHW5Q3VxF7rpump` | `So11111111111111111111111111111111111111112` | CONTRACT_BLOCKED | POOL_CONTRACT_UNSUPPORTED | NEW_POOL_PENDING_PROOF only if venue/program supported; else terminal unsupported | recorded during mint-batch alternate reconciliation; no on-chain protocol confirm | shared batch request 1882 | UNSUPPORTED_VENUE (Dex `pump-fun` label ∉ {pumpswap,pumpfun,pump-amm}; non-historical alternate pool) |
| 44 | `3dQoupzWpXqTAAGqL83n6PmgATeVEkZfs6rmK6ipPump` | `DSRRjjPNN3DBZTyqmWcgDz7pagd6wmmiNCWuofzur2VM` | dexscreener:1882 | pump-fun | `pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA` | `3dQoupzWpXqTAAGqL83n6PmgATeVEkZfs6rmK6ipPump` | `So11111111111111111111111111111111111111112` | CONTRACT_BLOCKED | POOL_CONTRACT_UNSUPPORTED | NEW_POOL_PENDING_PROOF only if venue/program supported; else terminal unsupported | recorded during mint-batch alternate reconciliation; no on-chain protocol confirm | shared batch request 1882 | UNSUPPORTED_VENUE (Dex `pump-fun` label ∉ {pumpswap,pumpfun,pump-amm}; non-historical alternate pool) |
| 45 | `4G5y3xjDB5F8QCcAuCkqMXiWjCjuuRPnUoqm9y9bpump` | `3CCakxQDnNxmS3siW1g2qkYRtMRsAwaY4t8kycHjvPbK` | dexscreener:1882 | pump-fun | `pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA` | `4G5y3xjDB5F8QCcAuCkqMXiWjCjuuRPnUoqm9y9bpump` | `So11111111111111111111111111111111111111112` | CONTRACT_BLOCKED | POOL_CONTRACT_UNSUPPORTED | NEW_POOL_PENDING_PROOF only if venue/program supported; else terminal unsupported | recorded during mint-batch alternate reconciliation; no on-chain protocol confirm | shared batch request 1882 | UNSUPPORTED_VENUE (Dex `pump-fun` label ∉ {pumpswap,pumpfun,pump-amm}; non-historical alternate pool) |
| 46 | `4hi84NkokbcM6G1LFQ9wB7HgjGrFxh4qXwAc16chpump` | `2APRw7ZNUkswaLA5vjFnK67r95x32nkBWqHGekXr8tXe` | dexscreener:1882 | pump-fun | `pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA` | `4hi84NkokbcM6G1LFQ9wB7HgjGrFxh4qXwAc16chpump` | `So11111111111111111111111111111111111111112` | CONTRACT_BLOCKED | POOL_CONTRACT_UNSUPPORTED | NEW_POOL_PENDING_PROOF only if venue/program supported; else terminal unsupported | recorded during mint-batch alternate reconciliation; no on-chain protocol confirm | shared batch request 1882 | UNSUPPORTED_VENUE (Dex `pump-fun` label ∉ {pumpswap,pumpfun,pump-amm}; non-historical alternate pool) |

**Category totals:** PROTOCOL_CONFIRMATION_DUE (pump/pumpswap fresh aggregator)=38; UNSUPPORTED_VENUE meteora fresh=2; UNSUPPORTED_VENUE alternate-pool pump-fun label=6; genuine layout/quote IDENTITY_CONFLICT=0 in this set.

## D. Stage-capacity reconstruction

### What the 18 remaining units are

Reconstructed stage consumption matching the 12 governed requests:

| Stage | Reserved | Used | Remaining |
|---|---:|---:|---:|
| intake | 3 | 3 | 0 |
| market_batching | 2 | 1 | **1** |
| reconciliation | 6 | 6 | 0 |
| protocol_confirmation | 7 | 2 | **5** |
| holder_safety | 8 | 0 | **8** |
| final_refresh_handoff | 4 | 0 | **4** |
| **sum** | **30** | **12** | **18** |

### Why discovery stopped with 18 remaining

1. After permanent mint-market round 1, code advances and charges `protocol_confirmation` using the already-finished migration ledger (`source_requests - 1`).
2. That advances the immutable stage cursor past `market_batching` / `reconciliation`.
3. Round 2 tries to re-enter `market_batching` → `BUDGET_STAGE_REWIND_FORBIDDEN` → labeled `DISCOVERY_OPERATION_BUDGET_EXHAUSTED`.
4. Flat ceiling still has 18; holder and handoff reservations were never the spent resource.
5. Shortage classifier then **relabels** the terminal to `SOURCE_AVAILABILITY_FAILURE` due to the two migrate validation failures.

### Reserved / reclaimable / unreachable

| Unit group | Status under approved forward-only policy |
|---|---|
| 1 unused market_batching | **Stranded** behind protocol cursor (not forward-reclaimable without rewind or reordering fix) |
| 5 unused protocol_confirmation | Forward-available on paper; not spent because loop aborted and no further protocol work was scheduled for fresh nominations |
| 8 holder_safety | Protected remaining; **unreachable** after campaign pre-holder gate (`graduated_candidates < 2`) and supply terminalization |
| 4 final_refresh_handoff | Same; lifecycle never started |

### Planner vs shared terminal

- **Planner/stage defect:** premature protocol stage advance after the first market batch independently prevents additional market-batch work despite remaining flat capacity and one reserved market unit.
- **Shared terminal:** migrate validation → `SOURCE_AVAILABILITY_FAILURE` freezes the campaign before holder/handoff even if more market-ready depth appeared.
- **Not** a recommendation to raise the 30 ceiling. Capacity existed; ordering/classification burned the path to use it.

## E. Terminal-precedence reconstruction

### Immutable first terminal path

1. Migration txs 1879/1880 fail local decode → durable failures 197/198.
2. Supply marks `provider_failures=2`, `channels_unavailable=['direct_pump_finalized_live_tail']`.
3. Loop stop reason becomes `DISCOVERY_OPERATION_BUDGET_EXHAUSTED` (stage rewind), with `unexplored_work_prevented_by_hard_ceiling=true` and 18 ops remaining.
4. Shortage override: provider failures + unavailable channel ⇒ **`SOURCE_AVAILABILITY_FAILURE`**.
5. Campaign pre-lifecycle package copies that shortage as `terminal_classification` / `blocked_supply_reason`.
6. `graduated_candidate_count=1` skips holder; lifecycle never starts.
7. Campaign/run/cycle rows and cleanup seal `first_terminal_cause=SOURCE_AVAILABILITY_FAILURE` immutably.

### Correct classification among exact terminals

| Candidate terminal | Fit for this execution |
|---|---|
| `SOURCE_AVAILABILITY_FAILURE` | **What was recorded**; **over-broad** relative to evidence (transport OK on failed channel; other sources OK) |
| `MIGRATION_EVIDENCE_REJECTED` / candidate-local migrate rejection | **Best description of the two Pump tx outcomes**; not the durable enum written |
| `OPERATION_BUDGET_EXHAUSTED` / `BUDGET_EXHAUSTION` | Stop reason label used internally, but **false as flat exhaustion** (18 remaining); true only as stage-cursor deadlock |
| `CONTRACT_COVERAGE_BLOCKED` | Describes the 46 broad/alternate rows, **not** the first terminal cause (market still produced 1 ready survivor) |
| `IDENTITY_CONFLICT_BLOCKED` | Not evidenced as terminal driver |
| True market supply shortage | Not selected; unexplored work remained |

**Distinction:** the two migrate failures are **candidate-local validation rejections**. Shared-source failure is a **classification defect** layered on top of an independent **stage-ordering defect**.

## Proven root-cause hierarchy

1. **Terminal classification defect (primary recorded cause):** candidate-local Pump migrate validation rejections counted as shared `SOURCE_AVAILABILITY_FAILURE` via channel unavailability.
2. **Stage-ordering defect (capacity strand):** charging/advancing `protocol_confirmation` after the first mint-market batch prevents further market rounds despite remaining flat and stage capacity (1 market + 5 protocol + 8 holder + 4 handoff = 18).
3. **Market-depth reality (non-defect):** only one exact pool cleared the $3,000 floor among evaluated graduated inventory; thirteen below floor; sixteen exact-pool no-match (market absence, not provider failure).
4. **Holder non-activation:** single market-ready survivor never entered holder/safety because campaign requires ≥2 graduated candidates before `_evaluate_holder_eligibility`.
5. **Contract-blocked mass (mostly expected):** 40 fresh aggregator nominations intentionally land protocol-due; 6 alternate pools blocked by venue-support rule; not the immutable first terminal.

## Exact defects versus expected behavior

### Proven defects

| ID | Defect | Evidence |
|---|---|---|
| D1 | Candidate-local migrate validation failure escalated to shared `SOURCE_AVAILABILITY_FAILURE` | failures 197/198; channels_unavailable; shortage override; successful Dex/Gecko peers |
| D2 | Stage budget advances to `protocol_confirmation` after first permanent market batch, forbidding further `market_batching` (rewind) while 18 flat units remain | code path + `discovery_rounds=2` + stop reason vs remaining 18 |
| D3 | Solitary market-ready survivor cannot receive holder/safety under `<2` graduated gate despite reserved holder capacity | graduated_count=1; holder attempts=0; stage holder rem=8 |

### Expected / non-defects

| Behavior | Why expected |
|---|---|
| Exactly-one migrate instruction rule rejecting non-conforming txs | Pinned Pump contract; must not be relaxed |
| Fresh aggregator rows → `CONTRACT_BLOCKED` / protocol-due | Approved permanent design: broad only until exact proof |
| $3,000 floor, exact-pool no-match as market absence | Unchanged eligibility law |
| No lifecycle / Scheduler / memory window | Pre-lifecycle honest block |
| Not raising discovery ceiling | Capacity remained; ceiling was not the binding truth |
| Transport vs request count divergence (13 vs 12) | Explicit six-unit contract |

## Remaining evidence gaps

1. Raw `getTransaction` JSON for signatures `v5DuHZ…` and `2oVXpG…` (instruction list, inner vs outer, mint accounts). Not stored on rejection.
2. Durable stage_operations_used map was not sealed into the campaign report JSON (reconstructed from code + request ledger).
3. Named file `docs/printer-v1-v2-9-8b-permanent-discovery-conversion-terminal-audit.md` absent on this HEAD; gaps taken from attempt closeout + artifacts.

These gaps do **not** block answering the four audit questions.

## Narrowest permitted repair boundary

Evidence allows only these narrow repairs (no budget increase, no exactly-one relaxation, no eligibility threshold change):

1. **Terminal classification:** treat durable `direct_pump_migration_rejected_*` validation failures as candidate-local / migration-evidence outcomes; do not mark the entire direct-Pump channel as shared source-unavailable when transport completed and peer sources are healthy, unless a true transport/source-health failure is proven.
2. **Stage ordering:** charge and advance `protocol_confirmation` in chronological alignment with direct migration (or otherwise avoid advancing past `market_batching` before market-stage work is finished), preserving forward-only law and protected holder/handoff reservations.
3. **Holder activation policy (optional, design-aligned):** allow holder/safety evaluation for market-ready survivors when depth is in `(0,4)` without requiring two fully formed graduated candidates up front, while still requiring four fully eligible (or honest exhaustion) before selection/handoff.

Out of scope: relaxing migrate exactly-one; raising the 30 ceiling; auto-accepting aggregator pools without protocol proof; retries/successors; live re-attempt without new authorization.

## Money-usefulness contribution

This supplement converts an opaque pre-lifecycle block into actionable root causes: the machine did not “run out of operations” and did not need a weaker Pump parser. It mislabeled local migrate proof failures as shared source death and mis-ordered stage accounting so remaining capacity could not buy more market-ready depth or holder evaluation. Fixing classification and stage ordering is the cheapest path back toward lawful four-candidate fully eligible freezes and eventual clean `WINDOW_15M` memory—without faking profit or loosening V1 locks.

## What remains locked

Retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, PnL, wallets, private keys, live execution, paid APIs, scoring/ranking/confidence, retries, successors, and any second use of authorization `V2_9_8B_WINDOW_15M_AUTH_20260804T141128Z` remain locked. No new memory windows were created (162→162).

## Functionality Risks / Setbacks / Efficiency Blockers

- **Risk:** continuing to treat validation rejects as source outages will keep producing false `SOURCE_AVAILABILITY_FAILURE` terminals whenever the Pump tail yields non-migrate signatures.
- **Setback:** stage rewind after protocol advance can freeze market exploration while advertising “budget exhausted” with large remaining capacity—operator confusion and wasted authorized attempts.
- **Efficiency blocker:** holder/safety eight-unit reservation is protected correctly from stale polling, but the `<2` gate plus early terminal means those units never convert solitary market-ready rows into fully eligible depth.
- **Efficiency blocker:** forty protocol-due fresh nominations and six venue-unsupported alternates consume no protocol budget this run; without ordered protocol work they cannot become market-ready.
- **Forensic blocker:** discarding raw migrate transactions on reject prevents offline instruction-level audits; retain redacted/normalized instruction digests if future audits must prove mint multiplicity.

## Answers to the four audit questions (completion gate)

1. **Holder/safety:** not invoked because campaign requires ≥2 graduated/market-ready candidates; only one `MARKET_READY` existed; code does not wait for four before any holder call—it never reached the holder stage.
2. **Pump rejections → shared source failure:** both txs failed the pinned exactly-one migrate decode after successful transport; durable failures were counted as provider failures and marked the direct-Pump channel unavailable, which the shortage classifier maps to `SOURCE_AVAILABILITY_FAILURE` (classification defect; rule itself correct).
3. **46 CONTRACT_BLOCKED:** 38 protocol-confirmation-due fresh Pump-family nominations; 2 unsupported meteora venues; 6 alternate-pool `pump-fun` venue-support blocks from mint batch—table above; not left as vague “awaiting proof” only.
4. **18 unused ops:** not true flat exhaustion; stage cursor advanced to protocol after round 1, stranding further market_batching; holder/handoff reservations remained protected and unused; shared terminal prevented later stages. Capacity stranded by stage-ordering plus premature terminalization, not by spending the ceiling.

## Verification performed

- Static inspection of permanent discovery, eligible supply, pump contracts, direct migration, and campaign holder gate owners.
- Read-only artifact parsing (terminal, campaign report, wrapper).
- Read-only SQLite (`mode=ro`) queries and report/DB count reconciliation.
- `git diff --check` on the audit document at commit time.

No unit tests, providers, runtime, migrations, or live commands were run for this lane.

