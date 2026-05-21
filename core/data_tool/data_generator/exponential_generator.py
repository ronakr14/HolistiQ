import numpy as np
from performance_data.distribution_generator import DistributionGenerator


class ExponentialGenerator(DistributionGenerator):
    def generate(self, size: int, scale: float = 1, **kwargs) -> np.ndarray:
        return np.random.exponential(scale=scale, size=size)
