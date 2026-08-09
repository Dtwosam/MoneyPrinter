# Printer V1 V2-9.8B — Post-DTW93 WINDOW_15M One-Shot Blocked Closeout

Date: 2026-08-09

## Verdict

`V2_9_8B_POST_DTW93_WINDOW_15M_ONE_SHOT_BLOCKED_HOST_AWAKE_LEASE_EXPIRY_WITH_SECONDARY_ACCOUNTING_AUDIT_REQUIRED`

The fresh one-use authorization was consumed exactly once. The real ordinary `WINDOW_15M` campaign started and made bounded progress, but did not earn campaign acceptance. Its immutable first terminal cause is `LEASE_RENEWAL_LEASE_EXPIRED`.

No retry, rerun, resume, restart, or successor is authorized.

## Exact attempt identity

- authorization ID: `V2_9_8B_WINDOW_15M_AUTH_20260808T215650Z`
- authorization SHA-256: `6b1500d00a7a309d0726dec9146ac30f04ee9fe4cdad72cbc8f0eae4231263d1`
- authorized Git branch: `agent/v2-9-8b-post-dtw92-window15m-authorization-preparation`
- authorized Git HEAD: `b85a42d404f41487497347a2e0fd9f778ff0ef2e`
- execution ID: `20260808T215802Z-8cd614da1094`
- campaign ID: `20260808T215802Z-8cd614da1094-campaign`
- run ID: `20260808T215802Z-8cd614da1094-campaign-run`
- wrapper child exit: `0`
- child terminal envelope: valid
- application marker consumed: `true`

A zero process exit is not treated as campaign PASS. The stored campaign verdict is `BLOCKED_UNSAFE`, `campaign_pass=false`, and `run_status=FAILED`.

## Controlling blocker classification

`CONFIG_OR_ENVIRONMENT_BLOCKER__NO_PRODUCT_CODE`

Durable heartbeat evidence shows:

- prior heartbeat: `2026-08-08T22:10:33.493667+00:00`
- lease expiry: `2026-08-08T22:12:03.493667+00:00`
- renewal attempt: `2026-08-08T22:12:40.388903+00:00`
- renewal confirmed: `false`
- SQLite locked: `false`
- safe category: `LEASE_EXPIRED`
- terminal cause: `LEASE_RENEWAL_LEASE_EXPIRED`

The renewal attempt arrived about 126.9 seconds after the prior heartbeat and about 36.9 seconds after the 90-second lease had already expired. The committed ordinary campaign uses a 30-second heartbeat and a 90-second lease and correctly fails closed when renewal is late.

This pattern matches the previously documented macOS host-suspension/process-freeze lease-expiry case. The operator runbook requires the Mac host-awake safeguard `caffeinate -dimsu` for a real bounded campaign. The DTW93 wrapper launch was issued without that safeguard. That omission is an operational launch defect, not evidence that the lease duration should be widened or the fail-closed supervision rule weakened.

Minimum safe correction for any later separately authorized attempt: preserve the existing lease contract and run the one-shot wrapper under the approved macOS host-awake safeguard.

## Campaign progress and safe stop

The campaign progressed beyond discovery/selection and entered both 15-minute lifecycles.

Observed before the lease failure:

- discovery/selection stages completed;
- both tokens completed snapshot jobs through `snapshot_06`;
- source transport owner/action-local identity totals matched `30/30`;
- lifecycle reservation identity totals matched `14/14`;
- Scheduler work identity totals matched `28/28`.

The lease failure occurred before `snapshot_07` and `WINDOW_CLOSE` could complete for either token. Scheduler jobs `1394`, `1395`, `1402`, and `1403` therefore did not reach the required claim/terminal coverage. No terminal current-run 15m windows were registered and no current-run clean-memory outcome was produced.

Terminal cleanup nevertheless behaved safely:

- supervision state: `TERMINAL`
- supervision terminal status: `FAILED`
- cleanup completed: yes
- lease released: yes
- lease lock absent after cleanup
- zero active owned work
- zero locked work
- zero retry/restart/resume/successor
- zero forbidden capability deltas

## Report-only replay

Exact-identity report-only replay was performed after the attempt and made:

- source calls: `0`
- Scheduler runtime calls: `0`
- database writes: `0`

Replay returned:

`REPLAY_BLOCKED / FULL_RUN_REPAIRED_EVIDENCE_INVALID`

This is not the first terminal cause and does not authorize a rerun. It is consistent with the stored full-run evidence being incomplete/blocked after the lease safe-stop.

## Secondary accounting finding — audit required

The retained full-run evidence also contains a separate owner/action-local reconciliation mismatch:

- owner `LOCAL_VALIDATION_STEP`: `80`
- action-local `LOCAL_VALIDATION_STEP`: `67`
- difference: `13`
- reconciliation reason: `LOCAL_VALIDATION_STEP:UNIT_IDENTITY_SET_MISMATCH`

The 13 owner-only validations correspond to `PROTOCOL_CONFIRMATION` PumpSwap account-validation identities. Static call-path inspection indicates the local-validation observer is carried into the eligible-supply path, while protocol-confirmation stage evidence seals its own local validation identities. Whether the action-local observer is omitted at that exact protocol boundary must be confirmed in a dedicated static/offline audit before any code change.

Classification for this secondary finding:

`AUDIT_REQUIRED_PENDING_COMMITTED_CODE_DEFECT_CONFIRMATION`

Do not attribute this mismatch to host sleep, and do not patch it from the live artifact alone.

## Money-usefulness contribution

The attempt proved the repaired discovery/selection route could enter and sustain both bounded 15m lifecycles through multiple real governed snapshots. It also exposed two operationally useful truths before corpus acceptance: host-awake protection remains required, and campaign acceptance correctly refuses incomplete or unreconciled evidence.

## What this attempt improves

- confirms the migration-053 route repair progressed into real lifecycle work;
- confirms first-cause preservation and fail-closed lease handling;
- confirms safe cleanup/release with no automatic successor;
- preserves the accounting mismatch as evidence for a focused audit rather than smoothing it over.

## What remains locked

No capability unlock results from this attempt. Still locked:

- any retry/rerun/resume/restart/successor under the consumed authorization;
- new real `WINDOW_15M` authorization until the secondary accounting audit is resolved;
- `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, `WINDOW_24H`;
- retrieval;
- paper decisions and BUY/SELL/HOLD;
- paper positions, trade events, trade audits, and PnL;
- wallets, private keys, signing, real funds, or live execution;
- paid API dependencies;
- scoring/ranking/confidence/weighted systems;
- embeddings/vectors.

`WINDOW_5M_MICRO_EVENT` remains support-only.

## Functionality Risks / Setbacks / Efficiency Blockers

- A sleeping/suspended Mac can miss multiple heartbeat intervals and force an honest lease-expiry terminal.
- A future run without `caffeinate -dimsu` would repeat a known operational risk.
- The 13-validation owner/action-local mismatch may independently block campaign acceptance even with host-awake protection; it must be audited before another live attempt.
- The consumed authorization cannot be repaired, edited, or reused.
- Widening lease/heartbeat limits as a shortcut would weaken the supervision contract and is not justified by this evidence.

## Next roadmap-compliant step

Open a static/offline audit of the `PROTOCOL_CONFIRMATION` local-validation observer propagation and the exact 13-identity mismatch. No source fetching, authoritative DB mutation, Printer runtime, new authorization, or real `WINDOW_15M` attempt is permitted in that audit.

If and only if the audit proves a committed-code defect, continue through the normal sequence: design/specification -> narrow implementation -> focused bounded offline proof -> closeout -> fresh readiness review. Only after those gates may a new one-use 15m authorization be considered, with the launch guarded by `caffeinate -dimsu`.