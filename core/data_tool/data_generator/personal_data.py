import random
from datetime import datetime
from typing import Union

from core.generators.fake_data.base_generator import BaseGenerator
from core.generators.fake_data.data_info import HeightRange, PhoneConfig, WeightRange
from core.generators.fake_data.locale import FakerLocale


class PersonalDataGenerator(BaseGenerator):
    """Generator for personal information."""

    GENDER_OPTIONS = ["M", "F", "Other", "Not Specified"]
    RELATION_OPTIONS = [
        "Nurse",
        "Spouse",
        "Child",
        "Parent",
        "Sibling",
        "Guardian",
        "Other",
    ]

    def __init__(
        self,
        locale: FakerLocale = FakerLocale.US,
        weight_range: WeightRange = None,
        height_range: HeightRange = None,
        phone_config: PhoneConfig = None,
    ):
        """
        Initialize PersonalDataGenerator with a locale, weight range, height range, and phone config.

        Args:
            locale (FakerLocale, optional): The locale to use for generating fake data. Defaults to FakerLocale.US.
            weight_range (WeightRange, optional): The weight range to use for generating fake data. Defaults to None.
            height_range (HeightRange, optional): The height range to use for generating fake data. Defaults to None.
            phone_config (PhoneConfig, optional): The phone config to use for generating fake data. Defaults to None.
        """
        super().__init__(locale)
        self.weight_range = weight_range or WeightRange()
        self.height_range = height_range or HeightRange()
        self.phone_config = phone_config or PhoneConfig()

    def generate_name(self, include_middle: bool = False) -> dict[str, str]:
        """
        Generate complete name information.

        Args:
            include_middle (bool, optional): Whether to include middle name. Defaults to False.

        Returns:
            dict[str, str]: A dictionary containing complete name information.
        """
        result = {
            "first_name": self.fake.first_name(),
            "last_name": self.fake.last_name(),
        }
        if include_middle:
            result["middle_name"] = self.fake.first_name()
        return result

    def generate_demographics(self) -> dict[str, Union[str, datetime]]:
        """
        Generate demographic information.

        Returns:
            dict[str, Union[str, datetime]]: A dictionary containing demographic information.
        """
        return {
            "gender": self.fake.random_element(self.GENDER_OPTIONS),
            "date_of_birth": self.fake.date_of_birth(minimum_age=5, maximum_age=90),
            "ssn": self.fake.ssn(),
        }

    def generate_address(self) -> dict[str, str]:
        """Generate address information."""
        full_address = self.fake.address()
        return {
            "street_address": self.fake.street_address(),
            "city": self.fake.city(),
            "state": self.fake.state_abbr(),
            "zip_code": self.fake.zipcode(),
            "country": self.fake.country_code(),
            "full_address": full_address,
        }

    def generate_contact_info(self) -> dict[str, str]:
        """Generate contact information."""
        phone = self._generate_phone_number()
        return {
            "phone": phone,
            "fax": self._generate_phone_number(),
            "email": self.fake.email(),
            "mobile": self._generate_phone_number(),
        }

    def generate_physical_attributes(self) -> dict[str, Union[float, str]]:
        """Generate physical attributes."""
        return {
            "weight": round(
                random.uniform(
                    self.weight_range.min_weight, self.weight_range.max_weight
                ),
                2,
            ),
            "weight_unit": self.weight_range.unit,
            "height": round(
                random.uniform(
                    self.height_range.min_height, self.height_range.max_height
                ),
                2,
            ),
            "height_unit": self.height_range.unit,
        }

    def generate_relation(self) -> str:
        """Generate relationship type."""
        return random.choice(self.RELATION_OPTIONS)

    def _generate_phone_number(self) -> str:
        """Generate formatted phone number."""
        area = random.randint(
            self.phone_config.area_code_min, self.phone_config.area_code_max
        )
        exchange = random.randint(
            self.phone_config.exchange_code_min, self.phone_config.exchange_code_max
        )
        subscriber = random.randint(
            self.phone_config.subscriber_min, self.phone_config.subscriber_max
        )

        if self.phone_config.format_with_dashes:
            return f"{area}-{exchange}-{subscriber}"
        return f"{area}{exchange}{subscriber}"

    def generate(self, **kwargs) -> dict[str, Union[str, datetime, float]]:
        """Generate complete personal profile."""
        profile = {}
        profile.update(self.generate_demographics())
        profile.update(self.generate_name(kwargs.get("include_middle", False)))
        profile.update(self.generate_address())
        profile.update(self.generate_contact_info())
        profile.update(self.generate_physical_attributes())
        profile["relation"] = self.generate_relation()
        return profile
