import numpy as np
from performance_data.distribution_generator import DistributionGenerator


class GammaGenerator(DistributionGenerator):
    def generate(
        self, size: int, shape: float = 2, scale: float = 2, **kwargs
    ) -> np.ndarray:
        return np.random.gamma(shape=shape, scale=scale, size=size)
