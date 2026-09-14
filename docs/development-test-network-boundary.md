# Development test network boundary

Run repository verification with `.venv/bin/python -m pytest`. Root `conftest.py`
installs the test-only CPython audit hook before test collection. Importing the
`tests` package also installs it, including package-based unittest execution.
No production module imports this guard.

The hook rejects DNS resolution/reverse resolution, creation of non-Unix
sockets, and non-Unix connect/bind/datagram-send audit events. IPv4, IPv6, TCP,
UDP and loopback TCP are blocked. Blocking socket creation also prevents later
writes through a newly created connected socket. Unix sockets and socketpairs,
SQLite, and local filesystem I/O remain available.

`TEST_NETWORK_BLOCKED` reports the primitive and host/port or socket family.
It never prints request bodies, headers or provider URLs containing secrets.
The exception inherits directly from BaseException so provider `except Exception`
or `except OSError` handlers cannot convert a missing fixture into an ordinary
source failure. Pytest additionally fails teardown for unacknowledged blocks,
including faults caught by broad handlers or raised in worker threads. Only
network-guard regression tests acknowledge deliberately blocked operations;
acknowledgement never enables network access.

There is no environment-variable, marker, host allowlist or CLI live opt-out.
Use injected offline transports. An approved live operation belongs outside
this development test runner and still requires the repository's exact-identity
preflight and explicit operator approval; this document supplies no authority.

This is a Python test-process boundary, not an OS sandbox for arbitrary native
extensions or separately launched programs. A new process must load the test
infrastructure to receive the hook; tests must not launch external network tools.
Root conftest and package loading cover normal repository pytest verification.

## Relevant paths

- DexScreener, GeckoTerminal and public context adapters use urllib openers.
- Solana RPC, generic-present-pool, PumpSwap account batches and direct Pump
  migration use urllib HTTP transports; these converge on DNS and sockets.
- PumpPortal uses websockets/asyncio, which also converge on sockets and DNS.
- The inspected source modules do not use requests/httpx/aiohttp as separate
  transport owners. Future Python clients using these socket primitives are
  covered without adding provider URLs to the guard.
- Existing `fixture_success_transport`, provider transport injection points,
  `tests/support/window_15m_measured_frozen_transports.py`, and the accelerated
  lifecycle harness remain the normal offline mechanisms.

The cooperative-resume regression deliberately omits protocol injection and
proves the real default RPC path stops locally with no RPC response. Its normal
fixture proves discovery request reuse and a distinct offline governed protocol
confirmation under this same guard. The historical unintended RPC attempt
remains acknowledged; adding this boundary does not relabel it as zero calls.
