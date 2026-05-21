from core.infrastructure.messaging.email.providers.gmail_provider import GmailProvider
from core.infrastructure.messaging.email.providers.resend_provider import ResendProvider

PROVIDERS = {
    "gmail": GmailProvider(),
    "resend": ResendProvider(),
}


def get_provider(name: str):
    provider = PROVIDERS.get(name)
    if not provider:
        raise ValueError(f"Email provider '{name}' not supported.")
    return provider
