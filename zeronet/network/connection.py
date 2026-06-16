import socket
import threading
import time
import os
import logging
import traceback
from typing import Dict, Any, Tuple, Optional

from zeronet.crypto.manager import CryptoManager, CryptoSession
from zeronet.network.protocol import Protocol

logger = logging.getLogger(__name__)


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
                logger.error("Error calling listener for %s: %s", event_name, e)
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
    HEARTBEAT_INTERVAL = 30  # seconds between heartbeats
    CONNECTION_TIMEOUT = 10  # seconds for connect/handshake timeout
    MAX_RETRY_ATTEMPTS = 3

    def __init__(self, username: str, device_id: str, default_port: int = 54321):
        super().__init__()
        self.daemon = True  # Exit cleanly when main thread drops
        self.username = username
        self.device_id = device_id
        self.default_port = default_port
        self.port = default_port

        self.callbacks = NetworkCallbacks()

        # Sockets & Threading Control
        self.running = False
        self.server_socket = None

        # Peer Registry: peer_id -> { "name": name, "ip": ip, "port": port, "status": "online" }
        self.peers: Dict[str, Dict[str, Any]] = {}
        self.peers_lock = threading.Lock()

        # Active Connections: peer_id -> PeerConnection
        self.connections: Dict[str, PeerConnection] = {}
        self.connections_lock = threading.Lock()

        # File transfer registry: transfer_id -> info
        self.file_transfers: Dict[str, Dict[str, Any]] = {}
        self.file_transfers_lock = threading.Lock()

        # Pending outgoing connections (for deduplication)
        self._connecting: set = set()
        self._connecting_lock = threading.Lock()

        # Heartbeat thread
        self._heartbeat_thread: Optional[threading.Thread] = None

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
                logger.info("Listening on port %d", self.port)
            except Exception:
                logger.info("Port %d in use, trying %d...", self.port, self.port + 1)
                self.port += 1
                if self.port > 65535:
                    logger.error("No ports available!")
                    return

        # Start heartbeat thread
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._heartbeat_thread.start()

        while self.running:
            try:
                self.server_socket.settimeout(1.0)
                try:
                    client_sock, addr = self.server_socket.accept()
                except socket.timeout:
                    continue

                logger.info("Accepted connection from %s", addr)
                t = threading.Thread(target=self._handle_incoming_connection, args=(client_sock, addr), daemon=True)
                t.start()
            except Exception as e:
                if self.running:
                    logger.error("Listener error: %s", e)
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

    def _heartbeat_loop(self):
        """
        Periodically sends heartbeat packets to all connected peers.
        Detects dead connections and cleans them up.
        """
        while self.running:
            time.sleep(self.HEARTBEAT_INTERVAL)
            if not self.running:
                break

            with self.connections_lock:
                conn_list = list(self.connections.items())

            for peer_id, conn in conn_list:
                try:
                    hb_pkt = Protocol.create_heartbeat(self.username, self.device_id)
                    conn.send(hb_pkt)
                except Exception as e:
                    logger.warning("Heartbeat failed for %s: %s", conn.peer_name, e)
                    # Connection is dead, clean up
                    with self.connections_lock:
                        if peer_id in self.connections and self.connections[peer_id] is conn:
                            del self.connections[peer_id]
                    conn.close()
                    with self.peers_lock:
                        if peer_id in self.peers:
                            self.peers[peer_id]["status"] = "offline"
                    self.callbacks.trigger("peer_removed", peer_id)

    def _handle_incoming_connection(self, client_sock: socket.socket, addr: Tuple[str, int]):
        """
        Handles key exchange for incoming connections and starts the message reader loop.
        Uses per-connection CryptoSession for fresh ECDH keys.
        """
        try:
            client_sock.settimeout(self.CONNECTION_TIMEOUT)

            # Step 1: Read their KEY_EXCHANGE packet
            metadata, payload = Protocol.unpack_message(client_sock)
            if metadata.get("msg_type") != "KEY_EXCHANGE":
                logger.warning("Expected KEY_EXCHANGE as first packet from %s", addr)
                client_sock.close()
                return

            peer_id = metadata["sender_id"]
            peer_name = metadata["sender_name"]
            peer_public_key_bytes = payload

            # Connection deduplication: if we are already connecting outward to this peer,
            # use device_id comparison as tie-breaker (lower ID is the initiator).
            with self._connecting_lock:
                if peer_id in self._connecting:
                    if self.device_id < peer_id:
                        # We win as initiator, reject this incoming
                        logger.info("Dedup: rejecting incoming from %s (we are initiator)", peer_name)
                        client_sock.close()
                        return
                    # else: they win as initiator, accept this incoming and our outgoing will fail

            # Step 2: Create a fresh ECDH session for this connection
            session = CryptoManager.create_session()
            fernet_key = session.derive_shared_fernet_key(peer_public_key_bytes)

            # Step 3: Send our KEY_EXCHANGE packet in response
            response_pkt = Protocol.create_key_exchange(self.username, self.device_id, session.get_public_bytes())
            client_sock.sendall(response_pkt)

            # Key exchange complete! Create PeerConnection
            client_sock.settimeout(None)  # Reset timeout to blocking
            conn = PeerConnection(peer_id, peer_name, client_sock, fernet_key)

            with self.connections_lock:
                if peer_id in self.connections:
                    self.connections[peer_id].close()
                self.connections[peer_id] = conn

            # Update/Verify they are in our peers list
            with self.peers_lock:
                if peer_id not in self.peers:
                    self.peers[peer_id] = {
                        "name": peer_name,
                        "ip": addr[0],
                        "port": addr[1],
                        "status": "online"
                    }
                else:
                    self.peers[peer_id]["status"] = "online"
            self.callbacks.trigger("peer_discovered", peer_id, peer_name, addr[0], addr[1])

            logger.info("E2E Encryption established with %s (%s)", peer_name, peer_id)

            self._peer_reader_loop(conn)

        except Exception as e:
            logger.error("Error handling incoming from %s: %s", addr, e)
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
                    plaintext = CryptoManager.decrypt_message(conn.fernet_key, payload)
                    self.callbacks.trigger("message_received", peer_id, peer_name, plaintext, metadata["timestamp"])

                elif msg_type == "GROUP_TEXT_CHAT":
                    plaintext = CryptoManager.decrypt_message(conn.fernet_key, payload)
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
                    with self.file_transfers_lock:
                        self.file_transfers[transfer_id] = {
                            "role": "receiver",
                            "peer_id": peer_id,
                            "file_name": file_name,
                            "file_size": file_size,
                            "status": "offered"
                        }
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
                logger.info("Connection to %s dropped: %s", peer_name, e)
                break

        with self.connections_lock:
            if peer_id in self.connections and self.connections[peer_id] is conn:
                del self.connections[peer_id]
        conn.close()

        # Mark peer as offline if connection dropped
        with self.peers_lock:
            if peer_id in self.peers:
                self.peers[peer_id]["status"] = "offline"
        self.callbacks.trigger("peer_removed", peer_id)

    def get_or_create_connection(self, peer_id: str) -> PeerConnection:
        with self.connections_lock:
            if peer_id in self.connections:
                return self.connections[peer_id]

        with self.peers_lock:
            peer_info = self.peers.get(peer_id)
        if not peer_info:
            raise ConnectionError(f"Peer {peer_id} not discovered/known")

        ip = peer_info["ip"]
        port = peer_info["port"]
        peer_name = peer_info["name"]

        # Mark that we are connecting to this peer (for dedup)
        with self._connecting_lock:
            self._connecting.add(peer_id)

        # Retry connection with backoff
        last_error = None
        for attempt in range(self.MAX_RETRY_ATTEMPTS):
            try:
                # Check if another thread already connected while we waited
                with self.connections_lock:
                    if peer_id in self.connections:
                        with self._connecting_lock:
                            self._connecting.discard(peer_id)
                        return self.connections[peer_id]

                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(self.CONNECTION_TIMEOUT)
                sock.connect((ip, port))

                # Create a fresh ECDH session for this connection
                session = CryptoManager.create_session()

                # Perform Key Exchange
                exchange_pkt = Protocol.create_key_exchange(self.username, self.device_id, session.get_public_bytes())
                sock.sendall(exchange_pkt)

                metadata, payload = Protocol.unpack_message(sock)
                if metadata.get("msg_type") != "KEY_EXCHANGE":
                    sock.close()
                    raise ConnectionError("Key exchange failed: expected public key in response")

                peer_pub_bytes = payload
                fernet_key = session.derive_shared_fernet_key(peer_pub_bytes)

                sock.settimeout(None)
                conn = PeerConnection(peer_id, peer_name, sock, fernet_key)

                with self.connections_lock:
                    if peer_id in self.connections:
                        sock.close()
                        with self._connecting_lock:
                            self._connecting.discard(peer_id)
                        return self.connections[peer_id]
                    self.connections[peer_id] = conn

                # Mark peer as online
                with self.peers_lock:
                    if peer_id in self.peers:
                        self.peers[peer_id]["status"] = "online"

                with self._connecting_lock:
                    self._connecting.discard(peer_id)

                t = threading.Thread(target=self._peer_reader_loop, args=(conn,), daemon=True)
                t.start()

                return conn

            except Exception as e:
                last_error = e
                if attempt < self.MAX_RETRY_ATTEMPTS - 1:
                    backoff = (attempt + 1) * 0.5
                    logger.info("Connection attempt %d to %s failed, retrying in %.1fs...", attempt + 1, peer_name, backoff)
                    time.sleep(backoff)
                try:
                    sock.close()
                except Exception:
                    pass

        with self._connecting_lock:
            self._connecting.discard(peer_id)

        raise ConnectionError(f"Failed to connect to {peer_name} after {self.MAX_RETRY_ATTEMPTS} attempts: {last_error}")

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
                logger.error("Failed to send group message to member %s: %s", member_id, e)

    def offer_file(self, peer_id: str, file_path: str) -> str:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        transfer_id = f"tx_{int(time.time())}_{file_name.replace(' ', '_')}"

        with self.file_transfers_lock:
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
        with self.file_transfers_lock:
            transfer_info = self.file_transfers.get(transfer_id)
        if not transfer_info:
            raise ValueError("Unknown transfer ID")

        with self.file_transfers_lock:
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
        with self.file_transfers_lock:
            if transfer_id in self.file_transfers:
                self.file_transfers[transfer_id]["status"] = "rejected"

        conn = self.get_or_create_connection(peer_id)
        pkt = Protocol.create_file_reject(self.username, self.device_id, transfer_id)
        conn.send(pkt)

    def _file_receiver_server(self, file_sock: socket.socket, transfer_id: str, peer_id: str):
        file_sock.settimeout(10.0)
        client_sock = None
        f_write = None
        save_path = None
        try:
            client_sock, addr = file_sock.accept()
            with self.file_transfers_lock:
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

            with self.file_transfers_lock:
                info["status"] = "completed"
            self.callbacks.trigger("file_completed", transfer_id, save_path)

        except Exception as e:
            logger.error("File receiver error: %s", e)
            traceback.print_exc()
            if f_write:
                try:
                    f_write.close()
                except Exception:
                    pass
                if save_path:
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
        with self.file_transfers_lock:
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

            with self.file_transfers_lock:
                info["status"] = "completed"
            self.callbacks.trigger("file_completed", transfer_id, file_path)

        except Exception as e:
            logger.error("File sender error: %s", e)
            traceback.print_exc()
            self.callbacks.trigger("file_failed", transfer_id, str(e))
        finally:
            sock.close()
