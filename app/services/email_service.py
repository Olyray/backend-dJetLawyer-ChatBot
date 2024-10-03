import logging
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def send_verification_email(email: str, token: str):
    verify_url = f"{settings.SERVER_HOST}/api/v1/auth/verify-email?token={token}"
    
    message = MIMEMultipart("alternative")
    message["Subject"] = "Verify your email"
    message["From"] = settings.MAIL_FROM
    message["To"] = email

    text = f"Please click the link below to verify your email:\n\n{verify_url}"
    html = f"""\
    <html>
      <body>
        <p>Please click the link below to verify your email:<br>
           <a href="{verify_url}">{verify_url}</a>
        </p>
      </body>
    </html>
    """

    part1 = MIMEText(text, "plain")
    part2 = MIMEText(html, "html")

    message.attach(part1)
    message.attach(part2)

    # New Addition: Create a secure SSL/TLS context
    context = ssl.create_default_context()

    try:
        logger.info(f"Attempting to connect to email server: {settings.MAIL_SERVER}:{settings.MAIL_PORT}")
        # New Addition: Use SMTP instead of SMTP_SSL for TLS
        with smtplib.SMTP(settings.MAIL_SERVER, settings.MAIL_PORT) as server:
            # New Addition: Start TLS for security
            server.starttls(context=context)
            
            logger.info(f"Attempting to login with username: {settings.MAIL_USERNAME}")
            server.login(settings.MAIL_USERNAME, settings.MAIL_PASSWORD)
            logger.info(f"Attempting to send email to: {email}")
            server.sendmail(settings.MAIL_FROM, email, message.as_string())
        logger.info(f"Email sent successfully to {email}")
        return True
    except smtplib.SMTPException as e:
        logger.error(f"SMTP error occurred: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Failed to send email: {str(e)}")
        return False