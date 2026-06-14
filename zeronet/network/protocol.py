import struct
import json
import time
from typing import Tuple, Dict, Any

# Packet format:
# [4 bytes metadata_len (big-endian uint32)]
# [4 bytes payload_len (big-endian uint32)]
# [metadata_bytes (JSON UTF-8)]
# [payload_bytes (raw binary)]

class Protocol:
    @staticmethod
    def pack_message(metadata: Dict[str, Any], payload: bytes = b"") -> bytes:
        """
        Packs metadata (dict) and payload (bytes) into a framed network packet.
        """
        metadata_str = json.dumps(metadata)
        metadata_bytes = metadata_str.encode('utf-8')
        
        metadata_len = len(metadata_bytes)
        payload_len = len(payload)
        
        header = struct.pack("!II", metadata_len, payload_len)
        return header + metadata_bytes + payload

    @staticmethod
    def receive_exact(sock, length: int) -> bytes:
        """
        Helper to receive exactly 'length' bytes from the socket.
        Returns empty bytes if EOF/connection closed.
        """
        data = bytearray()
        while len(data) < length:
            packet = sock.recv(length - len(data))
            if not packet:
                return b""  # Connection closed
            data.extend(packet)
        return bytes(data)

    @classmethod
    def unpack_message(cls, sock) -> Tuple[Dict[str, Any], bytes]:
        """
        Reads a framed packet from a socket and unpacks it.
        Returns (metadata_dict, payload_bytes).
        Raises ConnectionError or ValueError if socket fails or frame is invalid.
        """
        header = cls.receive_exact(sock, 8)
        if not header:
            raise ConnectionError("Connection closed while reading header")
            
        metadata_len, payload_len = struct.unpack("!II", header)
        
        # Guard against absurd sizes (dos mitigation)
        if metadata_len > 10 * 1024 * 1024:  # 10 MB limit for metadata
            raise ValueError(f"Metadata length too large: {metadata_len}")
        if payload_len > 100 * 1024 * 1024:  # 100 MB limit for single packet payload
            raise ValueError(f"Payload length too large: {payload_len}")

        metadata_bytes = cls.receive_exact(sock, metadata_len)
        if len(metadata_bytes) != metadata_len:
            raise ConnectionError("Connection closed while reading metadata")
            
        payload = cls.receive_exact(sock, payload_len)
        if len(payload) != payload_len:
            raise ConnectionError("Connection closed while reading payload")

        metadata_str = metadata_bytes.decode('utf-8')
        metadata = json.loads(metadata_str)
        
        return metadata, payload

    # Message creators for convenience
    @classmethod
    def create_key_exchange(cls, sender_name: str, sender_id: str, public_key_bytes: bytes) -> bytes:
        metadata = {
            "sender_name": sender_name,
            "sender_id": sender_id,
            "msg_type": "KEY_EXCHANGE",
            "timestamp": time.time()
        }
        return cls.pack_message(metadata, public_key_bytes)

    @classmethod
    def create_text_chat(cls, sender_name: str, sender_id: str, encrypted_bytes: bytes) -> bytes:
        metadata = {
            "sender_name": sender_name,
            "sender_id": sender_id,
            "msg_type": "TEXT_CHAT",
            "timestamp": time.time()
        }
        return cls.pack_message(metadata, encrypted_bytes)

    @classmethod
    def create_group_chat(cls, sender_name: str, sender_id: str, group_id: str, group_name: str, encrypted_bytes: bytes) -> bytes:
        metadata = {
            "sender_name": sender_name,
            "sender_id": sender_id,
            "msg_type": "GROUP_TEXT_CHAT",
            "group_id": group_id,
            "group_name": group_name,
            "timestamp": time.time()
        }
        return cls.pack_message(metadata, encrypted_bytes)

    @classmethod
    def create_file_offer(cls, sender_name: str, sender_id: str, file_name: str, file_size: int, transfer_id: str) -> bytes:
        metadata = {
            "sender_name": sender_name,
            "sender_id": sender_id,
            "msg_type": "FILE_OFFER",
            "timestamp": time.time(),
            "extra": {
                "file_name": file_name,
                "file_size": file_size,
                "transfer_id": transfer_id
            }
        }
        return cls.pack_message(metadata)

    @classmethod
    def create_file_accept(cls, sender_name: str, sender_id: str, transfer_id: str, file_port: int) -> bytes:
        metadata = {
            "sender_name": sender_name,
            "sender_id": sender_id,
            "msg_type": "FILE_ACCEPT",
            "timestamp": time.time(),
            "extra": {
                "transfer_id": transfer_id,
                "file_port": file_port
            }
        }
        return cls.pack_message(metadata)

    @classmethod
    def create_file_reject(cls, sender_name: str, sender_id: str, transfer_id: str) -> bytes:
        metadata = {
            "sender_name": sender_name,
            "sender_id": sender_id,
            "msg_type": "FILE_REJECT",
            "timestamp": time.time(),
            "extra": {
                "transfer_id": transfer_id
            }
        }
        return cls.pack_message(metadata)

    @classmethod
    def create_heartbeat(cls, sender_name: str, sender_id: str, status: str = "online") -> bytes:
        metadata = {
            "sender_name": sender_name,
            "sender_id": sender_id,
            "msg_type": "HEARTBEAT",
            "timestamp": time.time(),
            "extra": {
                "status": status
            }
        }
        return cls.pack_message(metadata)
