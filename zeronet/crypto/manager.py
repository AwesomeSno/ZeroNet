import base64
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.fernet import Fernet

class CryptoManager:
    """
    Handles ECDH Key Exchange and E2E Fernet encryption/decryption.
    """
    def __init__(self):
        # Generate our ephemeral ECDH private key
        self.private_key = ec.generate_private_key(ec.SECP256R1())
        self.public_key = self.private_key.public_key()

    def get_public_bytes(self) -> bytes:
        """
        Serializes our public key to DER format (SubjectPublicKeyInfo) for sending over network.
        """
        return self.public_key.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )

    @staticmethod
    def load_public_key(pub_bytes: bytes) -> ec.EllipticCurvePublicKey:
        """
        Deserializes a DER-encoded public key from bytes.
        """
        return serialization.load_der_public_key(pub_bytes)

    def derive_shared_fernet_key(self, peer_public_bytes: bytes) -> bytes:
        """
        Performs Diffie-Hellman key exchange, derives a 32-byte shared key using HKDF,
        and returns a url-safe base64 encoded Fernet key.
        """
        peer_pub_key = self.load_public_key(peer_public_bytes)
        shared_secret = self.private_key.exchange(ec.ECDH(), peer_pub_key)
        
        # Derive key using HKDF
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=None,
            info=b"zeronet-e2ee-key-derivation",
        )
        derived_key = hkdf.derive(shared_secret)
        
        # Base64 encode for Fernet
        return base64.urlsafe_b64encode(derived_key)

    @staticmethod
    def encrypt_message(fernet_key: bytes, plaintext: str) -> bytes:
        """
        Encrypts a string plaintext message using the derived Fernet key.
        """
        f = Fernet(fernet_key)
        return f.encrypt(plaintext.encode('utf-8'))

    @staticmethod
    def decrypt_message(fernet_key: bytes, ciphertext: bytes) -> str:
        """
        Decrypts a ciphertext message using the derived Fernet key.
        """
        f = Fernet(fernet_key)
        return f.decrypt(ciphertext).decode('utf-8')

    @staticmethod
    def encrypt_data(fernet_key: bytes, data: bytes) -> bytes:
        """
        Encrypts raw binary data (e.g. file chunks) using the derived Fernet key.
        """
        f = Fernet(fernet_key)
        return f.encrypt(data)

    @staticmethod
    def decrypt_data(fernet_key: bytes, ciphertext: bytes) -> bytes:
        """
        Decrypts raw binary data using the derived Fernet key.
        """
        f = Fernet(fernet_key)
        return f.decrypt(ciphertext)
