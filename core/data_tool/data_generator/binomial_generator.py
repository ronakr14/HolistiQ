import numpy as np
from performance_data.distribution_generator import DistributionGenerator


class BinomialGenerator(DistributionGenerator):
    def generate(self, size: int, n: int = 10, p: float = 0.5, **kwargs) -> np.ndarray:
        return np.random.binomial(n=n, p=p, size=size)
