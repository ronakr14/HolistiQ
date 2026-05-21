# holistiq/core/crypto/key_manager.py

import os
from typing import Optional, Tuple

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from config.defaults.defaults import AES_KEY_SIZE, KDF_ITERATIONS, SALT_SIZE


def derive_key_from_password(
    password: str,
    salt: Optional[bytes] = None,
) -> Tuple[bytes, bytes]:
    """
    Derive a key from a password using PBKDF2-HMAC.

    Parameters:
    password (str): The password from which to derive the key.
    salt (Optional[bytes]): The salt to use in the key derivation process.
        If not provided, a random salt will be generated.

    Returns:
    Tuple[bytes, bytes]: A tuple containing the derived key and the salt used.
    """
    if salt is None:
        salt = os.urandom(SALT_SIZE)

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=AES_KEY_SIZE,
        salt=salt,
        iterations=KDF_ITERATIONS,
    )

    key = kdf.derive(password.encode("utf-8"))
    return key, salt


def validate_raw_key(key: bytes) -> None:
    """
    Validate a raw encryption key.

    This function takes a raw encryption key and raises a ValueError if it does not
    meet the size requirement of AES_KEY_SIZE bytes.

    Parameters:
    key (bytes): The raw encryption key to validate.

    Raises:
    ValueError: If the key does not meet the size requirement.
    """
    if len(key) != AES_KEY_SIZE:
        raise ValueError(f"Raw key must be {AES_KEY_SIZE} bytes")
