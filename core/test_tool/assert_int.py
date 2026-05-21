import math
from enum import Enum
from typing import Optional, Union

Numeric = Union[int, float]


class ComparisonOperator(Enum):
    EQ = "=="
    NE = "!="
    GT = ">"
    LT = "<"
    GTE = ">="
    LTE = "<="


class AssertNum:
    """Simplified numeric assertions with tolerance support."""

    # --- Utility validation methods ---
    @staticmethod
    def _validate_numeric(value: Numeric, name: str):
        """
        Validates that a given value is numeric (int or float) and not NaN or infinite.

        Args:
            value: The value to validate.
            name: The name of the value in the context of the validation.

        Raises:
            ValueError: If the value is not numeric or is NaN or infinite.
        """
        if not isinstance(value, (int, float)):
            raise ValueError(
                f"{name} must be numeric, got {type(value).__name__}: {value}"
            )
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            raise ValueError(f"{name} cannot be NaN or infinite")

    @staticmethod
    def _validate_tolerance(tol: Optional[float]):
        """
        Validates a tolerance value.

        Args:
            tol: The tolerance value to validate.

        Raises:
            ValueError: If the tolerance value is invalid.
        """
        if tol is None:
            return
        if (
            not isinstance(tol, (int, float))
            or tol < 0
            or math.isinf(tol)
            or math.isnan(tol)
        ):
            raise ValueError(f"Invalid tolerance: {tol}")

    @staticmethod
    def _fail(
        msg: str,
        actual: Numeric,
        expected: Numeric,
        op: str,
        tol: Optional[float] = None,
    ):
        """
        Raise an AssertionError with a formatted message.

        Args:
            msg: The assertion message.
            actual: The actual value.
            expected: The expected value.
            op: The operator used in the assertion.
            tol: The tolerance value used in the assertion.

        Raises:
            AssertionError: Always raised.
        """
        tol_text = f" (±{tol})" if tol else ""
        raise AssertionError(f"{msg}: expected {actual} {op} {expected}{tol_text}")

    # --- Core execution ---
    @classmethod
    def _assert(
        cls,
        actual: Numeric,
        expected: Numeric,
        op: ComparisonOperator,
        message: Optional[str] = None,
        tol: Optional[float] = None,
    ):
        """
        Perform a numeric assertion with tolerance support.

        Args:
            actual: The actual numeric value.
            expected: The expected numeric value.
            op: The comparison operator to use.
            message: An optional custom error message.
            tol: An optional tolerance value.

        Raises:
            AssertionError: If the assertion fails.
        """
        cls._validate_numeric(actual, "Actual")
        cls._validate_numeric(expected, "Expected")
        cls._validate_tolerance(tol)

        ok = False
        if op == ComparisonOperator.EQ:
            ok = math.isclose(actual, expected, abs_tol=tol or 0.0)
        elif op == ComparisonOperator.NE:
            ok = not math.isclose(actual, expected, abs_tol=tol or 0.0)
        elif op == ComparisonOperator.GT:
            ok = actual > expected
        elif op == ComparisonOperator.LT:
            ok = actual < expected
        elif op == ComparisonOperator.GTE:
            ok = actual >= expected
        elif op == ComparisonOperator.LTE:
            ok = actual <= expected

        if not ok:
            msg = message or f"Assertion failed: {actual} {op.value} {expected}"
            cls._fail(msg, actual, expected, op.value, tol)

    # --- Assertion methods ---
    @classmethod
    def equal(cls, a: Numeric, b: Numeric, message=None, tol: Optional[float] = None):
        """
        Assert that two numeric values are equal with optional tolerance.

        Args:
            a: The first numeric value.
            b: The second numeric value.
            message: An optional custom error message.
            tol: An optional tolerance value.

        Raises:
            AssertionError: If the assertion fails.
        """
        cls._assert(a, b, ComparisonOperator.EQ, message, tol)

    @classmethod
    def not_equal(
        cls, a: Numeric, b: Numeric, message=None, tol: Optional[float] = None
    ):
        """
        Assert that two numeric values are not equal with optional tolerance.

        Args:
            a: The first numeric value.
            b: The second numeric value.
            message: An optional custom error message.
            tol: An optional tolerance value.

        Raises:
            AssertionError: If the assertion fails.
        """
        cls._assert(a, b, ComparisonOperator.NE, message, tol)

    @classmethod
    def greater(cls, a: Numeric, b: Numeric, message=None):
        """
        Assert that the first numeric value is greater than the second numeric value.

        Args:
            a: The first numeric value.
            b: The second numeric value.
            message: An optional custom error message.

        Raises:
            AssertionError: If the assertion fails.
        """
        cls._assert(a, b, ComparisonOperator.GT, message)

    @classmethod
    def less(cls, a: Numeric, b: Numeric, message=None):
        """
        Assert that the first numeric value is less than the second numeric value.

        Args:
            a: The first numeric value.
            b: The second numeric value.
            message: An optional custom error message.

        Raises:
            AssertionError: If the assertion fails.
        """
        cls._assert(a, b, ComparisonOperator.LT, message)

    @classmethod
    def gte(cls, a: Numeric, b: Numeric, message=None):
        """
        Assert that the first numeric value is greater than or equal to the second numeric value.

        Args:
            a: The first numeric value.
            b: The second numeric value.
            message: An optional custom error message.

        Raises:
            AssertionError: If the assertion fails.
        """
        cls._assert(a, b, ComparisonOperator.GTE, message)

    @classmethod
    def lte(cls, a: Numeric, b: Numeric, message=None):
        """
        Assert that the first numeric value is less than or equal to the second numeric value.

        Args:
            a: The first numeric value.
            b: The second numeric value.
            message: An optional custom error message.

        Raises:
            AssertionError: If the assertion fails.
        """
        cls._assert(a, b, ComparisonOperator.LTE, message)

    # --- Convenience ---
    @classmethod
    def in_range(
        cls,
        value: Numeric,
        low: Numeric,
        high: Numeric,
        inclusive: bool = True,
        message: Optional[str] = None,
    ):
        """
        Assert that a given numeric value is within a specified range.

        Args:
            value: The numeric value to check.
            low: The lower bound of the range.
            high: The upper bound of the range.
            inclusive: Whether the range is inclusive or exclusive.
            message: An optional custom error message.

        Raises:
            AssertionError: If the value is not within the specified range.
        """
        cls._validate_numeric(value, "Value")
        cls._validate_numeric(low, "Min")
        cls._validate_numeric(high, "Max")

        if low > high:
            raise ValueError(f"Invalid range: min ({low}) > max ({high})")

        ok = (low <= value <= high) if inclusive else (low < value < high)
        if not ok:
            msg = message or f"Value {value} not in range [{low}, {high}]"
            raise AssertionError(msg)

    @staticmethod
    def fail(message: str):
        """
        Raise an AssertionError with a custom error message.

        Args:
            message: Custom error message to raise with the AssertionError.

        Raises:
            AssertionError: Always raised with the provided error message.
        """
        raise AssertionError(message or "Assertion failed")
