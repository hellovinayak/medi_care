"""Email service for sending appointment confirmations.

Uses SMTP (Gmail) when configured, otherwise logs the email.
"""

from config import get_settings
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

settings = get_settings()


def send_appointment_email(
    patient_email: str,
    patient_name: str,
    doctor_name: str,
    doctor_specialty: str,
    date: str,
    time_slot: str,
    appointment_id: int
) -> str:
    """Send appointment confirmation email."""

    subject = f"MediConnect - Appointment Confirmation #{appointment_id}"

    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: linear-gradient(135deg, #0066cc, #004d99); color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0;">
            <h1 style="margin: 0;">MediConnect</h1>
            <p style="margin: 5px 0 0;">Appointment Confirmation</p>
        </div>
        <div style="padding: 30px; background: #f9f9f9;">
            <h2 style="color: #0066cc;">Hello {patient_name},</h2>
            <p>Your appointment has been confirmed! Here are the details:</p>
            <div style="background: white; padding: 20px; border-radius: 8px; border-left: 4px solid #00cc99;">
                <table style="width: 100%; border-collapse: collapse;">
                    <tr><td style="padding: 8px 0; font-weight: bold; color: #666;">Appointment ID:</td><td>#{appointment_id}</td></tr>
                    <tr><td style="padding: 8px 0; font-weight: bold; color: #666;">Doctor:</td><td>{doctor_name}</td></tr>
                    <tr><td style="padding: 8px 0; font-weight: bold; color: #666;">Specialty:</td><td>{doctor_specialty}</td></tr>
                    <tr><td style="padding: 8px 0; font-weight: bold; color: #666;">Date:</td><td>{date}</td></tr>
                    <tr><td style="padding: 8px 0; font-weight: bold; color: #666;">Time:</td><td>{time_slot}</td></tr>
                    <tr><td style="padding: 8px 0; font-weight: bold; color: #666;">Status:</td><td style="color: #00cc99; font-weight: bold;">Confirmed ✓</td></tr>
                </table>
            </div>
            <p style="margin-top: 20px; color: #666;">Please arrive 10 minutes before your scheduled time.</p>
            <p style="color: #666;">If you need to reschedule or cancel, please contact us or use the MediConnect app.</p>
        </div>
        <div style="background: #004d99; color: white; padding: 15px; text-align: center; border-radius: 0 0 8px 8px;">
            <p style="margin: 0; font-size: 12px;">MediConnect Healthcare | Chennai City - 600127 | Phone: 00121012</p>
        </div>
    </body>
    </html>
    """

    if not settings.EMAIL_ENABLED:
        print(f"📧 [MOCK EMAIL] To: {patient_email}")
        print(f"   Subject: {subject}")
        print(f"   Appointment #{appointment_id}: {patient_name} with {doctor_name} on {date} at {time_slot}")
        return "mock_sent"

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = settings.EMAIL_FROM
        msg['To'] = patient_email

        msg.attach(MIMEText(html_body, 'html'))

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)

        return "sent"
    except Exception as e:
        print(f"⚠️ Email error: {e}")
        return "mock_sent"
