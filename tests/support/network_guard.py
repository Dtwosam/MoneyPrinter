"""Process-local, test-only CPython network boundary. No live opt-out."""
from contextlib import contextmanager
import socket
import sys


class TestNetworkBlocked(BaseException):
    """Not an Exception: provider recovery must not swallow a test-safety fault."""


_installed = False
_pending = []
_DNS_EVENTS = {
    "socket.getaddrinfo", "socket.gethostbyname", "socket.gethostbyaddr",
    "socket.getnameinfo",
}


def _audit(event, args):
    context = None
    if event in _DNS_EVENTS:
        # Host/service only; never include provider URLs, headers or credentials.
        context = repr(args[:2])
    elif event == "socket.__new__" and args[1] != socket.AF_UNIX:
        context = f"family={args[1]} type={args[2]} protocol={args[3]}"
    elif event in {"socket.connect", "socket.bind", "socket.sendto", "socket.sendmsg"}:
        if args[0].family != socket.AF_UNIX:
            context = repr(args[1:] if event in {"socket.connect", "socket.bind"} else "non-Unix socket")
    if context is not None:
        fault = TestNetworkBlocked(
            f"TEST_NETWORK_BLOCKED: {event} {context}; inject an offline transport. "
            "Development tests have no live-network authority."
        )
        _pending.append(fault)
        raise fault


def install():
    global _installed
    if not _installed:
        sys.addaudithook(_audit)
        _installed = True


def take_unacknowledged():
    faults = tuple(_pending)
    _pending.clear()
    return faults


@contextmanager
def expect_network_block():
    """Acknowledge exactly one deliberately blocked operation in a guard test."""
    try:
        yield
    except TestNetworkBlocked as fault:
        _pending.remove(fault)
    else:
        raise AssertionError("expected TEST_NETWORK_BLOCKED before network I/O")
