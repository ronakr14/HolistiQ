import numpy as np
from performance_data.distribution_generator import DistributionGenerator


class ParetoGenerator(DistributionGenerator):
    def generate(self, size: int, a: float = 2, **kwargs) -> np.ndarray:
        return np.random.pareto(a=a, size=size)
