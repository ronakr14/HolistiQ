from abc import ABC, abstractmethod

import numpy as np


class DistributionGenerator(ABC):
    """Abstract base class for distribution generators."""

    @abstractmethod
    def generate(self, size: int, **kwargs) -> np.ndarray:
        """Generate data with specific distribution."""
        pass
