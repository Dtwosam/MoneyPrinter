"""Checkpoint 3 in-place guards for discovery, handoff, and source scope.

The connected GitHub surface cannot apply a unified diff to the two large owner
modules without replacing their complete contents.  This package-local installer
therefore changes only the three RED-proven contracts on their existing module
objects and executor class.  It creates no second discovery engine, selector,
Source Governor, Scheduler owner, retry path, or runtime entry point.
"""

from __future__ import annotations

from functools import wraps
import importlib
from typing import Any


_GUARD_VERSION = "V2_9_8B_WINDOW_15M_CHECKPOINT_3_GUARDS_V1"


def install_checkpoint3_guards() -> None:
    """Install the three deterministic Checkpoint 3 repairs exactly once."""
    combined = importlib.import_module(
        "printer_v1.discovery.combined_executor"
    )
    permanent = importlib.import_module(
        "printer_v1.discovery.permanent_discovery_availability"
    )
    executor_class = combined.CombinedPumpfunCampaignExecutor
    if getattr(executor_class, "_checkpoint3_guard_version", None) == _GUARD_VERSION:
        return

    original_direct_lane = executor_class._run_direct_lane
    original_handoff_one_slot = executor_class._handoff_one_slot

    @wraps(original_direct_lane)
    def guarded_direct_lane(
        self: Any,
        connection: Any,
        command: Any,
        usage: Any,
        discovery_batch_id: str,
        existing: list[Any],
    ) -> list[Any]:
        fixtures = self.fixtures
        if "direct" not in fixtures.provider_failures_injected:
            return original_direct_lane(
                self,
                connection,
                command,
                usage,
                discovery_batch_id,
                existing,
            )

        # A failure is evidence about a governed request.  Persist the exact
        # request identity before the failure and link both to the same work.
        del existing
        now = fixtures.evaluated_at
        work_id = self._create_work(
            connection,
            command,
            usage,
            discovery_batch_id,
            combined.DIRECT_WORK_TYPE,
            now,
        )
        self._set_diagnostic_stage("DISCOVERY_WORK_GOVERNED_EXECUTION")
        self._inject_diagnostic_fault("DISCOVERY_WORK_GOVERNED_EXECUTION")
        request_id = self._governed_request(
            connection,
            usage,
            source_name="solana_rpc",
            request_kind="pumpfun_create_event_subscription",
            now=now,
        )
        failure_id = self._store_failure(
            connection,
            usage,
            source_name="solana_rpc",
            request_kind="pumpfun_create_event_subscription",
            failure_type=fixtures.provider_failures_injected["direct"],
            now=now,
        )
        combined.link_discovery_work_source(
            connection,
            discovery_work_id=work_id,
            link_ordinal=1,
            source_request_id=request_id,
            source_failure_id=failure_id,
            now=now,
        )
        self._terminalize_work(
            connection,
            work_id,
            "FAILED",
            "DIRECT_PROVIDER_FAILED",
            now,
        )
        return []

    @wraps(original_handoff_one_slot)
    def guarded_handoff_one_slot(
        self: Any,
        connection: Any,
        command: Any,
        usage: Any,
        *,
        discovery_batch_id: str,
        selection_batch_id: str,
        candidate: Any,
        ordinal: int,
        cycle_seed: str,
        now: str,
        handoff_work: str,
        force_scheduler_failure: bool = False,
        force_duplicate_active: bool = False,
    ) -> None:
        mint = str(candidate.mint)
        pool = str(candidate.market_identity).rsplit(":", 1)[-1]
        pair_row = connection.execute(
            "SELECT token_id, base_token_mint "
            "FROM printer_pairs WHERE pair_address = ?",
            (pool,),
        ).fetchone()
        if pair_row is not None:
            token_row = connection.execute(
                "SELECT id FROM printer_tokens WHERE token_mint = ?",
                (mint,),
            ).fetchone()
            base_token_mint = pair_row["base_token_mint"]
            if (
                token_row is None
                or int(pair_row["token_id"]) != int(token_row["id"])
                or (
                    base_token_mint is not None
                    and str(base_token_mint) != mint
                )
            ):
                raise combined.CombinedDiscoveryError(
                    "PAIR_TOKEN_IDENTITY_MISMATCH"
                )

        return original_handoff_one_slot(
            self,
            connection,
            command,
            usage,
            discovery_batch_id=discovery_batch_id,
            selection_batch_id=selection_batch_id,
            candidate=candidate,
            ordinal=ordinal,
            cycle_seed=cycle_seed,
            now=now,
            handoff_work=handoff_work,
            force_scheduler_failure=force_scheduler_failure,
            force_duplicate_active=force_duplicate_active,
        )

    def request_key_belongs_to_root(
        request_key: str,
        request_key_root: str,
    ) -> bool:
        """Accept only the canonical root or one hyphen-delimited child."""
        key = str(request_key or "")
        root = str(request_key_root or "")
        if not key or not root:
            return False
        return key == root or key.startswith(f"{root}-")

    executor_class._run_direct_lane = guarded_direct_lane
    executor_class._handoff_one_slot = guarded_handoff_one_slot
    executor_class._checkpoint3_guard_version = _GUARD_VERSION
    permanent.request_key_belongs_to_root = request_key_belongs_to_root
