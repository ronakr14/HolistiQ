import numpy as np
from performance_data.distribution_generator import DistributionGenerator


class PoissonGenerator(DistributionGenerator):
    def generate(self, size: int, lam: float = 5, **kwargs) -> np.ndarray:
        return np.random.poisson(lam=lam, size=size)
