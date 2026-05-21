import re
from typing import Optional
from urllib.parse import urlparse, urlunparse


class MaskingRule:
    def apply(self, raw: str) -> Optional[str]:
        """
        Applies the masking rule to the given input string.

        Args:
            raw: str
                The input string to apply the masking rule to

        Returns:
            Optional[str]
                The masked string if the rule matches, otherwise None

        Raises:
            NotImplementedError
                If the subclass does not implement this method
        """
        raise NotImplementedError


class UrlPasswordRule(MaskingRule):
    def __init__(self, mask: str):
        """
        Initializes a UrlPasswordRule instance.

        Args:
            mask (str): The string to use for masking passwords in URLs

        Returns:
            None
        """
        self._mask = mask

    def apply(self, raw: str) -> Optional[str]:
        """
        Applies the UrlPasswordRule to the given input string.

        If the input string does not contain a password in the URL (i.e., no
        password is specified after the username in the URL), this method
        returns None.

        Otherwise, the method returns a new URL string with the password
        replaced with the masking string.

        Args:
            raw (str): The input string to apply the UrlPasswordRule to

        Returns:
            Optional[str]: The masked URL string if the rule matches, otherwise None
        """
        parsed = urlparse(raw)
        if not parsed.password:
            return None

        netloc = f"{parsed.username}:{self._mask}@{parsed.hostname}"
        if parsed.port:
            netloc += f":{parsed.port}"

        return urlunparse(
            (
                parsed.scheme,
                netloc,
                parsed.path,
                parsed.params,
                parsed.query,
                parsed.fragment,
            )
        )


class KeyValueRule(MaskingRule):
    def __init__(self, sensitive_keys: set[str], mask: str):
        """
        Initializes a KeyValueRule instance.

        Args:
            sensitive_keys (set[str]): Set of key names that are considered sensitive and should be masked
            mask (str): The string to use for masking sensitive values

        Returns:
            None
        """
        self._keys = sensitive_keys
        self._mask = mask

    def apply(self, raw: str) -> Optional[str]:
        """
        Applies the KeyValueRule to the given input string.

        If the input string does not contain an '=' character, this method
        returns None.

        Otherwise, the method splits the input string into key-value pairs
        using the first '=' character as the separator. It then iterates over
        each key-value pair and checks if the key is in the set of sensitive
        keys. If it is, the value is replaced with the masking string.

        Finally, the method joins the key-value pairs back together using the
        separator character and returns the masked string if any of the
        values were replaced, otherwise None.

        Args:
            raw (str): The input string to apply the KeyValueRule to

        Returns:
            Optional[str]: The masked string if the rule matches, otherwise None
        """

        if "=" not in raw:
            return None

        sep = ";" if ";" in raw else "&"
        parts = raw.split(sep)
        masked = []

        hit = False
        for part in parts:
            if "=" not in part:
                masked.append(part)
                continue

            key, value = part.split("=", 1)
            if key.strip().lower() in self._keys:
                masked.append(f"{key}={self._mask}")
                hit = True
            else:
                masked.append(part)

        return sep.join(masked) if hit else None


class GenericRegexRule(MaskingRule):
    _PATTERNS = [
        r"(password=)[^;&\s]+",
        r"(pwd=)[^;&\s]+",
        r"(pass=)[^;&\s]+",
        r"(:)([^@:/]+)(@)",
    ]

    def __init__(self, mask: str):
        """
        Initializes a GenericRegexRule instance.

        Args:
            mask (str): The string to use for masking sensitive values

        Returns:
            None
        """
        self._mask = mask

    def apply(self, raw: str) -> Optional[str]:
        """
        Applies the GenericRegexRule to the given input string.

        The method uses a list of predefined regex patterns to search for
        sensitive values in the input string. If a match is found, the
        value is replaced with the masking string.

        Args:
            raw (str): The input string to apply the GenericRegexRule to

        Returns:
            Optional[str]: The masked string if the rule matches, otherwise None
        """
        masked = raw
        for pattern in self._PATTERNS:
            masked = re.sub(
                pattern,
                rf"\1{self._mask}\3" if "@" in pattern else rf"\1{self._mask}",
                masked,
                flags=re.IGNORECASE,
            )
        return masked if masked != raw else None
