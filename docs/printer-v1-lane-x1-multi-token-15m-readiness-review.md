# Printer V1 Lane X1 Multi-Token 15m Readiness Review

## 1. Status

Lane X1 is documentation/review only.

This document reviews whether Printer V1 is ready to move from the proven single-token 15m Memory Factory path toward a controlled two-token 15m design.

Lane X1 does not run runtime, fetch sources, mutate the DB, create snapshots, create memory, activate retrieval, create paper decisions, unlock BUY, SELL, or HOLD, open paper positions, create trade events, create audits, or create PnL.

## 2. Active Source-of-Truth Stack Checked

Reviewed source-of-truth and evidence files:

- `AGENTS.md`
- `docs/printer-v1-memory-growth-build-order.md`
- `docs/printer-v1-memory-growth-automation-audit.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`
- `lane-x1-manual-readiness-evidence-output.txt`

The raw manual evidence file is the main evidence source for this review.

## 3. Lane X1 Goal

Lane X1 must decide whether Printer is ready for a later implementation lane that supports more than one active 15m tracking token.

The immediate design target is intentionally narrow:

- exactly two operator-approved `TRACK_FAST` tokens
- `WINDOW_15M` only
- isolated proof DB
- deterministic A/B snapshot rotation
- separate evidence identity per token
- no 5m support integration
- no longer-window activation
- no retrieval, paper decision, BUY, SELL, HOLD, position, or PnL unlock

## 4. Verdict

Verdict: `PARTIAL_READY` for design review.

Runtime execution verdict: `NOT_READY`.

Reason:

- The current system has enough proven single-token 15m machinery to design the next step.
- The current runner and token-list validation still enforce exactly one approved `TRACK_FAST` token.
- `max_active_tokens` exists, but does not make multi-token runtime functional.
- No multi-token runner currently proves fair rotation, separate memory grouping, source-budget backoff, or isolated per-token evidence windows.

## 5. Current Proven Capabilities

The manual evidence and supporting audit show these capabilities are already proven:

- HEAD is `219584e Adopt memory growth build order`.
- Tag `printer-v1-memory-growth-build-order-adoption` points at HEAD.
- The active memory-growth doc says the current active lane is Lane X1.
- `AGENTS.md` contains the Memory Growth Build Order Anchor.
- `WINDOW_5M_MICRO_EVENT` remains support-only.
- Single-token `WINDOW_15M` Memory Factory behavior has been proven in earlier lanes.
- Scheduler job kinds and priorities exist.
- Source Governor boundaries exist.
- Coverage and gap audits exist.
- Repeatable evidence identity exists.
- Clean-memory retrieval reporting exists as read-only reporting, not retrieval activation.
- Financial and paper-decision locks remain policy-locked.

## 6. Evidence From Manual Inspection

Key evidence from `lane-x1-manual-readiness-evidence-output.txt`:

- `git log -1 --oneline` showed `219584e Adopt memory growth build order`.
- Tags pointing at HEAD included `printer-v1-memory-growth-build-order-adoption`.
- The active memory-growth build order identifies Lane X1 as `Multi-Token 15m Readiness Review`.
- `AGENTS.md` includes the Memory Growth Build Order Anchor and keeps `WINDOW_5M_MICRO_EVENT` support-only.
- `_load_and_validate_token_list` is found in `src/printer_v1/operator_cli/e2i_source_transport.py`.
- `_load_and_validate_token_list` is imported by E2J in `src/printer_v1/operator_cli/e2j_first_15m_cycle.py`.
- The Lane W automation audit states that `_load_and_validate_token_list` enforces exactly one approved `TRACK_FAST` token.
- E2H validates exactly one approved `TRACK_FAST` token for the first run.
- Lane U runner still describes the token list as exactly one `TRACK_FAST` token.
- CLI help still describes the token-list path as exactly one `TRACK_FAST` token.
- `run_memory_factory_cycle()` declares `max_active_tokens`, but the current path still passes through the single-token E2J/E2I validator.
- Scheduler priorities include token-level job kinds, but no multi-token runner currently exercises them.
- No runner-level source-budget or backoff gate is proven for larger multi-token operation.

The evidence file also records existing workspace dirtiness at the time of evidence collection. This review did not clean, alter, or rely on those files beyond using the evidence text.

## 7. Blockers

Hard blockers before runtime execution:

- `_load_and_validate_token_list` currently enforces exactly one approved `TRACK_FAST` token.
- E2J imports and uses that single-token validator.
- E2H first-run validation is still single-token.
- Lane U runner documentation and CLI help still describe exactly one `TRACK_FAST` token.
- `max_active_tokens` is declarative, not a functional multi-token scheduler or rotation mechanism.
- No two-token A/B snapshot rotation exists.
- No proof exists that two tokens get distinct 15m snapshot ranges and memory windows without mixing.
- No proof exists that source budget/backoff behavior remains safe under multi-token load.
- No proof exists that a two-token run leaves retrieval, paper decisions, BUY, SELL, HOLD, positions, and PnL locked.

Non-blockers for Lane X2:

- 5m support is not required for Lane X2.
- 1h, 4h, 12h, and 24h are not required for Lane X2.
- Discovery automation is not required for Lane X2.

## 8. Risks

Main risks for Lane X2:

- Token/pair mixing if snapshot rows or memory windows are grouped incorrectly.
- False confidence from `max_active_tokens` existing without working rotation.
- Source budget overrun if both tokens are snapshotted too aggressively.
- Duplicate evidence if retry or replay semantics are not idempotent per token.
- Starvation if token A receives more snapshots than token B.
- Dirty or incomplete windows being mistaken for clean memory.
- 5m support evidence accidentally entering main memory logic.
- Retrieval or paper-decision paths being triggered too early.
- Longer windows being accidentally enabled before 15m multi-token proof.

## 9. Required Lane X2 Design

Lane X2 should be a narrow implementation/proof lane for exactly two approved `TRACK_FAST` tokens.

Required design constraints:

- accept exactly two operator-approved `TRACK_FAST` token entries
- reject zero, one, three, or more approved `TRACK_FAST` entries for this proof
- reject `TRACK_NORMAL`, `WATCH_ONLY`, unapproved, malformed, duplicate, unsupported-chain, or placeholder entries
- run only `WINDOW_15M`
- use an isolated proof DB
- rotate deterministically between token A and token B
- preserve one source-governed snapshot path per token
- keep memory grouping isolated by token_id and pair_id
- stop cleanly if either token cannot produce valid governed evidence
- produce a proof report, not retrieval or paper decisions

## 10. Token-List Shape for Exactly Two Approved TRACK_FAST Tokens

Lane X2 token-list shape should be explicit and small:

```json
{
  "tokens": [
    {
      "token_mint": "TOKEN_A_SOLANA_MINT",
      "pair_address": "TOKEN_A_PAIR_ADDRESS",
      "chain": "solana",
      "tracking_lane": "TRACK_FAST",
      "operator_approved": true
    },
    {
      "token_mint": "TOKEN_B_SOLANA_MINT",
      "pair_address": "TOKEN_B_PAIR_ADDRESS",
      "chain": "solana",
      "tracking_lane": "TRACK_FAST",
      "operator_approved": true
    }
  ]
}
```

Required validation:

- exactly two entries
- exactly two approved `TRACK_FAST` entries
- both entries on `solana`
- token mints present and distinct
- pair addresses present and distinct unless a test explicitly proves same-token/different-pair isolation
- no placeholders
- no unapproved entries
- no non-`TRACK_FAST` lane for Lane X2

## 11. Two-Token Rotation Design

Lane X2 should use deterministic A/B rotation:

```text
tick 1: token A snapshot
tick 2: token B snapshot
tick 3: token A snapshot
tick 4: token B snapshot
...
window close: token A close/evaluate, token B close/evaluate
```

Rotation requirements:

- each token receives its own expected snapshot cadence
- each token has independent gap/coverage evaluation
- token A failure must not silently pollute token B
- token B failure must not silently pollute token A
- source failures remain visible per token
- stopped/failed token state is reported honestly
- the run exits cleanly without unbounded loops

## 12. Evidence Identity Requirements

Each token must have separate evidence identity:

- separate `token_id`
- separate `pair_id`
- separate snapshot sequence
- separate `snapshot_start_id`
- separate `snapshot_end_id`
- separate `window_start_at`
- separate `window_end_at`
- separate `memory_window_id`
- separate coverage/gap audit
- separate memory fingerprint or audit payload if memory is created
- separate duplicate/idempotency guard

The two-token proof must prove that one token's evidence cannot satisfy or overwrite the other token's memory window.

## 13. Memory Grouping and Isolation Requirements

Lane X2 must group by `(token_id, pair_id, window_kind, evidence identity)`.

Required isolation rules:

- token A snapshots cannot build token B memory
- token B snapshots cannot build token A memory
- same-token/different-pair evidence remains pair-isolated
- dirty or audit-only memory for one token does not block a distinct window for the other token
- duplicate evidence no-ops remain idempotent per token
- clean memory, if produced, is attached to the correct token/pair only
- no retrieval match rows are created
- no paper decision rows are created

## 14. Source-Budget Expectations

Lane X2 should keep budget intentionally conservative:

- exactly two `TRACK_FAST` tokens
- no discovery automation
- no broad candidate expansion
- no 5m support collection
- no 1h or longer-window collection
- no extra quote/safety refresh beyond what existing approved `WINDOW_15M` path requires

Expected source-budget posture:

- two tokens should remain materially safer than three to ten tokens
- every source request must go through Source Governor
- every source response or failure must be recorded honestly
- runner-level report must show source request/response/failure counts per token
- any rate-limit, stale, failed, or partial result must stop or downgrade honestly
- no automatic provider rotation or source spam

## 15. Stop Conditions

Lane X2 must stop if:

- token list has anything other than exactly two approved `TRACK_FAST` Solana tokens
- token mints or pair addresses are missing, duplicated, unsupported, or placeholder
- Source Governor rejects a source request
- source request/response/failure rows are not recorded
- either token misses required snapshot coverage
- window-close snapshot cannot be captured or verified
- source budget or rate limits become unsafe
- token/pair mixing is detected
- `WINDOW_5M_MICRO_EVENT` is treated as main memory
- `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, or `WINDOW_24H` is attempted
- retrieval rows or matches are created
- paper decisions are created
- BUY, SELL, or HOLD appears
- paper positions, trade events, audits, or PnL are created
- wallet, private-key, signing, live execution, paid API, scoring, ranking, confidence, weighted logic, embeddings, or vectors appear

## 16. Required Lane X2 Tests

Lane X2 should include tests proving:

- exactly two approved `TRACK_FAST` tokens are accepted
- one approved token is rejected for Lane X2
- three or more approved tokens are rejected for Lane X2
- unapproved tokens are rejected
- `TRACK_NORMAL`, `WATCH_ONLY`, and unsupported lanes are rejected
- duplicate token mints are rejected
- duplicate pair addresses are rejected unless explicitly testing pair-isolation behavior
- deterministic A/B snapshot rotation is followed
- each token receives its own snapshot range
- each token receives its own `memory_window_id`
- token A snapshots cannot create token B memory
- token B snapshots cannot create token A memory
- source rows are recorded per token
- source failures stop or downgrade without fake clean memory
- memory grouping is isolated by `(token_id, pair_id)`
- duplicate replay is idempotent per token
- no retrieval rows or matches are created
- no paper decisions are created
- no BUY, SELL, or HOLD is created
- no positions, trade events, audits, or PnL are created
- 5m support remains disabled or support-only
- 1h/4h/12h/24h remain blocked

## 17. Required Lane X2 Proof Report

Lane X2 proof report must include:

- token A mint and pair address
- token B mint and pair address
- token A snapshot ids
- token B snapshot ids
- token A `snapshot_start_id` and `snapshot_end_id`
- token B `snapshot_start_id` and `snapshot_end_id`
- token A memory window id, if created
- token B memory window id, if created
- per-token source request/response/failure counts
- per-token coverage state
- per-token memory quality result
- per-token dirty/audit-only blocker reasons, if any
- duplicate/idempotency result
- source-budget result
- lock status after exit
- retrieval row/match counts
- paper decision row counts
- BUY/SELL/HOLD counts
- paper position, trade event, audit, and PnL counts
- explicit statement that 5m support and longer windows remained off

## 18. Locked-State Verification

Lane X1 confirms the following must remain locked through Lane X2:

- retrieval activation
- paper decisions
- BUY
- SELL
- HOLD
- paper positions
- paper trade events
- paper audits
- PnL
- live execution
- wallet logic
- private keys
- signing
- paid API dependency
- scoring
- ranking
- confidence percentages
- weighted decision logic
- embeddings
- vectors

`WINDOW_5M_MICRO_EVENT` remains support-only and must not unlock anything by itself.

## 19. What Lane X2 Must Not Build

Lane X2 must not build:

- discovery automation
- multi-token discovery selection
- 5m support integration
- 1h, 4h, 12h, or 24h collection
- retrieval activation
- clean-memory retrieval matching
- paper decision creation
- BUY, SELL, or HOLD paths
- paper position activation
- trade events
- paper audits
- PnL
- live trading
- wallet/private-key/signing logic
- paid API dependency
- scoring, ranking, confidence, or weighted systems
- embeddings or vectors

## 20. Next Recommended Lane

Next recommended lane:

`Lane X2 - Two-Token Controlled 15m Proof`

Recommended status:

- implementation/proof lane
- exactly two approved `TRACK_FAST` tokens
- isolated proof DB
- `WINDOW_15M` only
- no retrieval or paper decision activation

## 21. Final Conclusion

Lane X1 verdict is `PARTIAL_READY` for design review.

Printer is not ready for multi-token runtime execution yet.

The single-token 15m path, scheduler contracts, evidence identity model, and source-governed boundaries provide a credible base for a two-token design. The hard blocker is that the current token-list validation and E2J/E2I/Lane U execution path still enforce exactly one approved `TRACK_FAST` token.

Lane X2 should implement the smallest possible two-token proof: exactly two approved `TRACK_FAST` Solana tokens, `WINDOW_15M` only, isolated DB, deterministic A/B snapshot rotation, separate memory windows, no token mixing, and all financial/retrieval/paper-trading locks preserved.

## Central Scheduler Boundary

Lane X2 must remain Central Scheduler-led.

A two-token `WINDOW_15M` proof may not create independent source loops, direct engine loops, background workers, or unmanaged token snapshot paths.

All token snapshot attempts, window-close attempts, lock handling, job status transitions, stop conditions, and final locked-state reporting must preserve the Central Scheduler boundary.

Lane X2 must prove that no token can bypass the Central Scheduler and that the two-token runner exits with no running scheduler jobs and no leaked scheduler locks.

## Exact Locked-State Phrase Check

Lane X1 and Lane X2 preserve the following exact locked-state requirements:

- no retrieval activation
- no paper decisions
- no BUY
- no SELL
- no HOLD
- no positions
- no PnL
- no live execution
- no wallet/private-key behavior
- no paid API dependency
- no scoring/ranking/confidence/weighted logic
- no dirty-memory decision support

