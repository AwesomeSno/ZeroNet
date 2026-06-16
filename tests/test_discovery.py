import pytest
from zeronet.network.discovery import get_local_ip


def test_get_local_ip_returns_string():
    """Test that get_local_ip returns a valid IP string."""
    ip = get_local_ip()
    assert isinstance(ip, str)
    assert len(ip) > 0
    # Should be a valid IPv4 format
    parts = ip.split(".")
    assert len(parts) == 4
    for part in parts:
        assert part.isdigit()
        assert 0 <= int(part) <= 255


def test_get_local_ip_not_empty():
    """get_local_ip should return either a real LAN IP or 127.0.0.1."""
    ip = get_local_ip()
    assert ip != ""
    assert ip != "0.0.0.0"
