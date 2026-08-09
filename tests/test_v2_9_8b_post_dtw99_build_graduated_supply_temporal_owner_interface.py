"""V2-9.8B Post-DTW99 ``build_graduated_supply`` temporal-owner interface proof.

Closes the ``PRODUCTION_COMPOSITION_INTERFACE_FORWARDING_GAP`` that consumed the
DTW99 one-use authorization with::

    TypeError: build_graduated_supply() got an unexpected keyword argument
               'temporal_refresh_owner'

The DTW98 completion test replaced the front door with a permissive
``fake_build_graduated_supply(db_path, **kwargs)`` stub. A ``**kwargs`` stub
accepts every keyword by construction, so it accepted ``temporal_refresh_owner``
and reported the plumbing as working while the real signature rejected it.

This proof therefore keeps the **real** ``build_graduated_supply`` under test and
substitutes only the *lower-level* supply service, so the forwarded argument can
be captured. Every substitution is validated against the real lower-level
signature, so no undeclared keyword can be silently absorbed here either.

No provider/source calls, no authoritative database, no sleep, no network, no
authorization, no wrapper, no WINDOW_15M.
"""

from __future__ import annotations

import inspect
import unittest
from pathlib import Path
from typing import Any

from printer_v1.discovery import eligible_token_supply
from printer_v1.discovery.eligible_token_supply import (
    DEFAULT_DISCOVERY_OPERATION_BUDGET,
    run_persistent_eligible_token_supply,
)
from printer_v1.discovery.pre_lifecycle_temporal_acquisition import (
    PRE_LIFECYCLE_ACQUISITION_DURATION_SECONDS,
)
from printer_v1.operator_cli.graduated_supply_front_door import (
    build_graduated_supply,
)

#: Path that must never be created. ``permanent_availability`` defaults to
#: False, so the front door must reach the supply boundary without opening any
#: database at all.
_NEVER_CREATED_DB = Path("/nonexistent-dtw99-proof/never-created.sqlite3")


class _ReachedSupplyBoundary(Exception):
    """Raised by the captured lower-level service to stop before real work."""


class _Owner:
    """Stand-in temporal refresh owner. Identity is the only thing under test."""

    refresh_interval_seconds = 600


class BuildGraduatedSupplyTemporalOwnerInterfaceTest(unittest.TestCase):
    """The exact seam that consumed the DTW99 authorization."""

    def setUp(self) -> None:
        self._real_supply = eligible_token_supply.run_persistent_eligible_token_supply
        self._real_signature = inspect.signature(self._real_supply)
        self.captured: dict[str, Any] = {}
        self.migration_transport_calls = 0

    def tearDown(self) -> None:
        eligible_token_supply.run_persistent_eligible_token_supply = self._real_supply

    def _migration_transport(self, _request: Any) -> dict[str, Any]:
        # Any invocation here would be provider work. It must never happen.
        self.migration_transport_calls += 1
        return {}

    def _install_capture(self) -> None:
        """Replace only the lower-level service, validating against its real signature."""
        real_signature = self._real_signature
        captured = self.captured

        def capturing_supply(db_path: Any, **kwargs: Any) -> None:
            # Reject anything the real lower-level service would reject, so this
            # substitute cannot hide a signature defect the way the DTW98 stub did.
            real_signature.bind(db_path, **kwargs)
            captured.update(kwargs)
            captured["__db_path__"] = db_path
            raise _ReachedSupplyBoundary()

        eligible_token_supply.run_persistent_eligible_token_supply = capturing_supply

    def _call_front_door(self, **extra: Any) -> None:
        """Invoke the REAL front door and stop at the supply boundary."""
        self._install_capture()
        with self.assertRaises(_ReachedSupplyBoundary):
            build_graduated_supply(
                _NEVER_CREATED_DB,
                cycle_seed="dtw99-proof-seed",
                migration_transport=self._migration_transport,
                **extra,
            )

    # 1. The required interface accepts a non-null temporal owner.
    def test_real_signature_accepts_non_null_temporal_refresh_owner(self) -> None:
        signature = inspect.signature(build_graduated_supply)
        self.assertIn(
            "temporal_refresh_owner",
            signature.parameters,
            "build_graduated_supply must declare temporal_refresh_owner",
        )
        parameter = signature.parameters["temporal_refresh_owner"]
        self.assertIs(parameter.default, None)
        self.assertEqual(parameter.kind, inspect.Parameter.KEYWORD_ONLY)
        self.assertFalse(
            any(p.kind is inspect.Parameter.VAR_KEYWORD for p in signature.parameters.values()),
            "a **kwargs catch-all would hide future signature defects",
        )
        # The exact DTW99 failure must now be impossible at this seam.
        signature.bind(
            _NEVER_CREATED_DB,
            cycle_seed="dtw99-proof-seed",
            migration_transport=self._migration_transport,
            temporal_refresh_owner=_Owner(),
        )

    # 2. The exact same object is forwarded (identity, not equality).
    def test_forwards_exact_object_identity_to_supply_service(self) -> None:
        owner = _Owner()
        self._call_front_door(temporal_refresh_owner=owner)
        self.assertIn("temporal_refresh_owner", self.captured)
        self.assertIs(
            self.captured["temporal_refresh_owner"],
            owner,
            "front door must forward the same object, not a copy or adapter",
        )

    def test_equal_but_distinct_owner_is_not_accepted_as_identity(self) -> None:
        """Guards the proof itself: equality must not be mistaken for identity."""
        owner = _Owner()
        self._call_front_door(temporal_refresh_owner=owner)
        self.assertIsNot(self.captured["temporal_refresh_owner"], _Owner())

    # 3. Omitted argument defaults/forwards as None.
    def test_omitted_temporal_owner_forwards_none(self) -> None:
        self._call_front_door()
        self.assertIn(
            "temporal_refresh_owner",
            self.captured,
            "front door must forward the parameter even when defaulted",
        )
        self.assertIsNone(self.captured["temporal_refresh_owner"])

    def test_explicit_none_forwards_none(self) -> None:
        self._call_front_door(temporal_refresh_owner=None)
        self.assertIsNone(self.captured["temporal_refresh_owner"])

    # 4. Zero provider/source calls.
    def test_no_provider_or_source_call_is_required(self) -> None:
        self._call_front_door(temporal_refresh_owner=_Owner())
        self.assertEqual(
            self.migration_transport_calls,
            0,
            "the interface proof must not require provider work",
        )

    # 5. No database is opened; the authoritative database is never touched.
    def test_no_database_is_opened(self) -> None:
        self._call_front_door(temporal_refresh_owner=_Owner())
        self.assertFalse(_NEVER_CREATED_DB.exists())
        self.assertFalse(_NEVER_CREATED_DB.parent.exists())
        self.assertEqual(self.captured["__db_path__"], _NEVER_CREATED_DB)

    # Lower-level contract remains the already-designed one.
    def test_lower_level_service_declares_the_parameter_unchanged(self) -> None:
        parameter = self._real_signature.parameters["temporal_refresh_owner"]
        self.assertIs(parameter.default, None)
        self.assertEqual(parameter.kind, inspect.Parameter.KEYWORD_ONLY)
        self.assertIs(
            run_persistent_eligible_token_supply,
            self._real_supply,
            "run_persistent_eligible_token_supply must not be modified",
        )

    # Invariants the repair must not disturb.
    def test_bounding_invariants_unchanged(self) -> None:
        self.assertEqual(PRE_LIFECYCLE_ACQUISITION_DURATION_SECONDS, 900)
        self.assertEqual(DEFAULT_DISCOVERY_OPERATION_BUDGET, 30)

    def test_default_discovery_budget_still_applied_when_unspecified(self) -> None:
        self._call_front_door(temporal_refresh_owner=_Owner())
        self.assertEqual(
            self.captured["discovery_operation_budget"],
            DEFAULT_DISCOVERY_OPERATION_BUDGET,
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
