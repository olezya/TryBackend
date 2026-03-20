from email.message import EmailMessage
import aiosmtplib

async def send_email(to_email: str, subject: str, body: str):
    message = EmailMessage()
    message["From"] = "no-reply@hotelapp.com"
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(body)

    await aiosmtplib.send(
        message,
        hostname="localhost",
        port=1025  # MailHog default
    )