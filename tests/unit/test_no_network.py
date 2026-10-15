"""Story 9.1 AC 4: the guard really catches outside connections, so unit tests can't call real APIs."""

import socket

import httpx
import pytest


def test_a_connection_to_an_outside_host_is_recorded_and_refused(network_attempts):
    with pytest.raises(OSError):
        socket.create_connection(("example.com", 80), timeout=1)
    assert network_attempts and "example.com" in network_attempts[0]
    network_attempts.clear()  # this test did it on purpose


def test_a_direct_connect_to_an_ip_address_is_recorded_and_refused(network_attempts):
    with socket.socket() as sock:
        with pytest.raises(ConnectionRefusedError):
            sock.connect(("93.184.216.34", 443))
        assert sock.connect_ex(("93.184.216.34", 443)) == 111
    assert len(network_attempts) == 2
    network_attempts.clear()


def test_a_real_http_client_cannot_reach_the_alpha_vantage_or_openai_hosts(network_attempts):
    for url in ("https://www.alphavantage.co/query", "https://api.openai.com/v1/models", "https://serpapi.com/search.json"):
        with pytest.raises(httpx.ConnectError):
            httpx.get(url, timeout=2)
    assert len(network_attempts) == 3 and all("lookup" in a for a in network_attempts)
    network_attempts.clear()


def test_the_local_machine_is_still_reachable_because_tests_use_loopback(network_attempts):
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    with socket.create_connection(server.getsockname(), timeout=1):
        pass
    server.close()
    assert not network_attempts
