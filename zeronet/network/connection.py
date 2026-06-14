import socket
import threading
import time
import os
import traceback
from typing import Dict, Any, Tuple, Optional

from zeronet.crypto.manager import CryptoManager
from zeronet.network.protocol import Protocol

class NetworkCallbacks:
    """
    Standard Python callback registry to allow running network components 
    independently of any GUI (PyQt6) or TUI (Textual) runtime.
    """
    def __init__(self):
        self.peer_discovered = []
        self.peer_removed = []
        self.message_received = []
        self.group_message_received = []
        self.file_offer_received = []
        self.file_offer_accepted = []
        self.file_offer_rejected = []
        self.file_progress = []
        self.file_completed = []
        self.file_failed = []

    def trigger(self, event_name: str, *args):
        listeners = getattr(self, event_name, [])
        for listener in listeners:
            try:
                listener(*args)
            except Exception as e:
                print(f"[Callbacks] Error calling listener for {event_name}: {e}")
                traceback.print_exc()


class PeerConnection:
    """
    Wraps an active socket to a specific peer, along with the derived E2E Fernet key.
    """
    def __init__(self, peer_id: str, peer_name: str, sock: socket.socket, fernet_key: bytes):
        self.peer_id = peer_id
        self.peer_name = peer_name
        self.socket = sock
        self.fernet_key = fernet_key
        self.lock = threading.Lock()

    def send(self, data: bytes):
        with self.lock:
            self.socket.sendall(data)

    def close(self):
        try:
            self.socket.close()
        except Exception:
            pass


class NetworkManager(threading.Thread):
    def __init__(self, username: str, device_id: str, default_port: int = 54321):
        super().__init__()
        self.daemon = True  # Exit cleanly when main thread drops
        self.username = username
        self.device_id = device_id
        self.default_port = default_port
        self.port = default_port
        
        self.callbacks = NetworkCallbacks()
        self.crypto = CryptoManager()
        
        # Sockets & Threading Control
        self.running = False
        self.server_socket = None
        
        # Peer Registry: peer_id -> { "name": name, "ip": ip, "port": port, "status": "online" }
        self.peers: Dict[str, Dict[str, Any]] = {}
        
        # Active Connections: peer_id -> PeerConnection
        self.connections: Dict[str, PeerConnection] = {}
        self.connections_lock = threading.Lock()
        
        # File transfer registry: transfer_id -> info
        self.file_transfers: Dict[str, Dict[str, Any]] = {}

    def run(self):
        """
        Runs the TCP listener loop.
        """
        self.running = True
        
        # Try to bind to default port, increment if busy
        bound = False
        while not bound:
            try:
                self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.server_socket.bind(('0.0.0.0', self.port))
                self.server_socket.listen(10)
                bound = True
                print(f"[NetworkManager] Listening on port {self.port}")
            except Exception as e:
                print(f"[NetworkManager] Port {self.port} in use, trying {self.port + 1}...")
                self.port += 1
                if self.port > 65535:
                    print("[NetworkManager] No ports available!")
                    return
        
        while self.running:
            try:
                self.server_socket.settimeout(1.0)
                try:
                    client_sock, addr = self.server_socket.accept()
                except socket.timeout:
                    continue
                
                print(f"[NetworkManager] Accepted connection from {addr}")
                t = threading.Thread(target=self._handle_incoming_connection, args=(client_sock, addr))
                t.daemon = True
                t.start()
            except Exception as e:
                if self.running:
                    print(f"[NetworkManager] Listener error: {e}")
                    traceback.print_exc()

    def stop(self):
        self.running = False
        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass
            
        with self.connections_lock:
            for conn in list(self.connections.values()):
                conn.close()
            self.connections.clear()

    def _handle_incoming_connection(self, client_sock: socket.socket, addr: Tuple[str, int]):
        """
        Handles key exchange for incoming connections and starts the message reader loop.
        """
        try:
            client_sock.settimeout(5.0)
            
            # Step 1: Read their KEY_EXCHANGE packet
            metadata, payload = Protocol.unpack_message(client_sock)
            if metadata.get("msg_type") != "KEY_EXCHANGE":
                print("[NetworkManager] Expected KEY_EXCHANGE as first packet")
                client_sock.close()
                return
            
            peer_id = metadata["sender_id"]
            peer_name = metadata["sender_name"]
            peer_public_key_bytes = payload
            
            # Step 2: Derive key and encrypt/decrypt messages
            fernet_key = self.crypto.derive_shared_fernet_key(peer_public_key_bytes)
            
            # Step 3: Send our KEY_EXCHANGE packet in response
            response_pkt = Protocol.create_key_exchange(self.username, self.device_id, self.crypto.get_public_bytes())
            client_sock.sendall(response_pkt)
            
            # Key exchange complete! Create PeerConnection
            client_sock.settimeout(None)  # Reset timeout to blocking
            conn = PeerConnection(peer_id, peer_name, client_sock, fernet_key)
            
            with self.connections_lock:
                if peer_id in self.connections:
                    self.connections[peer_id].close()
                self.connections[peer_id] = conn
            
            # Update/Verify they are in our peers list
            if peer_id not in self.peers:
                self.peers[peer_id] = {
                    "name": peer_name,
                    "ip": addr[0],
                    "port": addr[1],
                    "status": "online"
                }
            self.callbacks.trigger("peer_discovered", peer_id, peer_name, addr[0], addr[1])
            
            print(f"[NetworkManager] E2E Encryption established with {peer_name} ({peer_id})")
            
            self._peer_reader_loop(conn)
            
        except Exception as e:
            print(f"[NetworkManager] Error handling incoming from {addr}: {e}")
            traceback.print_exc()
            try:
                client_sock.close()
            except Exception:
                pass

    def _peer_reader_loop(self, conn: PeerConnection):
        """
        Loops on the socket to read messages until connection drops.
        """
        peer_id = conn.peer_id
        peer_name = conn.peer_name
        
        while self.running:
            try:
                metadata, payload = Protocol.unpack_message(conn.socket)
                msg_type = metadata.get("msg_type")
                
                if msg_type == "TEXT_CHAT":
                    plaintext = self.crypto.decrypt_message(conn.fernet_key, payload)
                    self.callbacks.trigger("message_received", peer_id, peer_name, plaintext, metadata["timestamp"])
                    
                elif msg_type == "GROUP_TEXT_CHAT":
                    plaintext = self.crypto.decrypt_message(conn.fernet_key, payload)
                    self.callbacks.trigger(
                        "group_message_received", 
                        peer_id, 
                        peer_name, 
                        metadata["group_id"], 
                        metadata["group_name"], 
                        plaintext, 
                        metadata["timestamp"]
                    )
                    
                elif msg_type == "FILE_OFFER":
                    extra = metadata.get("extra", {})
                    file_name = extra.get("file_name")
                    file_size = extra.get("file_size")
                    transfer_id = extra.get("transfer_id")
                    self.callbacks.trigger("file_offer_received", peer_id, peer_name, file_name, file_size, transfer_id)
                    
                elif msg_type == "FILE_ACCEPT":
                    extra = metadata.get("extra", {})
                    transfer_id = extra.get("transfer_id")
                    file_port = extra.get("file_port")
                    self.callbacks.trigger("file_offer_accepted", peer_id, transfer_id, file_port)
                    
                elif msg_type == "FILE_REJECT":
                    extra = metadata.get("extra", {})
                    transfer_id = extra.get("transfer_id")
                    self.callbacks.trigger("file_offer_rejected", peer_id, transfer_id)
                    
                elif msg_type == "HEARTBEAT":
                    pass
                    
            except Exception as e:
                print(f"[NetworkManager] Connection to {peer_name} dropped: {e}")
                break
                
        with self.connections_lock:
            if peer_id in self.connections and self.connections[peer_id] is conn:
                del self.connections[peer_id]
        conn.close()

    def get_or_create_connection(self, peer_id: str) -> PeerConnection:
        with self.connections_lock:
            if peer_id in self.connections:
                return self.connections[peer_id]
                
        peer_info = self.peers.get(peer_id)
        if not peer_info:
            raise ConnectionError(f"Peer {peer_id} not discovered/known")
            
        ip = peer_info["ip"]
        port = peer_info["port"]
        peer_name = peer_info["name"]
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5.0)
        sock.connect((ip, port))
        
        # Perform Key Exchange
        my_pub_bytes = self.crypto.get_public_bytes()
        exchange_pkt = Protocol.create_key_exchange(self.username, self.device_id, my_pub_bytes)
        sock.sendall(exchange_pkt)
        
        metadata, payload = Protocol.unpack_message(sock)
        if metadata.get("msg_type") != "KEY_EXCHANGE":
            sock.close()
            raise ConnectionError("Key exchange failed: expected public key in response")
            
        peer_pub_bytes = payload
        fernet_key = self.crypto.derive_shared_fernet_key(peer_pub_bytes)
        
        sock.settimeout(None)
        conn = PeerConnection(peer_id, peer_name, sock, fernet_key)
        
        with self.connections_lock:
            if peer_id in self.connections:
                sock.close()
                return self.connections[peer_id]
            self.connections[peer_id] = conn
            
        t = threading.Thread(target=self._peer_reader_loop, args=(conn,))
        t.daemon = True
        t.start()
        
        return conn

    def send_direct_message(self, peer_id: str, message_text: str):
        conn = self.get_or_create_connection(peer_id)
        encrypted_bytes = CryptoManager.encrypt_message(conn.fernet_key, message_text)
        pkt = Protocol.create_text_chat(self.username, self.device_id, encrypted_bytes)
        conn.send(pkt)

    def send_group_message(self, group_id: str, group_name: str, member_ids: list, message_text: str):
        for member_id in member_ids:
            if member_id == self.device_id:
                continue
            try:
                conn = self.get_or_create_connection(member_id)
                encrypted_bytes = CryptoManager.encrypt_message(conn.fernet_key, message_text)
                pkt = Protocol.create_group_chat(self.username, self.device_id, group_id, group_name, encrypted_bytes)
                conn.send(pkt)
            except Exception as e:
                print(f"[NetworkManager] Failed to send group message to member {member_id}: {e}")

    def offer_file(self, peer_id: str, file_path: str) -> str:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
            
        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        transfer_id = f"tx_{int(time.time())}_{file_name.replace(' ', '_')}"
        
        self.file_transfers[transfer_id] = {
            "role": "sender",
            "peer_id": peer_id,
            "file_path": file_path,
            "file_name": file_name,
            "file_size": file_size,
            "status": "offered"
        }
        
        conn = self.get_or_create_connection(peer_id)
        pkt = Protocol.create_file_offer(self.username, self.device_id, file_name, file_size, transfer_id)
        conn.send(pkt)
        return transfer_id

    def accept_file(self, peer_id: str, transfer_id: str, save_path: str):
        transfer_info = self.file_transfers.get(transfer_id)
        if not transfer_info:
            raise ValueError("Unknown transfer ID")
            
        transfer_info["save_path"] = save_path
        transfer_info["status"] = "accepted"
        
        file_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        file_sock.bind(('0.0.0.0', 0))
        file_sock.listen(1)
        file_port = file_sock.getsockname()[1]
        
        t = threading.Thread(target=self._file_receiver_server, args=(file_sock, transfer_id, peer_id))
        t.daemon = True
        t.start()
        
        conn = self.get_or_create_connection(peer_id)
        pkt = Protocol.create_file_accept(self.username, self.device_id, transfer_id, file_port)
        conn.send(pkt)

    def reject_file(self, peer_id: str, transfer_id: str):
        if transfer_id in self.file_transfers:
            self.file_transfers[transfer_id]["status"] = "rejected"
            
        conn = self.get_or_create_connection(peer_id)
        pkt = Protocol.create_file_reject(self.username, self.device_id, transfer_id)
        conn.send(pkt)

    def _file_receiver_server(self, file_sock: socket.socket, transfer_id: str, peer_id: str):
        file_sock.settimeout(10.0)
        client_sock = None
        f_write = None
        try:
            client_sock, addr = file_sock.accept()
            info = self.file_transfers[transfer_id]
            save_path = info["save_path"]
            file_size = info["file_size"]
            
            conn = self.get_or_create_connection(peer_id)
            fernet_key = conn.fernet_key
            
            f_write = open(save_path, "wb")
            bytes_received = 0
            
            client_sock.settimeout(5.0)
            while bytes_received < file_size:
                metadata, payload = Protocol.unpack_message(client_sock)
                if metadata.get("msg_type") != "FILE_CHUNK":
                    raise ValueError("Expected FILE_CHUNK message type")
                
                decrypted_chunk = CryptoManager.decrypt_data(fernet_key, payload)
                f_write.write(decrypted_chunk)
                bytes_received += len(decrypted_chunk)
                
                self.callbacks.trigger("file_progress", transfer_id, bytes_received, file_size)
                
            f_write.close()
            f_write = None
            
            info["status"] = "completed"
            self.callbacks.trigger("file_completed", transfer_id, save_path)
            
        except Exception as e:
            print(f"[NetworkManager] File receiver error: {e}")
            traceback.print_exc()
            if f_write:
                try:
                    f_write.close()
                except Exception:
                    pass
                try:
                    os.remove(save_path)
                except Exception:
                    pass
            self.callbacks.trigger("file_failed", transfer_id, str(e))
        finally:
            file_sock.close()
            if client_sock:
                client_sock.close()

    def start_file_upload(self, peer_id: str, transfer_id: str, file_port: int):
        t = threading.Thread(target=self._file_sender_client, args=(peer_id, transfer_id, file_port))
        t.daemon = True
        t.start()

    def _file_sender_client(self, peer_id: str, transfer_id: str, file_port: int):
        info = self.file_transfers.get(transfer_id)
        if not info:
            return
            
        file_path = info["file_path"]
        file_size = info["file_size"]
        
        peer_info = self.peers.get(peer_id)
        if not peer_info:
            self.callbacks.trigger("file_failed", transfer_id, "Peer went offline")
            return
            
        peer_ip = peer_info["ip"]
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5.0)
        try:
            sock.connect((peer_ip, file_port))
            
            conn = self.get_or_create_connection(peer_id)
            fernet_key = conn.fernet_key
            
            bytes_sent = 0
            chunk_size = 64 * 1024
            
            sock.settimeout(5.0)
            with open(file_path, "rb") as f_read:
                while bytes_sent < file_size:
                    chunk = f_read.read(chunk_size)
                    if not chunk:
                        break
                        
                    encrypted_chunk = CryptoManager.encrypt_data(fernet_key, chunk)
                    
                    metadata = {"msg_type": "FILE_CHUNK", "timestamp": time.time()}
                    pkt = Protocol.pack_message(metadata, encrypted_chunk)
                    
                    sock.sendall(pkt)
                    bytes_sent += len(chunk)
                    
                    self.callbacks.trigger("file_progress", transfer_id, bytes_sent, file_size)
                    
            info["status"] = "completed"
            self.callbacks.trigger("file_completed", transfer_id, file_path)
            
        except Exception as e:
            print(f"[NetworkManager] File sender error: {e}")
            traceback.print_exc()
            self.callbacks.trigger("file_failed", transfer_id, str(e))
        finally:
            sock.close()
