# string_asserts.py

import difflib
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Pattern, Union

try:
    import Levenshtein

    HAS_LEVENSHTEIN = True
except ImportError:
    HAS_LEVENSHTEIN = False


@dataclass
class NormalizeConfig:
    case_sensitive: bool = True
    whitespace: bool = False
    unicode: bool = False
    punctuation: bool = False

    def apply(self, text: str) -> str:
        """
        Apply the given normalization configuration to the input text.

        :param text: Input string to be normalized
        :return: Normalized string
        """
        if not self.case_sensitive:
            text = text.lower()
        if self.whitespace:
            text = " ".join(text.split())
        if self.unicode:
            text = unicodedata.normalize("NFKC", text)
        if self.punctuation:
            text = re.sub(r"[^\w\s]", "", text)
        return text.strip()


def _diff(a: str, b: str, ctx: int = 3) -> str:
    """
    Generate a unified diff string between two strings a and b, showing
    the differences between the two strings with up to ctx lines of context.

    :param a: First string to compare
    :param b: Second string to compare
    :param ctx: Number of lines of context to show
    :return: Unified diff string showing the differences between the two strings
    """
    diff = difflib.unified_diff(
        a.splitlines(keepends=True),
        b.splitlines(keepends=True),
        fromfile="expected",
        tofile="actual",
        n=ctx,
    )
    return "".join(diff)


class AssertStr:
    """Lightweight, flexible string assertions with optional normalization and fuzzy matching."""

    # --- Helpers ---
    @staticmethod
    def _normalize(a: str, b: str, config: NormalizeConfig):
        """
        Normalize two strings according to the given configuration.

        :param a: First string to normalize
        :param b: Second string to normalize
        :param config: Normalization configuration
        :return: Two normalized strings
        """
        return config.apply(a), config.apply(b)

    @staticmethod
    def _check_type(value: Any, name: str) -> str:
        """
        Check that a given value is a string and raise a TypeError if not.

        :param value: Value to check
        :param name: Name of the value in the context of the check
        :return: The original value if it's a string

        :raises TypeError: If the value is not a string
        """
        if not isinstance(value, str):
            raise TypeError(f"{name} must be a string, got {type(value).__name__}")
        return value

    # --- Core Asserts ---
    @staticmethod
    def equal(a: str, b: str, msg=None, **kwargs):
        """
        Assert that two strings are equal with optional normalization.

        Args:
            a: The first string to compare.
            b: The second string to compare.
            msg: An optional custom error message.
            **kwargs: Keyword arguments to pass to NormalizeConfig.

        Raises:
            AssertionError: If the assertion fails.
        """
        cfg = NormalizeConfig(**kwargs)
        a, b = AssertStr._normalize(a, b, cfg)
        if a != b:
            raise AssertionError(msg or f"Strings differ:\n{_diff(b, a)}")

    @staticmethod
    def contains(text: str, sub: str, msg=None, **kwargs):
        """
        Assert that a given substring is present in a given string with optional normalization.

        Args:
            text: The string to search in.
            sub: The substring to search for.
            msg: An optional custom error message.
            **kwargs: Keyword arguments to pass to NormalizeConfig.

        Raises:
            AssertionError: If the assertion fails.
        """
        cfg = NormalizeConfig(**kwargs)
        text, sub = AssertStr._normalize(text, sub, cfg)
        if sub not in text:
            raise AssertionError(msg or f"'{sub}' not found in '{text}'")

    @staticmethod
    def not_contains(text: str, sub: str, msg=None, **kwargs):
        """
        Assert that a given substring is not present in a given string with optional normalization.

        Args:
            text: The string to search in.
            sub: The substring to search for.
            msg: An optional custom error message.
            **kwargs: Keyword arguments to pass to NormalizeConfig.

        Raises:
            AssertionError: If the assertion fails.
        """
        cfg = NormalizeConfig(**kwargs)
        text, sub = AssertStr._normalize(text, sub, cfg)
        if sub in text:
            raise AssertionError(msg or f"'{sub}' should not be in '{text}'")

    @staticmethod
    def regex(text: str, pattern: Union[str, Pattern[str]], msg=None, flags=0):
        """
        Assert that a given regular expression matches a given string.

        Args:
            text: The string to search in.
            pattern: The regular expression pattern to search for.
            msg: An optional custom error message.
            flags: Optional flags to pass to re.compile.

        Raises:
            AssertionError: If the assertion fails.
        """
        regex = re.compile(pattern, flags) if isinstance(pattern, str) else pattern
        if not regex.search(text):
            raise AssertionError(
                msg or f"Regex '{regex.pattern}' did not match '{text}'"
            )

    @staticmethod
    def similar(a: str, b: str, threshold=0.85, msg=None, **kwargs):
        """
        Assert that two strings are similar with optional normalization.

        Args:
            a: The first string to compare.
            b: The second string to compare.
            threshold: The minimum similarity score required to pass the assertion.
            msg: An optional custom error message.
            **kwargs: Keyword arguments to pass to NormalizeConfig.

        Raises:
            AssertionError: If the assertion fails.
        """

        cfg = NormalizeConfig(**kwargs)
        a, b = AssertStr._normalize(a, b, cfg)
        score = (
            Levenshtein.ratio(a, b)
            if HAS_LEVENSHTEIN
            else difflib.SequenceMatcher(None, a, b).ratio()
        )
        if score < threshold:
            raise AssertionError(
                msg or f"Similarity {score:.3f} < {threshold:.3f}\n{_diff(b, a)}"
            )

    @staticmethod
    def line_equal(a: str, b: str, msg=None, **kwargs):
        """
        Assert that two strings have the same lines with optional normalization.

        Args:
            a: The first string to compare.
            b: The second string to compare.
            msg: An optional custom error message.
            **kwargs: Keyword arguments to pass to NormalizeConfig.

        Raises:
            AssertionError: If the assertion fails.
        """
        cfg = NormalizeConfig(**kwargs)
        a_lines = [cfg.apply(x) for x in a.strip().splitlines()]
        b_lines = [cfg.apply(x) for x in b.strip().splitlines()]
        if a_lines != b_lines:
            raise AssertionError(
                msg
                or f"Line mismatch:\n{_diff('\n'.join(b_lines), '\n'.join(a_lines))}"
            )
