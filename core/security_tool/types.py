from enum import Enum
from typing import Set


class MaskingMode(str, Enum):
    STRICT = "strict"  # mask everything sensitive, aggressively
    LENIENT = "lenient"  # mask known secrets only


DEFAULT_SENSITIVE_KEYS: Set[str] = {
    "password",
    "passwd",
    "pwd",
    "pass",
    "secret",
    "token",
    "key",
    "api_key",
    "auth",
    "credential",
    "access_token",
    "private_key",
}
