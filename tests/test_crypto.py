import pytest
from zeronet.crypto.manager import CryptoManager

def test_crypto_key_generation():
    crypto = CryptoManager()
    assert crypto._session is not None
    assert crypto._session.private_key is not None
    assert crypto._session.public_key is not None
    
    pub_bytes = crypto.get_public_bytes()
    assert len(pub_bytes) > 0
    
    loaded_key = CryptoManager.load_public_key(pub_bytes)
    assert loaded_key is not None

def test_key_exchange_and_encryption():
    alice = CryptoManager()
    bob = CryptoManager()
    
    alice_pub_bytes = alice.get_public_bytes()
    bob_pub_bytes = bob.get_public_bytes()
    
    alice_derived = alice.derive_shared_fernet_key(bob_pub_bytes)
    bob_derived = bob.derive_shared_fernet_key(alice_pub_bytes)
    
    # Assert they both derived the exact same symmetric key
    assert alice_derived == bob_derived
    
    # Test encryption & decryption
    plaintext = "Hello, this is a secure end-to-end encrypted message!"
    ciphertext = CryptoManager.encrypt_message(alice_derived, plaintext)
    
    decrypted = CryptoManager.decrypt_message(bob_derived, ciphertext)
    assert decrypted == plaintext

def test_data_encryption():
    alice = CryptoManager()
    bob = CryptoManager()
    
    alice_pub_bytes = alice.get_public_bytes()
    bob_pub_bytes = bob.get_public_bytes()
    
    shared_key = alice.derive_shared_fernet_key(bob_pub_bytes)
    
    raw_data = b"\x00\x01\x02\x03\x04\xff\xee\xdd\xcc"
    ciphertext = CryptoManager.encrypt_data(shared_key, raw_data)
    
    decrypted = CryptoManager.decrypt_data(shared_key, ciphertext)
    assert decrypted == raw_data
