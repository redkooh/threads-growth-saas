"""Email utilities — Gmail SMTP via app password."""
import os, smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from setup_logging import get_logger

logger = get_logger(__name__)

SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "465"))
SMTP_USER = os.environ.get("SMTP_USER", "growpilotgpt@gmail.com")
SMTP_PASS = os.environ.get("SMTP_PASS", "pxfg jqbl eqqp qfpv")

BASE_URL = os.environ.get("SITE_URL", "https://growpilotgpt.com").rstrip("/")
FROM_NAME = "Threads Growth"
FROM_EMAIL = SMTP_USER


def set_base_url(url: str):
    global BASE_URL
    BASE_URL = url.rstrip("/")


def _send_email(to: str, subject: str, html: str) -> bool:
    """Send an HTML email via Gmail SMTP (SSL). Returns True on success."""
    msg = MIMEMultipart("alternative")
    msg["From"] = f"{FROM_NAME} <{FROM_EMAIL}>"
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(html, "html"))

    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=ctx) as server:
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(FROM_EMAIL, to, msg.as_string())
        logger.info(f"✅ Email sent to {to}: {subject}")
        return True
    except Exception as e:
        logger.error(f"❌ Email send failed to {to}: {e}")
        return False


def send_verification_email(to: str, token: str) -> bool:
    """Send email verification link."""
    link = f"{BASE_URL}/verify-email?token={token}"
    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,sans-serif;background:#0f0f13;padding:40px 20px">
  <div style="max-width:480px;margin:0 auto;background:#1a1a24;border-radius:16px;padding:40px;border:1px solid #2a2a3a">
    <h2 style="color:#e0e0e0;margin:0 0 8px">Welcome to Threads Growth</h2>
    <p style="color:#888;font-size:14px;line-height:1.6">Click the button below to verify your email address and activate your account.</p>
    <a href="{link}" style="display:inline-block;margin:24px 0;padding:14px 32px;border-radius:10px;background:linear-gradient(135deg,#a855f7,#ec4899);color:white;text-decoration:none;font-weight:600;font-size:15px">Verify Email</a>
    <p style="color:#555;font-size:12px">Or copy this link: <br><span style="color:#888">{link}</span></p>
    <p style="color:#555;font-size:12px;margin-top:20px;border-top:1px solid #2a2a3a;padding-top:16px">If you didn't sign up, ignore this email.</p>
  </div>
</body>
</html>"""
    return _send_email(to, "Verify your email — Threads Growth", html)


def send_reset_email(to: str, token: str) -> bool:
    """Send password reset link."""
    link = f"{BASE_URL}/forgot-password?token={token}"
    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,sans-serif;background:#0f0f13;padding:40px 20px">
  <div style="max-width:480px;margin:0 auto;background:#1a1a24;border-radius:16px;padding:40px;border:1px solid #2a2a3a">
    <h2 style="color:#e0e0e0;margin:0 0 8px">Password Reset</h2>
    <p style="color:#888;font-size:14px;line-height:1.6">Click below to reset your password. This link expires in 1 hour.</p>
    <a href="{link}" style="display:inline-block;margin:24px 0;padding:14px 32px;border-radius:10px;background:linear-gradient(135deg,#a855f7,#ec4899);color:white;text-decoration:none;font-weight:600;font-size:15px">Reset Password</a>
    <p style="color:#555;font-size:12px">Or copy: <br><span style="color:#888">{link}</span></p>
    <p style="color:#555;font-size:12px;margin-top:20px;border-top:1px solid #2a2a3a;padding-top:16px">If you didn't request this, ignore this email.</p>
  </div>
</body>
</html>"""
    return _send_email(to, "Reset your password — Threads Growth", html)
