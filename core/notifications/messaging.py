from dataclasses import dataclass, field
from typing import Optional


@dataclass
class EmailMessageModel:
    to: list[str]
    subject: str
    body: str
    cc: Optional[list[str]] = field(default_factory=list)
    bcc: Optional[list[str]] = field(default_factory=list)
    attachments: Optional[list[str]] = field(default_factory=list)
    notification: bool = False