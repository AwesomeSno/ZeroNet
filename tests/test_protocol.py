import pytest
import socket
import threading
from zeronet.network.protocol import Protocol

def test_protocol_pack_unpack():
    metadata = {
        "sender_name": "Test User",
        "sender_id": "test_id_123",
        "msg_type": "TEST_CHAT",
        "timestamp": 123456789.0
    }
    payload = b"this is the payload content"
    
    packed = Protocol.pack_message(metadata, payload)
    assert len(packed) > 8
    
    # Test unpacking using a socket pair
    sock_a, sock_b = socket.socketpair()
    
    try:
        # Write to sock_a
        sock_a.sendall(packed)
        
        # Read from sock_b
        unpacked_meta, unpacked_payload = Protocol.unpack_message(sock_b)
        
        assert unpacked_meta == metadata
        assert unpacked_payload == payload
    finally:
        sock_a.close()
        sock_b.close()

def test_protocol_messages():
    sender_name = "Alice"
    sender_id = "alice_dev"
    
    # Test key exchange creation
    pub_key_bytes = b"publickeyderbytes"
    pkt = Protocol.create_key_exchange(sender_name, sender_id, pub_key_bytes)
    
    sock_a, sock_b = socket.socketpair()
    try:
        sock_a.sendall(pkt)
        meta, payload = Protocol.unpack_message(sock_b)
        assert meta["msg_type"] == "KEY_EXCHANGE"
        assert meta["sender_name"] == sender_name
        assert meta["sender_id"] == sender_id
        assert payload == pub_key_bytes
    finally:
        sock_a.close()
        sock_b.close()
