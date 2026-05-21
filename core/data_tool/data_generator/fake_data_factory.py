from core.generators.fake_data.base_generator import BaseGenerator
from core.generators.fake_data.data_file import DataFileManager
from core.generators.fake_data.generic_data import GenericDataGenerator
from core.generators.fake_data.insurance_data import InsuranceDataGenerator
from core.generators.fake_data.locale import FakerLocale
from core.generators.fake_data.medical_data import MedicalDataGenerator
from core.generators.fake_data.personal_data import PersonalDataGenerator


class FakeDataFactory:
    """Factory class for creating and managing data generators."""

    def __init__(
        self, locale: FakerLocale = FakerLocale.US, data_directory: str = "static"
    ):
        self.locale = locale
        self.file_manager = DataFileManager(data_directory)
        self._generators: dict[str, BaseGenerator] = {}

    def get_personal_generator(self, **config) -> PersonalDataGenerator:
        key = "personal"
        if key not in self._generators:
            self._generators[key] = PersonalDataGenerator(self.locale, **config)
        return self._generators[key]

    def get_medical_generator(self) -> MedicalDataGenerator:
        key = "medical"
        if key not in self._generators:
            self._generators[key] = MedicalDataGenerator(self.locale)
        return self._generators[key]

    def get_insurance_generator(self) -> InsuranceDataGenerator:
        key = "insurance"
        if key not in self._generators:
            self._generators[key] = InsuranceDataGenerator(self.locale)
        return self._generators[key]

    def get_generic_generator(self) -> GenericDataGenerator:
        key = "generic"
        if key not in self._generators:
            self._generators[key] = GenericDataGenerator(self.locale)
        return self._generators[key]

    # def generate_complete_profile(
    #     self, **kwargs
    # ) -> dict[str, Union[str, datetime, float, int]]:
    #     profile = {}

    #     if kwargs.get("include_personal", True):
    #         profile.update(self.get_personal_generator().generate(**kwargs))

    #     if kwargs.get("include_medical", True):
    #         profile.update(self.get_medical_generator().generate(**kwargs))

    #     if kwargs.get("include_insurance", True):
    #         profile.update(self.get_insurance_generator().generate(**kwargs))

    #     if kwargs.get("include_generic", True):
    #         profile.update(self.get_generic_generator().generate(**kwargs))

    #     return profile

    # def generate_batch_profiles(self, count: int, **kwargs) -> list[dict]:
    #     return [self.generate_complete_profile(**kwargs) for _ in range(count)]
