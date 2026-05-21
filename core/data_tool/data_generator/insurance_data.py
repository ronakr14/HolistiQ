import random

from core.generators.fake_data.base_generator import BaseGenerator


class InsuranceDataGenerator(BaseGenerator):
    """Generator for insurance information."""

    PAYER_CHANNELS = [
        "Medicare-A",
        "Medicare-B",
        "Medicare-C",
        "Medicare-D",
        "Commercial",
        "Medicaid",
        "Tricare",
        "VHA",
        "CHIP",
        "IHS",
        "MCO",
        "TPA",
    ]
    MCO_SUFFIXES = [
        "Health",
        "Health Partners",
        "Health Inc.",
        "Insurance Partners",
        "Corporation",
        "Health Plans",
        "Insurance Plans",
        "Insurance Inc.",
    ]
    PLAN_TYPES = ["State", "Employer", "Nation", "Commercial", "Government"]
    COVERAGE_TYPES = ["M", "P", "A", "C", "D"]

    def generate_payer_info(self) -> dict[str, str]:
        """Generate payer information."""
        return {
            "benefit_tier": f"{random.randint(1, 9)}-Tier",
            "mco_id": f"{random.randint(101, 999)}",
            "mco_name": self.fake.company() + " " + random.choice(self.MCO_SUFFIXES),
            "controller_id": f"{random.randint(1001, 9999)}",
            "formulary_id": f"{random.randint(100001, 999999)}",
            "bin_number": f"{random.randint(111111, 999999)}",
            "channel": random.choice(self.PAYER_CHANNELS),
            "pcn": self.fake.bothify(text="##########").upper(),
            "group_id": self.fake.bothify(text="???-#####").upper(),
            "plan_type": random.choice(self.PLAN_TYPES),
            "coverage_type": random.choice(self.COVERAGE_TYPES),
        }

    def generate_member_info(self) -> dict[str, str]:
        """Generate member-specific insurance information."""
        return {
            "member_id": self.fake.bothify(text="???########"),
            "policy_number": self.fake.bothify(text="#########"),
            "effective_date": self.fake.date_between(
                start_date="-2y", end_date="today"
            ).strftime("%Y-%m-%d"),
            "termination_date": self.fake.date_between(
                start_date="today", end_date="+2y"
            ).strftime("%Y-%m-%d"),
            "copay_amount": f"${random.choice([10, 15, 20, 25, 30])}.00",
            "deductible_amount": f"${random.choice([500, 1000, 1500, 2000, 2500])}.00",
        }

    def generate(self, **kwargs) -> dict[str, str]:
        """Generate complete insurance profile."""
        profile = {}
        profile.update(self.generate_payer_info())
        profile.update(self.generate_member_info())
        return profile
