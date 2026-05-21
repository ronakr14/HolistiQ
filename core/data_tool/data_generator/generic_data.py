import random
from datetime import datetime, timedelta
from typing import Union

from core.generators.fake_data.base_generator import BaseGenerator


class GenericDataGenerator(BaseGenerator):
    """Generator for generic utility data."""

    def generate_date_range(self, start_date: datetime, end_date: datetime) -> datetime:
        """
        Generate a random date between start_date and end_date (inclusive).

        Args:
            start_date (datetime): The earliest date that can be generated.
            end_date (datetime): The latest date that can be generated.

        Returns:
            datetime: A random date between start_date and end_date (inclusive).
        """
        delta = end_date - start_date
        random_days = random.randint(0, delta.days)
        return start_date + timedelta(days=random_days)

    def generate_date_series(
        self, start_date: datetime, end_date: datetime, count: int
    ) -> list[datetime]:
        """
        Generate a list of dates between start_date and end_date (inclusive) with the specified count.

        Args:
            start_date (datetime): The earliest date that can be generated.
            end_date (datetime): The latest date that can be generated.
            count (int): The number of dates to generate.

        Returns:
            list[datetime]: A list of dates between start_date and end_date (inclusive) with the specified count.
        """
        return [self.generate_date_range(start_date, end_date) for _ in range(count)]

    def generate_id_number(self, length: int = 10, prefix: str = "") -> str:
        """
        Generate a random ID number of the specified length with an optional prefix.

        Args:
            length (int, optional): The length of the ID number. Defaults to 10.
            prefix (str, optional): The prefix to add to the ID number. Defaults to "".

        Returns:
            str: The generated ID number with the prefix if specified.
        """
        number = self.fake.random_number(digits=length, fix_len=True)
        return f"{prefix}{number}" if prefix else str(number)

    def generate_code(self, pattern: str) -> str:
        """
        Generate a random code based on the provided pattern.

        Args:
            pattern (str): The pattern to generate the code from.

        Returns:
            str: The generated code based on the provided pattern.
        """
        return self.fake.bothify(text=pattern).upper()

    def generate(self, **kwargs) -> dict[str, Union[str, datetime]]:
        """
        Generate a dictionary containing a random date, ID number, and code based on the provided parameters.

        Args:
            start_date (datetime, optional): The earliest date that can be generated for the random_date key. Defaults to datetime(2020, 1, 1).
            end_date (datetime, optional): The latest date that can be generated for the random_date key. Defaults to datetime.now().
            id_length (int, optional): The length of the ID number for the random_id key. Defaults to 10.
            code_pattern (str, optional): The pattern to generate the code from for the random_code key. Defaults to "???###".

        Returns:
            dict[str, Union[str, datetime]]: A dictionary containing the generated random date, ID number, and code.
        """
        return {
            "random_date": self.generate_date_range(
                kwargs.get("start_date", datetime(2020, 1, 1)),
                kwargs.get("end_date", datetime.now()),
            ),
            "random_id": self.generate_id_number(kwargs.get("id_length", 10)),
            "random_code": self.generate_code(kwargs.get("code_pattern", "???###")),
        }
