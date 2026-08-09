from __future__ import annotations
import ast, json, os, shutil, subprocess, tempfile
from pathlib import Path

ROOT = Path.cwd()
RED = "95f9ffbd875352eb9df13422fb062427968354a9"
BRANCH = "agent/v2-9-8b-post-dtw96-permanent-supply-truth-repair-implementation"
PDA = Path("src/printer_v1/discovery/permanent_discovery_availability.py")
ETS = Path("src/printer_v1/discovery/eligible_token_supply.py")
FRONT = Path("src/printer_v1/operator_cli/graduated_supply_front_door.py")
LIVE = Path("src/printer_v1/operator_cli/authoritative_live_operational_campaign.py")
FILES = tuple(sorted(map(str, (PDA, ETS, FRONT, LIVE))))

def cmd(*a, cwd=ROOT, check=True, env=None):
    p = subprocess.run(a, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
    if check and p.returncode:
        raise RuntimeError(f"COMMAND_FAILED:{' '.join(a)}\n{p.stdout}")
    return p

def git(*a, cwd=ROOT, check=True):
    return cmd("git", *a, cwd=cwd, check=check)

def one(s, old, new, label):
    n = s.count(old)
    if n != 1:
        raise RuntimeError(f"ANCHOR_COUNT_MISMATCH:{label}:{n}")
    return s.replace(old, new, 1)

def rw(root, path, fn):
    p = root / path
    p.write_text(fn(p.read_text(encoding="utf-8")), encoding="utf-8")

def patch_pda(s):
    s = one(
        s,
        "def run_dexscreener_batch_market_resolution(\n",
        """def _bounded_geckoterminal_fallback_limit(*, unresolved_count: int, max_fallbacks: int | None) -> int:
    if type(unresolved_count) is not int or unresolved_count < 0:
        raise ValueError("INVALID_RECONCILIATION_FALLBACK_CAP")
    if max_fallbacks is not None and (type(max_fallbacks) is not int or max_fallbacks < 0):
        raise ValueError("INVALID_RECONCILIATION_FALLBACK_CAP")
    return min(6, unresolved_count, 6 if max_fallbacks is None else max_fallbacks)


def run_dexscreener_batch_market_resolution(
""",
        "pda.helper",
    )
    s = one(
        s,
        "    enable_geckoterminal_fallback: bool = False,\n    before_geckoterminal_request: Any | None = None,\n",
        "    enable_geckoterminal_fallback: bool = False,\n    max_geckoterminal_fallbacks: int | None = None,\n    before_geckoterminal_request: Any | None = None,\n",
        "pda.signature",
    )
    s = one(
        s,
        '        "calls_by_stage": {"market_batching": 0, "reconciliation": 0},\n',
        '        "calls_by_stage": {"market_batching": 0, "reconciliation": 0},\n        "reconciliation_fallback_suppressed_count": 0,\n',
        "pda.report",
    )
    s = one(
        s,
        "            for fallback_index, mint in enumerate(unresolved_for_fallback[:6], 1):\n",
        """            fallback_limit = _bounded_geckoterminal_fallback_limit(
                unresolved_count=len(unresolved_for_fallback),
                max_fallbacks=max_geckoterminal_fallbacks,
            )
            report["reconciliation_fallback_suppressed_count"] += (
                len(unresolved_for_fallback) - fallback_limit
            )
            for fallback_index, mint in enumerate(
                unresolved_for_fallback[:fallback_limit], 1
            ):
""",
        "pda.loop",
    )
    return s

def patch_ets(s):
    anchor = (
        'class EligibleTokenSupplyError(RuntimeError):\n'
        '    """Fail-closed eligible-token-supply fault."""\n'
        '\n\n'
        'def _utc_now_iso() -> str:\n'
    )
    replacement = (
        'class EligibleTokenSupplyError(RuntimeError):\n'
        '    """Fail-closed eligible-token-supply fault."""\n'
        '\n\n'
        'def _validate_reconciliation_stage_charge(*, offered: int, actual: int) -> int:\n'
        '    if type(offered) is not int or offered < 0 or type(actual) is not int or actual < 0 or actual > offered:\n'
        '        raise EligibleTokenSupplyError("RECONCILIATION_STAGE_CAPACITY_OVERRUN")\n'
        '    return actual\n'
        '\n\n'
        'def _apply_permanent_shortage_precedence(\n'
        '    *, shortage: str, last_stop_reason: str | None,\n'
        '    tracking_dispositions: Mapping[str, Mapping[str, Any]],\n'
        '    provider_failures: int, channels_unavailable: Sequence[str],\n'
        '    liquidity_source_unavailable: int, liquidity_stale_or_rate_limited: int,\n'
        '    liquidity_malformed_or_partial: int, true_budget_exhausted: bool,\n'
        '    duration_exhausted: bool,\n'
        ') -> str:\n'
        '    if liquidity_source_unavailable > 0: return SOURCE_AVAILABILITY_FAILURE\n'
        '    if liquidity_stale_or_rate_limited > 0: return STALE_EVIDENCE_SHORTAGE\n'
        '    if liquidity_malformed_or_partial > 0: return SOURCE_VISIBILITY_SHORTAGE\n'
        '    if provider_failures > 0 and channels_unavailable: return SOURCE_AVAILABILITY_FAILURE\n'
        '    if last_stop_reason == "DISCOVERY_OPERATION_BUDGET_EXHAUSTED" and true_budget_exhausted:\n'
        '        return BUDGET_EXHAUSTION\n'
        '    if duration_exhausted or last_stop_reason == "CAMPAIGN_DURATION_EXHAUSTED":\n'
        '        return DURATION_EXHAUSTION\n'
        '    if last_stop_reason == "LAWFUL_WORK_REMAINING_WITH_CAPACITY":\n'
        '        return DISCOVERY_ARCHITECTURE_FALSE_SHORTAGE\n'
        '    if any(not bool(x.get("eligible_for_evidence")) for x in tracking_dispositions.values()):\n'
        '        return TRACKING_STATE_CAPACITY_BLOCKED\n'
        '    return shortage\n'
        '\n\n'
        'def _utc_now_iso() -> str:\n'
    )
    s = one(s, anchor, replacement, "ets.helpers")
    s = one(
        s,
        "                permanent_report = run_dexscreener_batch_market_resolution(\n",
        '                reconciliation_offer = stage_budget.available("reconciliation")\n'
        "                permanent_report = run_dexscreener_batch_market_resolution(\n",
        "ets.offer",
    )
    s = one(
        s,
        "                    enable_geckoterminal_fallback=(\n                        enable_geckoterminal_reconciliation\n                    ),\n",
        "                    enable_geckoterminal_fallback=(\n                        enable_geckoterminal_reconciliation\n                    ),\n                    max_geckoterminal_fallbacks=reconciliation_offer,\n",
        "ets.cap",
    )
    s = one(
        s,
        """                reconciliation_calls = int(
                    permanent_report.get("calls_by_stage", {}).get(
                        "reconciliation", 0
                    )
                )
                if reconciliation_calls:
                    try:
                        stage_budget.consume(
                            "reconciliation", reconciliation_calls
                        )
                    except ValueError:
                        # Spend only what remains; do not invent budget.
                        remaining_recon = stage_budget.available("reconciliation")
                        if remaining_recon > 0:
                            stage_budget.consume(
                                "reconciliation", remaining_recon
                            )
                        else:
                            last_stop_reason = "DISCOVERY_OPERATION_BUDGET_EXHAUSTED"
                            break
""",
        """                reconciliation_calls = _validate_reconciliation_stage_charge(
                    offered=reconciliation_offer,
                    actual=int(permanent_report.get("calls_by_stage", {}).get("reconciliation", 0)),
                )
                if reconciliation_calls:
                    stage_budget.consume("reconciliation", reconciliation_calls)
""",
        "ets.charge",
    )
    a = "            # Source-evidence failures take precedence over a budget consumed by\n"
    b = "            certificate = ExhaustionCertificate(\n"
    if s.count(a) != 1:
        raise RuntimeError(f"ANCHOR_COUNT_MISMATCH:ets.precedence:{s.count(a)}")
    i = s.index(a)
    j = s.index(b, i)
    s = s[:i] + """            shortage = _apply_permanent_shortage_precedence(
                shortage=shortage,
                last_stop_reason=last_stop_reason,
                tracking_dispositions=tracking_dispositions,
                provider_failures=provider_failures,
                channels_unavailable=sorted(set(channels_unavailable)),
                liquidity_source_unavailable=liquidity_outcome_counts.get(LIQUIDITY_SOURCE_UNAVAILABLE, 0),
                liquidity_stale_or_rate_limited=liquidity_outcome_counts.get(LIQUIDITY_SOURCE_RATE_LIMITED_OR_STALE, 0),
                liquidity_malformed_or_partial=liquidity_outcome_counts.get(LIQUIDITY_RESPONSE_MALFORMED_OR_PARTIAL, 0),
                true_budget_exhausted=bool(true_flat_exhausted or true_stage_exhausted),
                duration_exhausted=bool(
                    last_stop_reason == "CAMPAIGN_DURATION_EXHAUSTED"
                    or (duration_remaining is not None and duration_remaining <= 0)
                ),
            )
""" + s[j:]
    return s

def patch_front(s):
    s = one(
        s,
        "def build_graduated_supply(\n",
        """def _compose_graduated_supply_ready(
    *, persistent_ready: bool, authority_ready: bool, supply_count: int,
    required_token_capacity: int, permanent_availability: bool,
) -> bool:
    selection_ready = bool(authority_ready) and int(supply_count) == int(required_token_capacity)
    return selection_ready and (not permanent_availability or bool(persistent_ready))


def build_graduated_supply(
""",
        "front.helper",
    )
    return one(
        s,
        "    ready = bool(authority.ready) and len(supply) == required_token_capacity\n",
        """    ready = _compose_graduated_supply_ready(
        persistent_ready=bool(persistent.ready),
        authority_ready=bool(authority.ready),
        supply_count=len(supply),
        required_token_capacity=required_token_capacity,
        permanent_availability=permanent_availability,
    )
""",
        "front.ready",
    )

def patch_live(s):
    s = one(
        s,
        "def _classify_graduation(proof: Any, *, graduation: Any) -> str:\n",
        """def _project_supply_exhaustion_certificate(supply_diagnostics: Mapping[str, Any]) -> Any | None:
    return supply_diagnostics.get("exhaustion_certificate")


def _classify_graduation(proof: Any, *, graduation: Any) -> str:
""",
        "live.helper",
    )
    s = one(
        s,
        '            "shortage_classification": supply_diagnostics.get(\n                "shortage_classification"\n            ),\n            "provider_failures": supply_diagnostics.get("provider_failures", 0),\n',
        '            "shortage_classification": supply_diagnostics.get(\n                "shortage_classification"\n            ),\n            "exhaustion_certificate": _project_supply_exhaustion_certificate(supply_diagnostics),\n            "provider_failures": supply_diagnostics.get("provider_failures", 0),\n',
        "live.pre",
    )
    return one(
        s,
        '                        "blocked_supply_reason": terminal,\n                        "shortage_classification": supply_diagnostics.get(\n',
        '                        "blocked_supply_reason": terminal,\n                        "exhaustion_certificate": _project_supply_exhaustion_certificate(supply_diagnostics),\n                        "shortage_classification": supply_diagnostics.get(\n',
        "live.terminal",
    )

def static(root):
    pda = (root / PDA).read_text()
    ets = (root / ETS).read_text()
    front = (root / FRONT).read_text()
    live = (root / LIVE).read_text()
    if "MINIMUM_FREEZE_DEPTH = 4" not in pda or "REQUIRED_TOKEN_CAPACITY = 2" not in ets:
        raise RuntimeError("LOCKED_CAPACITY_CHANGED")
    for x in (
        '("intake", 3)', '("market_batching", 2)', '("reconciliation", 6)',
        '("protocol_confirmation", 7)', '("holder_safety", 8)',
        '("final_refresh_handoff", 4)',
    ):
        if x not in pda:
            raise RuntimeError("LOCKED_STAGE_RESERVATIONS_CHANGED")
    seen = 0
    for n in ast.walk(ast.parse(ets)):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "run_dexscreener_batch_market_resolution":
            kw = {k.arg: k.value for k in n.keywords if k.arg}
            e = kw.get("enable_geckoterminal_fallback")
            if e is None or (isinstance(e, ast.Constant) and e.value is False):
                continue
            seen += 1
            if "max_geckoterminal_fallbacks" not in kw:
                raise RuntimeError("ENABLED_RECONCILIATION_CALL_MISSING_PRE_IO_CAP")
    if not seen:
        raise RuntimeError("CAPPED_RECONCILIATION_CALL_NOT_FOUND")
    if "_compose_graduated_supply_ready(" not in front or "_project_supply_exhaustion_certificate(" not in live:
        raise RuntimeError("IMPLEMENTATION_NOT_WIRED")

def main():
    if git("diff", "--quiet", check=False).returncode or git("diff", "--cached", "--quiet", check=False).returncode:
        raise RuntimeError("TRACKED_OR_INDEX_NOT_CLEAN")
    git("fetch", "origin", BRANCH)
    if git("rev-parse", "FETCH_HEAD").stdout.strip() != RED:
        raise RuntimeError("REMOTE_IMPLEMENTATION_HEAD_MOVED")
    w = Path(tempfile.mkdtemp(prefix="printer-dtw96-green."))
    shutil.rmtree(w)
    try:
        git("worktree", "add", "--detach", str(w), RED)
        rw(w, PDA, patch_pda)
        rw(w, ETS, patch_ets)
        rw(w, FRONT, patch_front)
        rw(w, LIVE, patch_live)
        static(w)
        changed = sorted(git("diff", "--name-only", cwd=w).stdout.splitlines())
        if changed != list(FILES):
            raise RuntimeError(f"IMPLEMENTATION_SCOPE_MISMATCH:{changed}")
        git("diff", "--check", cwd=w)
        py = ROOT / ".venv/bin/python"
        env = dict(os.environ)
        env["PYTHONPATH"] = str(w / "src")
        cmd(str(py), "-m", "py_compile", *(str(w / p) for p in (PDA, ETS, FRONT, LIVE)), cwd=w, env=env)
        t = cmd(
            str(py), "-m", "pytest", "-q",
            str(w / "tests/test_v2_9_8b_post_dtw96_supply_truth_repair.py"),
            str(w / "tests/test_v2_9_8b_post_dtw96_reconciliation_pre_io.py"),
            cwd=w, env=env,
        )
        c = cmd(
            str(py), "-m", "pytest", "-q",
            str(w / "tests/test_v2_9_8b_permanent_discovery_availability.py")
            + "::TestCanonicalBatchMarketOwner::test_unresolved_mint_cascades_to_geckoterminal_same_pool",
            cwd=w, env=env,
        )
        git("add", *FILES, cwd=w)
        git("commit", "-m", "Repair DTW96 permanent supply truth", cwd=w)
        sha = git("rev-parse", "HEAD", cwd=w).stdout.strip()
        if git("rev-parse", "HEAD^", cwd=w).stdout.strip() != RED:
            raise RuntimeError("PARENT_MISMATCH")
        git("fetch", "origin", BRANCH)
        if git("rev-parse", "FETCH_HEAD").stdout.strip() != RED:
            raise RuntimeError("REMOTE_MOVED_BEFORE_PUSH")
        git("push", "origin", f"{sha}:refs/heads/{BRANCH}", cwd=w)
        print(json.dumps({
            "status": "PASS",
            "verdict": "V2_9_8B_POST_DTW96_PERMANENT_SUPPLY_TRUTH_REPAIR_IMPLEMENTATION_FOCUSED_PROOF_PASS",
            "implementation_commit": sha,
            "changed_files_in_implementation_commit": list(FILES),
            "focused_green": t.stdout.strip().splitlines()[-1],
            "existing_fallback_compatibility": c.stdout.strip().splitlines()[-1],
            "py_compile": "PASS",
            "git_diff_check": "PASS",
            "authoritative_database_accessed": False,
            "printer_source_calls": 0,
            "scheduler_runtime_calls": 0,
            "authorization_created": False,
            "window_15m_started": False,
            "locked_stage_reservations": "3/2/6/7/8/4",
            "minimum_freeze_depth": 4,
            "active_selection_capacity": 2,
        }, indent=2, sort_keys=True))
    finally:
        git("worktree", "remove", str(w), "--force", check=False)
        shutil.rmtree(w, ignore_errors=True)

if __name__ == "__main__":
    main()
