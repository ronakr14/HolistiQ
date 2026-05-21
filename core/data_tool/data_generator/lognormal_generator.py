import numpy as np
from performance_data.distribution_generator import DistributionGenerator


class LognormalGenerator(DistributionGenerator):
    def generate(
        self, size: int, mean: float = 0, sigma: float = 1, **kwargs
    ) -> np.ndarray:
        return np.random.lognormal(mean=mean, sigma=sigma, size=size)
