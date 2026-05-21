# holistiq/core/crypto/algorithms.py

import hashlib
import hmac
import os
from hashlib import sha256
from pathlib import Path
from typing import Union

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# from config.defaults.defaults import BASE62_ALPHABET as _BASE62_ALPHABET
# from config.defaults.defaults import NONCE_SIZE

_BASE62_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
NONCE_SIZE = 12


def base62_encode(b: bytes) -> str:
    """
    Encode a byte string as a base62 string.

    Args:
        b: The byte string to encode.

    Returns:
        A base62 string representation of the input byte string.
    """
    v = int.from_bytes(b, "big")
    s = ""
    while v:
        s = _BASE62_ALPHABET[v % 62] + s
        v //= 62
    return s or "0"


def hmac_sha256(key: bytes, message: bytes) -> bytes:
    """
    Compute the HMAC-SHA256 digest of a message using a secret key.

    Args:
        key: The secret key to use for the HMAC.
        message: The message to compute the HMAC for.

    Returns:
        The HMAC-SHA256 digest of the message as a byte string.
    """
    return hmac.new(key, message, sha256).digest()


def hash_file(
    path: Union[str, Path],
    algo: str = "sha256",
    include_path: bool = False,
    chunk_size: int = 1024 * 1024,  # 1MB
) -> str:
    """
    Compute the hash of a file using a specified algorithm.

    Args:
        path: The path to the file to hash.
        algo: The hash algorithm to use. Defaults to "sha256".
        include_path: Whether to include the file path in the hash calculation.
        chunk_size: The size of each chunk to read from the file in bytes.

    Returns:
        The hash of the file as a hexadecimal string.
    """
    path = Path(path).resolve()
    algo = algo.lower()

    if algo not in hashlib.algorithms_available:
        raise ValueError(f"Unsupported hash algorithm: {algo}")

    h = hashlib.new(algo)

    if include_path:
        path = Path(path).expanduser().resolve(strict=True)
        h.update(f"PATH::{str(path)}".encode("utf-8"))

    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)

    return h.hexdigest()


# ---------- Symmetric encryption primitives ----------
def aes_gcm_encrypt(plaintext: bytes, key: bytes) -> bytes:
    """
    Encrypt a plaintext bytes object using AES-GCM encryption.

    Args:
        plaintext: The plaintext bytes object to encrypt.
        key: The encryption key to use for AES-GCM.

    Returns:
        A bytes object containing the encrypted ciphertext, prepended with a
        randomly generated nonce of size NONCE_SIZE.
    """
    aesgcm = AESGCM(key)
    nonce = os.urandom(NONCE_SIZE)
    ciphertext = aesgcm.encrypt(nonce, plaintext, associated_data=None)
    return nonce + ciphertext


def aes_gcm_decrypt(token_with_nonce: bytes, key: bytes) -> bytes:
    """
    Decrypt a ciphertext bytes object using AES-GCM decryption.

    Args:
        token_with_nonce: A bytes object containing the ciphertext, prepended with a
            randomly generated nonce of size NONCE_SIZE.
        key: The decryption key to use for AES-GCM.

    Returns:
        A bytes object containing the decrypted plaintext.
    """
    nonce = token_with_nonce[:NONCE_SIZE]
    ciphertext = token_with_nonce[NONCE_SIZE:]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ciphertext, associated_data=None)
