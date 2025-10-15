from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from jinja2 import Template
from pathlib import Path

from services.auth_service import AuthService
from core.config import Settings

auth_service = AuthService()
settings = Settings()

conf = ConnectionConfig(
    MAIL_USERNAME = settings.mail_username,
    MAIL_PASSWORD = settings.mail_password,
    MAIL_FROM = settings.mail_from,
    MAIL_PORT = settings.mail_port,
    MAIL_SERVER = settings.mail_server,
    MAIL_STARTTLS = settings.mail_starttls,
    MAIL_SSL_TLS = settings.mail_ssl_tls,
    USE_CREDENTIALS = True,
    TEMPLATE_FOLDER = Path(__file__).parent / "templates"
)

async def render_email_template(template_name: str, **kwargs) -> str:
    template_path = Path(__file__).parent / "templates" / template_name
    with open(template_path, "r", encoding="utf-8") as file:
        template_content = file.read()
    template = Template(template_content)
    return template.render(**kwargs)

async def send_verification_email(email: str):
    token_data = {"sub": email}
    verification_token = auth_service.create_email_token(token_data)

    verification_url = f"{settings.host_url}/api/auth/verify-email?token={verification_token}"

    html_content = await render_email_template(
        "verification_email.html",
        verification_url=verification_url,
        email=email
    )

    message = MessageSchema(
        subject="Verify registracion",
        recipients=[email],
        body=html_content,
        subtype="html"
    )

    fm = FastMail(conf)
    await fm.send_message(message)

    return True

