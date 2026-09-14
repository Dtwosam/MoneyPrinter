"""Enforce offline testing before collection, including non-package test files."""
import pytest

from tests.support.network_guard import install, take_unacknowledged

install()


@pytest.fixture(autouse=True)
def _reject_swallowed_network_faults():
    yield
    faults = take_unacknowledged()
    if faults:
        pytest.fail("Unacknowledged test network attempt(s):\n" + "\n".join(map(str, faults)))
