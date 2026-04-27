import logging
import os
import smtplib
from abc import ABC, abstractmethod
from email.message import EmailMessage
from urllib.parse import parse_qs, urlparse


class EmailSender(ABC):
    @abstractmethod
    def send_magic_link(self, email: str, subject: str, link: str) -> None:
        raise NotImplementedError


class DevMockEmailSender(EmailSender):
    def send_magic_link(self, email: str, subject: str, link: str) -> None:
        # Dev-safe mock: no real delivery, just logs to backend stdout.
        logging.info("[DEV_EMAIL] to=%s subject=%s link=%s", email, subject, link)


class SmtpEmailSender(EmailSender):
    def __init__(self) -> None:
        self.host = os.getenv("SMTP_HOST", "").strip()
        self.port = int(os.getenv("SMTP_PORT", "587"))
        self.username = os.getenv("SMTP_USERNAME", "").strip()
        self.password = os.getenv("SMTP_PASSWORD", "").strip()
        self.from_email = os.getenv("SMTP_FROM_EMAIL", self.username).strip()
        self.from_name = os.getenv("SMTP_FROM_NAME", "KairaVPN").strip()
        self.use_tls = os.getenv("SMTP_USE_TLS", "true").strip().lower() == "true"
        self.use_ssl = os.getenv("SMTP_USE_SSL", "false").strip().lower() == "true"
        self.timeout_seconds = float(os.getenv("SMTP_TIMEOUT_SECONDS", "15"))
        self.app_name = os.getenv("EMAIL_APP_NAME", "KairaVPN").strip()

        if not self.host:
            raise ValueError("SMTP_HOST must be set when EMAIL_SENDER_MODE=smtp.")
        if not self.from_email:
            raise ValueError("SMTP_FROM_EMAIL or SMTP_USERNAME must be set for SMTP sender.")

    def _build_message(self, email: str, subject: str, link: str) -> EmailMessage:
        parsed = urlparse(link)
        token = parse_qs(parsed.query).get("token", [""])[0]
        text_template = os.getenv(
            "EMAIL_MAGIC_TEXT_TEMPLATE",
            (
                "Sign in to {app_name}.\n\n"
                "Open this link:\n{link}\n\n"
                "If your page asks for token, paste this value:\n{token}\n\n"
                "If you did not request this email, ignore it."
            ),
        )
        html_template = os.getenv(
            "EMAIL_MAGIC_HTML_TEMPLATE",
            (
                "<p>Sign in to <strong>{app_name}</strong>.</p>"
                "<p><a href=\"{link}\">Open sign-in link</a></p>"
                "<p>If your page asks for token, use:<br><code>{token}</code></p>"
                "<p>If you did not request this email, ignore it.</p>"
            ),
        )
        text_body = text_template.format(app_name=self.app_name, link=link, token=token)
        html_body = html_template.format(app_name=self.app_name, link=link, token=token)

        message = EmailMessage()
        message["Subject"] = subject
        message["To"] = email
        message["From"] = f"{self.from_name} <{self.from_email}>"
        message.set_content(text_body)
        message.add_alternative(html_body, subtype="html")
        return message

    def send_magic_link(self, email: str, subject: str, link: str) -> None:
        message = self._build_message(email=email, subject=subject, link=link)
        if self.use_ssl:
            with smtplib.SMTP_SSL(self.host, self.port, timeout=self.timeout_seconds) as server:
                if self.username:
                    server.login(self.username, self.password)
                server.send_message(message)
            return

        with smtplib.SMTP(self.host, self.port, timeout=self.timeout_seconds) as server:
            if self.use_tls:
                server.starttls()
            if self.username:
                server.login(self.username, self.password)
            server.send_message(message)


def get_email_sender() -> EmailSender:
    mode = os.getenv("EMAIL_SENDER_MODE", "mock").strip().lower()
    if mode == "mock":
        return DevMockEmailSender()
    if mode == "smtp":
        return SmtpEmailSender()

    logging.warning("Unknown EMAIL_SENDER_MODE=%s, fallback to mock sender.", mode)
    return DevMockEmailSender()
