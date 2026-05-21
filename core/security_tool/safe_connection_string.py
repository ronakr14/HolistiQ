from functools import lru_cache
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlparse

from core.observe.logger_factory.logging_util import get_logger
from core.security.redaction.engine import MaskingEngine
from core.security.redaction.rules import (
    GenericRegexRule,
    KeyValueRule,
    UrlPasswordRule,
)
from core.security.redaction.types import DEFAULT_SENSITIVE_KEYS


class SafeConnectionString:
    logger = get_logger("SafeConnectionString", component="Security")

    def __init__(
        self,
        raw: str,
        mask_char: str = "*",
        mask_length: int = 4,
    ):
        """
        Initializes a SafeConnectionString object.

        Args:
            raw (str): The raw connection string
            mask_char (str, optional): The character to use for masking. Defaults to "*".
            mask_length (int, optional): The length of the masking string. Defaults to 4.
        """
        self._raw = raw.strip()
        self._mask = mask_char * mask_length
        self._parsed = self._parse()

        self._engine = MaskingEngine(
            rules=[
                UrlPasswordRule(self._mask),
                KeyValueRule(DEFAULT_SENSITIVE_KEYS, self._mask),
                GenericRegexRule(self._mask),
            ]
        )

    def _parse(self):
        try:
            return urlparse(self._raw)
        except Exception as e:
            self.logger.warning(f"Failed to parse connection string: {e}")
            return None

    def __str__(self) -> str:
        return self.masked

    def __repr__(self) -> str:
        return f"SafeConnectionString('{self.masked}')"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, SafeConnectionString) and self._raw == other._raw

    def __hash__(self) -> int:
        return hash(self._raw)

    @property
    def raw(self) -> str:
        return self._raw

    @property
    @lru_cache(maxsize=1)
    def masked(self) -> str:
        return self._engine.mask(self._raw)

    @property
    def database_type(self) -> Optional[str]:
        return self._parsed.scheme if self._parsed else None

    @property
    def host(self) -> Optional[str]:
        return self._parsed.hostname if self._parsed else None

    @property
    def port(self) -> Optional[int]:
        return self._parsed.port if self._parsed else None

    @property
    def database(self) -> Optional[str]:
        return (
            self._parsed.path.lstrip("/")
            if self._parsed and self._parsed.path
            else None
        )

    @property
    def username(self) -> Optional[str]:
        return self._parsed.username if self._parsed else None

    def looks_valid(self) -> bool:
        return bool(self._raw) and (
            (self._parsed and self._parsed.scheme) or "=" in self._raw
        )

    def get_safe_info(self) -> Dict[str, Any]:
        info = {
            "database_type": self.database_type,
            "host": self.host,
            "port": self.port,
            "database": self.database,
            "username": self.username,
            "masked": self.masked,
        }

        if self._parsed and self._parsed.query:
            query = parse_qs(self._parsed.query)
            info["query_params"] = {
                k: v
                for k, v in query.items()
                if k.lower() not in DEFAULT_SENSITIVE_KEYS
            }

        return info
