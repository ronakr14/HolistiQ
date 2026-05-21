import numpy as np
from performance_data.distribution_generator import DistributionGenerator


class BetaGenerator(DistributionGenerator):
    def generate(self, size: int, a: float = 2, b: float = 5, **kwargs) -> np.ndarray:
        return np.random.beta(a=a, b=b, size=size)
