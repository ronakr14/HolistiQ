from typing import Iterable

from core.security.redaction.rules import MaskingRule


class MaskingEngine:
    def __init__(self, rules: Iterable[MaskingRule]):
        """
        Initializes a MaskingEngine instance.

        Args:
            rules: Iterable[MaskingRule]
                An iterable of MaskingRule instances to use for masking.

        Returns:
            None
        """
        self._rules = list(rules)

    def mask(self, raw: str) -> str:
        """
        Applies all registered masking rules to the given input string.

        Args:
            raw: str
                The input string to apply masking rules to

        Returns:
            str
                The masked string if any rule matches, otherwise the original string

        Notes:
            1. If the input string is empty, an empty string is immediately returned.
            2. The rules are applied in the order they were registered.
            3. The first rule to match will have its result returned.
        """
        if not raw:
            return ""

        for rule in self._rules:
            result = rule.apply(raw)
            if result:
                return result

        return raw
