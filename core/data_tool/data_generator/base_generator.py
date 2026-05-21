from abc import ABC, abstractmethod

from faker import Faker

from core.generators.fake_data.locale import FakerLocale


class BaseGenerator(ABC):

    def __init__(self, locale: FakerLocale = FakerLocale.US):
        """
        Initialize BaseGenerator with a locale.

        Args:
            locale (FakerLocale, optional): The locale to use for
                generating fake data. Defaults to FakerLocale.US.
        """
        self.fake = Faker(locale.value)

    @abstractmethod
    def generate(self, **kwargs):
        """
        Generate fake data based on the provided parameters.

        This method is meant to be overridden by subclasses. It should
        generate fake data based on the provided parameters.

        Args:
            **kwargs: Parameters for generating fake data.

        Returns:
            A dictionary containing the generated fake data.
        """
        pass
