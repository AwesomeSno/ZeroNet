import base64
import logging
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)


class CryptoSession:
    """
    Represents a single ECDH key exchange session with one peer.
    Each peer connection gets its own CryptoSession with fresh ephemeral keys.
    """
    def __init__(self):
        self.private_key = ec.generate_private_key(ec.SECP256R1())
        self.public_key = self.private_key.public_key()

    def get_public_bytes(self) -> bytes:
        """Serializes our public key to DER format for sending over network."""
        return self.public_key.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )

    def derive_shared_fernet_key(self, peer_public_bytes: bytes) -> bytes:
        """
        Performs ECDH key exchange, derives a 32-byte shared key using HKDF,
        and returns a url-safe base64 encoded Fernet key.
        """
        peer_pub_key = serialization.load_der_public_key(peer_public_bytes)
        shared_secret = self.private_key.exchange(ec.ECDH(), peer_pub_key)

        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=None,
            info=b"zeronet-e2ee-key-derivation",
        )
        derived_key = hkdf.derive(shared_secret)
        return base64.urlsafe_b64encode(derived_key)


class CryptoManager:
    """
    Handles ECDH Key Exchange and E2E Fernet encryption/decryption.
    
    Each peer connection should create a new CryptoSession via create_session().
    The static encrypt/decrypt methods are used with the derived Fernet key.
    """

    @staticmethod
    def create_session() -> CryptoSession:
        """Creates a new ECDH session with fresh ephemeral keys."""
        return CryptoSession()

    # --- Legacy compatibility: instance-level session ---

    def __init__(self):
        self._session = CryptoSession()

    def get_public_bytes(self) -> bytes:
        """Serializes our public key to DER format for sending over network."""
        return self._session.get_public_bytes()

    @staticmethod
    def load_public_key(pub_bytes: bytes) -> ec.EllipticCurvePublicKey:
        """Deserializes a DER-encoded public key from bytes."""
        return serialization.load_der_public_key(pub_bytes)

    def derive_shared_fernet_key(self, peer_public_bytes: bytes) -> bytes:
        """
        Performs ECDH key exchange using the instance session.
        For per-connection crypto, use create_session() instead.
        """
        return self._session.derive_shared_fernet_key(peer_public_bytes)

    @staticmethod
    def encrypt_message(fernet_key: bytes, plaintext: str) -> bytes:
        """Encrypts a string plaintext message using the derived Fernet key."""
        f = Fernet(fernet_key)
        return f.encrypt(plaintext.encode('utf-8'))

    @staticmethod
    def decrypt_message(fernet_key: bytes, ciphertext: bytes) -> str:
        """Decrypts a ciphertext message using the derived Fernet key."""
        f = Fernet(fernet_key)
        return f.decrypt(ciphertext).decode('utf-8')

    @staticmethod
    def encrypt_data(fernet_key: bytes, data: bytes) -> bytes:
        """Encrypts raw binary data (e.g. file chunks) using the derived Fernet key."""
        f = Fernet(fernet_key)
        return f.encrypt(data)

    @staticmethod
    def decrypt_data(fernet_key: bytes, ciphertext: bytes) -> bytes:
        """Decrypts raw binary data using the derived Fernet key."""
        f = Fernet(fernet_key)
        return f.decrypt(ciphertext)
