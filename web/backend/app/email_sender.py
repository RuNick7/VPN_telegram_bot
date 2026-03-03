import os
from abc import ABC, abstractmethod


class EmailSender(ABC):
    @abstractmethod
    def send_magic_link(self, email: str, subject: str, link: str) -> None:
        raise NotImplementedError


class DevMockEmailSender(EmailSender):
    def send_magic_link(self, email: str, subject: str, link: str) -> None:
        # Dev-safe mock: no real delivery, just logs to backend stdout.
        print(
            "[DEV_EMAIL] "
            f"to={email} subject={subject} link={link}"
        )


def get_email_sender() -> EmailSender:
    mode = os.getenv("EMAIL_SENDER_MODE", "mock").strip().lower()
    if mode == "mock":
        return DevMockEmailSender()

    # Only mock sender exists in MVP scaffold.
    return DevMockEmailSender()
