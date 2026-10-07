import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import datetime

# Global notification log for in-app alert feeds
IN_APP_NOTIFICATIONS = []

def send_email_alert(
    to_email: str,
    subject: str,
    body_text: str,
    body_html: str = "",
    smtp_config: dict = None
):
    """
    Send email alert via SMTP if credentials provided,
    and always store an in-app notification alert.
    """
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Always log in-app notification
    notification_entry = {
        "to_email": to_email,
        "subject": subject,
        "message": body_text,
        "timestamp": now_str,
        "status": "LOGGED"
    }
    IN_APP_NOTIFICATIONS.append(notification_entry)

    if not smtp_config or not smtp_config.get("server") or smtp_config.get("server") == "smtp.example.com":
        print(f"[Email Alert Simulated] To: {to_email} | Subject: {subject} | Msg: {body_text}")
        return False, "SMTP server not configured. Email logged in-app."

    try:
        server = smtp_config.get("server")
        port = smtp_config.get("port", 587)
        user = smtp_config.get("username")
        password = smtp_config.get("password")
        sender = smtp_config.get("sender_email", user)

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[SupplyChain Alert] {subject}"
        msg["From"] = sender
        msg["To"] = to_email

        msg.attach(MIMEText(body_text, "plain"))
        if body_html:
            msg.attach(MIMEText(body_html, "html"))

        with smtplib.SMTP(server, port, timeout=5) as smtp:
            smtp.starttls()
            if user and password:
                smtp.login(user, password)
            smtp.sendmail(sender, [to_email], msg.as_string())

        notification_entry["status"] = "SENT_VIA_SMTP"
        print(f"[Email Alert Sent] To: {to_email} | Subject: {subject}")
        return True, "Email sent successfully"

    except Exception as e:
        print(f"[Email Alert Failed] Error sending to {to_email}: {e}")
        return False, str(e)

def get_in_app_notifications(to_email: str = None):
    """Filter in-app notifications by email or return all."""
    if not to_email:
        return IN_APP_NOTIFICATIONS[-50:] # Return last 50
    return [n for n in IN_APP_NOTIFICATIONS if n["to_email"] == to_email or n["to_email"] == "admin@supplychain.eth"][-30:]
