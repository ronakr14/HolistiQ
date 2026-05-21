import numpy as np
from performance_data.distribution_generator import DistributionGenerator


class WeibullGenerator(DistributionGenerator):
    def generate(self, size: int, a: float = 1, **kwargs) -> np.ndarray:
        return np.random.weibull(a=a, size=size)
