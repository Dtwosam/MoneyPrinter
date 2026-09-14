"""The test runner must stop missing transport injection before network I/O."""
import sys

import pytest

from tests.support.network_guard import expect_network_block


def test_dns_audit_boundary_is_installed_before_test_execution():
    # Emit the CPython pre-resolution event without calling DNS. Safe even red.
    with expect_network_block():
        sys.audit("socket.getaddrinfo", "missing-fixture.invalid", 443, 0, 0, 0)


def test_default_http_transport_cannot_resolve_or_connect():
    from printer_v1.sources.dexscreener import build_dexscreener_fresh_profiles_transport
    with expect_network_block():
        build_dexscreener_fresh_profiles_transport()(None)


def test_default_solana_rpc_transport_cannot_resolve_or_connect():
    from printer_v1.sources.generic_present_pool_account_batch import (
        build_generic_present_pool_account_batch_transport,
    )
    with expect_network_block():
        build_generic_present_pool_account_batch_transport(
            candidates=[{"mint": "offline-mint", "pool": "offline-pool"}],
        )(None)


def test_default_pumpportal_websocket_cannot_resolve_or_connect():
    from printer_v1.sources.pumpportal import build_pumpportal_live_transport
    with expect_network_block():
        build_pumpportal_live_transport()(None)


@pytest.mark.parametrize("family", [2, 10])
@pytest.mark.parametrize("kind", [1, 2])
def test_ipv4_ipv6_tcp_udp_socket_creation_is_blocked(family, kind):
    import socket
    with expect_network_block():
        socket.socket(family, kind)


def test_sqlite_files_and_unix_sockets_are_unaffected(tmp_path):
    import socket
    import sqlite3
    path = tmp_path / "local.txt"
    path.write_text("local")
    assert path.read_text() == "local"
    with sqlite3.connect(tmp_path / "local.sqlite3") as connection:
        connection.execute("CREATE TABLE evidence(value)")
        connection.execute("INSERT INTO evidence VALUES (42)")
        assert connection.execute("SELECT value FROM evidence").fetchone()[0] == 42
    left, right = socket.socketpair()
    try:
        left.sendall(b"local")
        assert right.recv(5) == b"local"
    finally:
        left.close()
        right.close()


def test_cooperative_resume_offline_fixture_still_passes(tmp_path, monkeypatch):
    from tests.test_v2_9_8b_four_concurrent_terminal_transaction_and_production_owner_proof import (
        test_cooperative_resume_reuses_governed_source_request,
    )
    test_cooperative_resume_reuses_governed_source_request(tmp_path, monkeypatch)


def test_omitted_cooperative_protocol_fixture_is_caught_before_rpc(tmp_path):
    import sqlite3
    from tests.test_v2_9_8b_four_concurrent_terminal_transaction_and_production_owner_proof import (
        test_cooperative_resume_reuses_governed_source_request,
    )

    class OmitProtocolInjection:
        def setattr(self, target, value):
            assert target == (
                "printer_v1.sources.generic_present_pool_account_batch."
                "build_generic_present_pool_account_batch_transport"
            )
            # Deliberately preserve the default builder for this regression.

    with expect_network_block():
        test_cooperative_resume_reuses_governed_source_request(tmp_path, OmitProtocolInjection())
    with sqlite3.connect(tmp_path / "gov-resume.sqlite3") as connection:
        # Only the offline DexScreener response exists; RPC never got a response.
        assert connection.execute(
            "SELECT COUNT(*) FROM printer_source_responses r JOIN printer_source_requests q "
            "ON q.id=r.source_request_id WHERE q.source_name='solana_rpc'"
        ).fetchone()[0] == 0


def test_swallowed_network_fault_still_fails_pytest(tmp_path):
    import subprocess
    from pathlib import Path
    probe = tmp_path / "test_swallowed.py"
    probe.write_text(
        "import sys\n"
        "def test_swallow():\n"
        "    try:\n"
        "        sys.audit('socket.getaddrinfo', 'missing-fixture.invalid', 443, 0, 0, 0)\n"
        "    except BaseException:\n"
        "        pass\n"
    )
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "conftest", "-p", "no:cacheprovider", str(probe)],
        cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True,
        timeout=30,
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert "Unacknowledged test network attempt" in result.stdout
    assert "TEST_NETWORK_BLOCKED: socket.getaddrinfo" in result.stdout
    assert "missing-fixture.invalid" in result.stdout


@pytest.mark.parametrize("operation", ["getaddrinfo", "gethostbyname", "gethostbyaddr"])
def test_dns_apis_fail_before_resolution(operation):
    import socket
    with expect_network_block():
        if operation == "getaddrinfo":
            socket.getaddrinfo("missing-fixture.invalid", 443)
        elif operation == "gethostbyaddr":
            socket.gethostbyaddr("192.0.2.1")
        else:
            socket.gethostbyname("missing-fixture.invalid")


def test_raw_socket_module_cannot_bypass_guard():
    import _socket
    with expect_network_block():
        _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
