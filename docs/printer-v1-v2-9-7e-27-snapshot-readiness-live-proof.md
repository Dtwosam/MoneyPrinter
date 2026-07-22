# Printer V1 V2-9.7E.27 Snapshot Readiness Live Proof

## Verdict

`V2_9_7E_27_BLOCKED_SOURCE_RELIABILITY`

E.27 stopped during preflight before any provider request. The committed
GeckoTerminal implementation and its adopted source contract disagree on the
required API version header and free/public rate ceiling. A live proof cannot
bypass that contradiction. The one-cycle authorization was not consumed, but
this lane is terminal and will not reuse it.

## Baseline and authorization

- Exact baseline: `956ad7616efccd4e571811d9128d8743de7a1eee`
- Baseline message: `Repair snapshot readiness contract`
- Tracked tree before preflight: clean
- Authorization: one bounded live readiness cycle
- External requests made: zero
- Authorization consumed: no
- Second execution, retry, rotation, reconnect or successor: none

## Source-stack preflight blocker

The Source Governor rules specifically permit
`geckoterminal_ohlcv_15m` and `geckoterminal_pool_trades_15m` only in a
separately authorized readiness proof. That permission does not resolve two
contradictions in the applicable provider contract:

1. `geckoterminal-api-contract.md` adopts
   `Accept: application/json;version=20230203` and explicitly states that the
   implementation's `version=20230302` header must be reconciled before network
   use. `geckoterminal_15m.py` still sends `version=20230302`.
2. The same contract adopts the stricter keyless ceiling of 10 calls/minute and
   requires the discrepancy to be rechecked before implementation. The source
   registry still configures GeckoTerminal at 30 calls/minute.

The planned E.27 cycle would require four live GeckoTerminal transports. It
would remain numerically below either per-minute ceiling, but the configured
Governor contract is still not the adopted contract. A proof cannot establish
source compliance by assuming the mismatch is harmless.

No production repair was made because E.27 is a live proof lane. No request was
sent to DexScreener, GeckoTerminal, Pump, GoPlus, public Solana RPC or Helius.

## Runtime and isolation preflight

- Process inspection found no active Printer Python/runtime process.
- Seven isolated PrinterPilot databases were inspected read-only. None had an
  active proof-supervision or campaign-supervision row.
- No PrinterPilot lock file existed.
- The operator-owned Helius Free secret was present through the committed
  runtime environment mechanism. Only presence was checked; the value was not
  printed, persisted, logged or copied into evidence.
- A fresh isolated DB was created at
  `C:\Users\dtwof\PrinterPilot\E27\printer-v1-e27-readiness.sqlite3`.
- The redacted preflight report is under
  `C:\Users\dtwof\PrinterPilot\E27\reports\`.
- Migration `039_snapshot_readiness_contract_repair.sql` is the latest applied
  migration, including `reserved_snapshot_completion_operations`.
- Integrity is `ok`; foreign-key violations are zero.
- All locked memory, retrieval and financial tables had zero baseline rows.
- The committed operation ceiling is 45, candidate cap is 3, and the complete
  two-candidate snapshot reservation is 6 operations.

## Execution, accounting and evidence outcome

The live execution did not begin. Consequently:

| Account | Count |
|---|---:|
| External/provider requests | 0 |
| Source requests/responses/failures persisted | 0 / 0 / 0 |
| Holder candidates evaluated | 0 |
| Holder-eligible candidates | 0 |
| DexScreener readiness bases | 0 |
| GeckoTerminal OHLCV/trades requests | 0 / 0 |
| Readiness snapshots | 0 |
| Charged operations | 0 |

This is not an insufficient-pool or snapshot-data verdict: neither gate was
reached. The first terminal cause is the pre-request source-contract conflict.

## Cleanup, integrity and zero-source replay

Because no campaign graph or source execution was started, cleanup is already
terminal:

- campaigns/runs/cycles: zero;
- active Scheduler work: zero;
- active tracking rows: zero;
- source request/response/failure rows: zero;
- lifecycle windows and memory rows: zero;
- retrieval, decisions, positions, trade events, audits and PnL: zero;
- integrity: `ok`;
- foreign-key violations: zero.

The redacted DB-only preflight replay made zero source requests and produced
report SHA-256
`049c0ad9d83060f32aa6f6e582a06089bf51d79959326209ed9ad0da7fbb80c6`.
The PASS replay gate is not claimed because the live cycle never began.

## Money-usefulness contribution

The block prevents a source proof from being called successful while its actual
request header and Governor ceiling contradict the adopted provider contract.
That protects future liquidity and 15m microstructure evidence from ambiguous
version behavior and preserves honest operation accounting before clean memory
or paper-money usefulness can be claimed.

## Functionality Risks / Setbacks / Efficiency Blockers

- E.26 granted request-kind permission without reconciling the older
  GeckoTerminal runtime version header against the adopted official contract.
- The registry's 30/min value remains looser than the adopted 10/min ceiling.
- The issue is deterministic and preflight-visible, so consuming the sole live
  authorization would add cost and ambiguity without producing compliant
  evidence.
- No holder or snapshot reliability conclusion can be drawn from this lane
  because zero providers were contacted.
- The fresh E.27 DB and redacted preflight evidence must not be treated as a
  completed readiness cycle or reused as authority for a pilot.

## Proof required before another live readiness cycle

A separate design/repair lane must freeze one official GeckoTerminal version
header, align the implementation and contract, reduce the registry/Governor
ceiling to the adopted free/public limit, and prove offline that both fixed
readiness request kinds preserve exact pool identity, no retry/rotation,
operation charging and fail-closed response handling. Only then may an operator
consider a newly authorized bounded live readiness cycle.

## What remains locked

This block does not authorize another E.27 execution, the full V2-9.7E pilot,
lifecycle windows, memory generation/promotion, corpus mutation, retrieval,
paper decisions, BUY/SELL/HOLD, positions, trades, audits, PnL, wallets, paid
sources, V2-9.7F or V2-9.8.
