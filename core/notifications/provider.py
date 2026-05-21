from abc import ABC, abstractmethod
from core.data.models.infrastructure.messaging import EmailMessageModel


class BaseEmailProvider(ABC):
    @abstractmethod
    def send(self, message: EmailMessageModel) -> bool:
        pass
