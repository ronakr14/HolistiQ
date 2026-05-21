import random
from typing import Union

from core.generators.fake_data.base_generator import BaseGenerator


class MedicalDataGenerator(BaseGenerator):
    """Generator for medical information."""

    HIPAA_STATUS_OPTIONS = ["Y", "N", "U"]
    HIPAA_MODE_OPTIONS = ["paper", "electronic", "verbal"]
    UNIT_MEASURES = ["tablet", "ml", "mg", "syringe", "capsule", "patch", "inhaler"]
    SPECIALTIES = [
        "Anesthesiology",
        "Cardiology",
        "Dermatology",
        "Emergency Medicine",
        "Family Medicine",
        "Gastroenterology",
        "Internal Medicine",
        "Neurology",
        "Obstetrics and Gynecology",
        "Oncology",
        "Ophthalmology",
        "Orthopedic Surgery",
        "Pediatrics",
        "Psychiatry",
        "Radiology",
        "Surgery",
        "Urology",
        "Pathology",
        "Physical Medicine",
        "Plastic Surgery",
        "Pulmonology",
        "Rheumatology",
    ]
    COMMON_MEDICATIONS = [
        "Aspirin",
        "Tylenol",
        "Ibuprofen",
        "Amoxicillin",
        "Penicillin",
        "Ciprofloxacin",
        "Metformin",
        "Lisinopril",
        "Simvastatin",
        "Omeprazole",
        "Atorvastatin",
        "Metoprolol",
        "Hydrochlorothiazide",
        "Gabapentin",
        "Sertraline",
    ]

    def generate_provider_info(self) -> dict[str, str]:
        """Generate medical provider information."""
        return {
            "npi": self.fake.numerify("##########"),
            "dea": self._generate_dea_number(),
            "hin": self.fake.bothify(text="?????????").upper(),
            "sln": self.fake.bothify(text="??#####").upper(),
            "specialty": random.choice(self.SPECIALTIES),
            "facility_name": self.fake.company() + " Medical Center",
        }

    def generate_prescription_info(self) -> dict[str, Union[str, int, float]]:
        """Generate prescription information."""
        return {
            "product_name": random.choice(self.COMMON_MEDICATIONS),
            "ndc": self._generate_ndc_number(),
            "quantity": random.choice([10, 20, 30, 60, 90]),
            "days_supply": random.choice([5, 10, 15, 30, 60, 90]),
            "unit_measure": random.choice(self.UNIT_MEASURES),
            "dose": self._generate_dose(),
            "strength": self._generate_strength(),
            "pharmacy_name": self.fake.company() + " Pharmacy",
            "ncpdp": self.fake.random_number(digits=7, fix_len=True),
        }

    def generate_hipaa_info(self) -> dict[str, str]:
        """Generate HIPAA related information."""
        return {
            "hipaa_status": random.choice(self.HIPAA_STATUS_OPTIONS),
            "transplant_status": random.choice(self.HIPAA_STATUS_OPTIONS),
            "hipaa_mode": random.choice(self.HIPAA_MODE_OPTIONS),
        }

    def _generate_dea_number(self) -> str:
        """Generate valid-format DEA number."""
        first_letter = random.choice("ABFG")
        second_letter = self.fake.random_uppercase_letter()
        digits = self.fake.numerify("#######")
        return f"{first_letter}{second_letter}{digits}"

    def _generate_ndc_number(self) -> str:
        """Generate NDC number in standard format."""
        part1 = self.fake.random_int(min=10000, max=99999)
        part2 = self.fake.random_int(min=1000, max=9999)
        part3 = self.fake.random_int(min=10, max=99)
        return f"{part1}-{part2}-{part3}"

    def _generate_dose(self) -> str:
        """Generate medication dose."""
        dose_num = random.randint(1, 5)
        unit = random.choice(["tablet", "ml"])
        if unit == "ml":
            return f"{random.choice([5, 10, 15, 20])} ml"
        return str(dose_num)

    def _generate_strength(self) -> str:
        """Generate medication strength."""
        strength = random.choice([5, 10, 15, 25, 50])
        unit = random.choice(["mg/dose", "mg/ml", "mcg", "units"])
        return f"{strength} {unit}"

    def generate(self, **kwargs) -> dict[str, Union[str, int, float]]:
        """Generate complete medical profile."""
        profile = {}
        profile.update(self.generate_provider_info())
        profile.update(self.generate_prescription_info())
        profile.update(self.generate_hipaa_info())
        return profile
