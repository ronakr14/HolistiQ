import numpy as np
from performance_data.distribution_generator import DistributionGenerator


class NormalGenerator(DistributionGenerator):
    def generate(
        self, size: int, loc: float = 0, scale: float = 1, **kwargs
    ) -> np.ndarray:
        return np.random.normal(loc=loc, scale=scale, size=size)
