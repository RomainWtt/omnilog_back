# app/core/email.py
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from pydantic import EmailStr
from jinja2 import Template
from app.core.config import settings  # ← Importer settings

# Configuration SMTP depuis settings
conf = ConnectionConfig(
    MAIL_USERNAME=settings.MAIL_USERNAME,
    MAIL_PASSWORD=settings.MAIL_PASSWORD,
    MAIL_FROM=settings.MAIL_FROM,
    MAIL_PORT=settings.MAIL_PORT,
    MAIL_SERVER=settings.MAIL_SERVER,
    MAIL_STARTTLS=True,
    MAIL_SSL_TLS=False,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True
)

fast_mail = FastMail(conf)

# Template HTML pour l'email de vérification
EMAIL_VERIFICATION_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
            border-radius: 10px 10px 0 0;
        }
        .content {
            background: #f9f9f9;
            padding: 30px;
            border-radius: 0 0 10px 10px;
        }
        .button {
            display: inline-block;
            padding: 12px 30px;
            background: #667eea;
            color: white;
            text-decoration: none;
            border-radius: 5px;
            margin: 20px 0;
        }
        .footer {
            text-align: center;
            color: #666;
            font-size: 12px;
            margin-top: 30px;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🎬 Omnilog</h1>
        <p>Vérifiez votre adresse email</p>
    </div>
    <div class="content">
        <p>Bonjour {{ username }},</p>
        <p>Merci de vous être inscrit sur Omnilog ! Pour activer votre compte, veuillez cliquer sur le bouton ci-dessous :</p>
        <p style="text-align: center;">
            <a href="{{ verification_url }}" class="button">Vérifier mon email</a>
        </p>
        <p>Ou copiez ce lien dans votre navigateur :</p>
        <p style="word-break: break-all; color: #667eea;">{{ verification_url }}</p>
        <p>Ce lien expirera dans 24 heures.</p>
        <p>Si vous n'avez pas créé de compte, vous pouvez ignorer cet email.</p>
    </div>
    <div class="footer">
        <p>© 2024 Omnilog - Votre plateforme de suivi de médias</p>
    </div>
</body>
</html>
"""


async def send_verification_email(
        email: EmailStr,
        username: str,
        verification_token: str,
        frontend_url: str
):
    """Envoie un email de vérification"""
    verification_url = f"{frontend_url}/verify-email/{verification_token}"

    template = Template(EMAIL_VERIFICATION_TEMPLATE)
    html_content = template.render(
        username=username,
        verification_url=verification_url
    )

    message = MessageSchema(
        subject="✨ Vérifiez votre email - Omnilog",
        recipients=[email],
        body=html_content,
        subtype="html"
    )

    await fast_mail.send_message(message)
    print(f"✅ Email de vérification envoyé à {email}")