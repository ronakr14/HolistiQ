import numpy as np
from performance_data.distribution_generator import DistributionGenerator


class UniformGenerator(DistributionGenerator):
    def generate(
        self, size: int, low: float = 0, high: float = 100, **kwargs
    ) -> np.ndarray:
        return np.random.uniform(low=low, high=high, size=size)
