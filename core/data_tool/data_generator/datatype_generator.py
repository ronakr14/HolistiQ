import uuid
from datetime import datetime, timedelta
from typing import Any

import numpy as np
from performance_data.beta_generator import BetaGenerator
from performance_data.binomial_generator import BinomialGenerator
from performance_data.distribution_generator import DistributionGenerator
from performance_data.exponential_generator import ExponentialGenerator
from performance_data.gamma_generator import GammaGenerator
from performance_data.lognormal_generator import LognormalGenerator
from performance_data.normal_generator import NormalGenerator
from performance_data.pareto_generator import ParetoGenerator
from performance_data.poisson_generator import PoissonGenerator
from performance_data.uniform_generator import UniformGenerator
from performance_data.weibull_generator import WeibullGenerator


class DataTypeGenerator:
    """Handles generation of specific data types with various distributions."""

    ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890@#$%^&*()_+-`~=;:',<.>?*"

    def __init__(self, distribution: str):
        self.distribution = distribution
        self.generators = self._create_generators()

    def _create_generators(self) -> dict[str, DistributionGenerator]:
        """Create distribution generator instances."""
        return {
            "uniform": UniformGenerator(),
            "normal": NormalGenerator(),
            "exponential": ExponentialGenerator(),
            "poisson": PoissonGenerator(),
            "binomial": BinomialGenerator(),
            "gamma": GammaGenerator(),
            "beta": BetaGenerator(),
            "pareto": ParetoGenerator(),
            "weibull": WeibullGenerator(),
            "lognormal": LognormalGenerator(),
        }

    def generate_int2(self, rows: int) -> np.ndarray:
        """Generate int2 data with specified distribution."""
        generator = self.generators.get(self.distribution, self.generators["uniform"])
        data = generator.generate(rows, low=0, high=100)
        return data.astype(int)

    def generate_int4(self, rows: int) -> np.ndarray:
        """Generate int4 data with specified distribution."""
        generator = self.generators.get(self.distribution, self.generators["uniform"])
        params = {
            "low": 0,
            "high": 100,
            "loc": 50,
            "scale": 10,
            "n": 10,
            "p": 0.5,
            "shape": 2,
        }
        data = generator.generate(rows, **params)
        return data.astype(np.int32)

    def generate_int8(self, rows: int) -> np.ndarray:
        """Generate int8 data with specified distribution."""
        generator = self.generators.get(self.distribution, self.generators["uniform"])
        data = generator.generate(rows, low=-128, high=128)
        return np.clip(data, -128, 127).astype(np.int8)

    def generate_float4(self, rows: int) -> np.ndarray:
        """Generate float4 data with specified distribution."""
        generator = self.generators.get(self.distribution, self.generators["uniform"])
        data = generator.generate(rows, low=0, high=100000)
        return data.astype(np.float32)

    def generate_float8(self, rows: int) -> np.ndarray:
        """Generate float8 data with specified distribution."""
        generator = self.generators.get(self.distribution, self.generators["uniform"])
        data = generator.generate(rows, low=0, high=100000)
        return data.astype(np.float64)

    def generate_varchar(self, rows: int, length: int) -> list[str]:
        """Generate varchar data."""
        return [self._generate_random_string(length) for _ in range(rows)]

    def generate_char(self, rows: int) -> np.ndarray:
        """Generate single character data."""
        return np.random.choice(list(self.ALPHABET), rows)

    def generate_uuid(self, rows: int) -> list[str]:
        """Generate UUID data."""
        return [str(uuid.uuid4()) for _ in range(rows)]

    def generate_date(self, rows: int) -> list[str]:
        """Generate date data with specified distribution."""
        start_date = datetime(2000, 1, 1)
        end_date = datetime(2025, 12, 31)
        return self._generate_temporal_data(
            rows, start_date, end_date, "%Y-%m-%d", "days"
        )

    def generate_datetime(self, rows: int) -> list[str]:
        """Generate datetime data with specified distribution."""
        start_date = datetime(2000, 1, 1, 0, 0, 0)
        end_date = datetime(2025, 12, 31, 23, 59, 59)
        return self._generate_temporal_data(
            rows, start_date, end_date, "%Y-%m-%d %H:%M:%S", "seconds"
        )

    def generate_time(self, rows: int) -> list[str]:
        """Generate time data with specified distribution."""
        if self.distribution == "uniform":
            return [self._generate_random_time() for _ in range(rows)]

        # For other distributions, use parameters appropriate for time
        generator = self.generators.get(self.distribution, self.generators["uniform"])
        params = self._get_time_distribution_params()
        random_seconds = generator.generate(rows, **params).astype(int)
        return [str(timedelta(seconds=max(0, s % 86400)))[:-3] for s in random_seconds]

    def _generate_temporal_data(
        self,
        rows: int,
        start_date: datetime,
        end_date: datetime,
        format_str: str,
        unit: str,
    ) -> list[str]:
        """Generate temporal data with specified distribution."""
        if self.distribution == "uniform":
            if unit == "days":
                delta_days = (end_date - start_date).days
                random_offsets = np.random.randint(0, delta_days, rows)
                return [
                    (start_date + timedelta(days=int(d))).strftime(format_str)
                    for d in random_offsets
                ]
            else:  # seconds
                delta_seconds = int((end_date - start_date).total_seconds())
                random_offsets = np.random.randint(0, delta_seconds, rows)
                return [
                    (start_date + timedelta(seconds=int(s))).strftime(format_str)
                    for s in random_offsets
                ]

        # For other distributions
        generator = self.generators.get(self.distribution, self.generators["uniform"])
        params = self._get_temporal_distribution_params(unit)
        random_offsets = generator.generate(rows, **params).astype(int)

        if unit == "days":
            return [
                (start_date + timedelta(days=max(0, int(d)))).strftime(format_str)
                for d in random_offsets
            ]
        else:
            return [
                (start_date + timedelta(seconds=max(0, int(s)))).strftime(format_str)
                for s in random_offsets
            ]

    def _get_temporal_distribution_params(self, unit: str) -> dict[str, Any]:
        """Get distribution parameters for temporal data."""
        if unit == "days":
            return {
                "loc": 0,
                "scale": 5 * 365,
                "lam": 3650,
                "n": 1000,
                "p": 0.5,
                "shape": 2,
            }
        else:  # seconds
            return {
                "loc": 0,
                "scale": 5 * 365 * 24 * 3600,
                "lam": 3650 * 24 * 3600,
                "n": 1000,
                "p": 0.5,
                "shape": 2,
            }

    def _get_time_distribution_params(self) -> dict[str, Any]:
        """Get distribution parameters for time data."""
        return {
            "loc": 12 * 3600,
            "scale": 3 * 3600,
            "lam": 7200,
            "n": 10,
            "p": 0.5,
            "shape": 2,
        }

    def _generate_random_time(self) -> str:
        """Generate a random time string."""
        random_seconds = np.random.randint(0, 86400)
        return str(timedelta(seconds=random_seconds))[:-3]

    def _generate_random_string(self, length: int) -> str:
        """Generate a random string of specified length."""
        return "".join(np.random.choice(list(self.ALPHABET), size=length))
