import pytest
import socket
import threading
import time

from zeronet.network.connection import NetworkManager, NetworkCallbacks, PeerConnection
from zeronet.crypto.manager import CryptoManager, CryptoSession


def test_network_callbacks_trigger():
    """Test that NetworkCallbacks triggers registered listeners."""
    results = []
    cb = NetworkCallbacks()
    cb.peer_discovered.append(lambda pid, name, ip, port: results.append((pid, name, ip, port)))

    cb.trigger("peer_discovered", "id1", "Alice", "192.168.1.1", 54321)

    assert len(results) == 1
    assert results[0] == ("id1", "Alice", "192.168.1.1", 54321)


def test_network_callbacks_error_handling():
    """Test that callback errors don't crash the trigger."""
    cb = NetworkCallbacks()
    cb.peer_discovered.append(lambda *args: (_ for _ in ()).throw(ValueError("boom")))

    # Should not raise
    cb.trigger("peer_discovered", "id1", "Alice", "192.168.1.1", 54321)


def test_network_callbacks_multiple_listeners():
    """Test that multiple listeners all get called."""
    results_a = []
    results_b = []
    cb = NetworkCallbacks()
    cb.message_received.append(lambda *args: results_a.append(args))
    cb.message_received.append(lambda *args: results_b.append(args))

    cb.trigger("message_received", "p1", "Bob", "hi", 123.0)

    assert len(results_a) == 1
    assert len(results_b) == 1


def test_peer_connection_send_and_close():
    """Test PeerConnection wraps send/close correctly."""
    sock_a, sock_b = socket.socketpair()
    try:
        conn = PeerConnection("peer1", "TestPeer", sock_a, b"fake_key")
        conn.send(b"hello")
        data = sock_b.recv(1024)
        assert data == b"hello"
    finally:
        sock_a.close()
        sock_b.close()


def test_peer_connection_close():
    """Test PeerConnection.close() is safe to call multiple times."""
    sock_a, sock_b = socket.socketpair()
    conn = PeerConnection("peer1", "TestPeer", sock_a, b"fake_key")
    conn.close()
    conn.close()  # Should not raise
    sock_b.close()


def test_network_manager_init():
    """Test NetworkManager initializes with correct state."""
    nm = NetworkManager("TestUser", "test_device_123", default_port=55555)
    assert nm.username == "TestUser"
    assert nm.device_id == "test_device_123"
    assert nm.port == 55555
    assert nm.running is False
    assert len(nm.peers) == 0
    assert len(nm.connections) == 0


def test_crypto_session_per_connection():
    """Test that CryptoManager.create_session() creates independent sessions."""
    session_a = CryptoManager.create_session()
    session_b = CryptoManager.create_session()

    # Different sessions should have different public keys
    assert session_a.get_public_bytes() != session_b.get_public_bytes()


def test_per_connection_key_exchange():
    """Test ECDH key exchange with per-connection sessions produces matching keys."""
    # Simulate Alice initiating to Bob
    alice_session = CryptoManager.create_session()
    bob_session = CryptoManager.create_session()

    alice_pub = alice_session.get_public_bytes()
    bob_pub = bob_session.get_public_bytes()

    alice_key = alice_session.derive_shared_fernet_key(bob_pub)
    bob_key = bob_session.derive_shared_fernet_key(alice_pub)

    assert alice_key == bob_key

    # Now a second connection to a different peer
    charlie_session = CryptoManager.create_session()
    charlie_pub = charlie_session.get_public_bytes()

    alice_session2 = CryptoManager.create_session()
    alice_key2 = alice_session2.derive_shared_fernet_key(charlie_pub)
    charlie_key = charlie_session.derive_shared_fernet_key(alice_session2.get_public_bytes())

    assert alice_key2 == charlie_key
    # Different peer connections should have different keys
    assert alice_key != alice_key2
