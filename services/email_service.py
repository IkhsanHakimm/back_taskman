"""
email_service.py
----------------
Service untuk mengirim email OTP ke user menggunakan Gmail SMTP.
Konfigurasi diambil dari environment variables.
"""

import os
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

MAIL_SERVER   = os.getenv("MAIL_SERVER", "smtp.gmail.com")
MAIL_PORT     = int(os.getenv("MAIL_PORT", "587"))
MAIL_USERNAME = os.getenv("MAIL_USERNAME", "")
MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "")
MAIL_FROM     = os.getenv("MAIL_FROM", MAIL_USERNAME)


def send_otp_email(to_email: str, username: str, otp_code: str) -> bool:
    """
    Kirim email OTP ke user.

    Args:
        to_email:  Alamat email tujuan.
        username:  Nama user (untuk personalisasi).
        otp_code:  6-digit kode OTP.

    Returns:
        True jika berhasil, False jika gagal.
    """
    if not MAIL_USERNAME or not MAIL_PASSWORD:
        logger.error("MAIL_USERNAME atau MAIL_PASSWORD belum diset di .env")
        return False

    subject = "Kode Verifikasi TaskMan - OTP Anda"

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="UTF-8">
      <style>
        body {{ font-family: Arial, sans-serif; background-color: #f4f4f4; margin: 0; padding: 0; }}
        .container {{ max-width: 480px; margin: 40px auto; background: #ffffff;
                      border-radius: 16px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }}
        .header {{ background: linear-gradient(135deg, #7C3AED, #9F67ED);
                   padding: 32px; text-align: center; }}
        .header h1 {{ color: #ffffff; margin: 0; font-size: 24px; letter-spacing: 1px; }}
        .header p {{ color: rgba(255,255,255,0.8); margin: 8px 0 0; font-size: 14px; }}
        .body {{ padding: 32px; }}
        .greeting {{ font-size: 16px; color: #374151; margin-bottom: 16px; }}
        .otp-box {{ background: #F5F3FF; border: 2px dashed #7C3AED; border-radius: 12px;
                    text-align: center; padding: 24px; margin: 24px 0; }}
        .otp-code {{ font-size: 42px; font-weight: bold; color: #7C3AED;
                     letter-spacing: 10px; font-family: monospace; }}
        .otp-label {{ font-size: 13px; color: #6B7280; margin-top: 8px; }}
        .note {{ background: #FEF3C7; border-left: 4px solid #F59E0B; border-radius: 8px;
                 padding: 12px 16px; font-size: 13px; color: #92400E; margin-top: 16px; }}
        .footer {{ background: #F9FAFB; padding: 20px; text-align: center;
                   font-size: 12px; color: #9CA3AF; }}
      </style>
    </head>
    <body>
      <div class="container">
        <div class="header">
          <h1>✅ TaskMan</h1>
          <p>Verifikasi Akun Anda</p>
        </div>
        <div class="body">
          <p class="greeting">Halo, <strong>{username}</strong>!</p>
          <p style="color:#6B7280; font-size:14px;">
            Terima kasih sudah mendaftar di <strong>TaskMan</strong>. 
            Gunakan kode OTP berikut untuk memverifikasi akun Anda:
          </p>
          <div class="otp-box">
            <div class="otp-code">{otp_code}</div>
            <div class="otp-label">Kode berlaku selama <strong>10 menit</strong></div>
          </div>
          <div class="note">
            ⚠️ Jangan bagikan kode ini kepada siapapun. 
            TaskMan tidak pernah meminta kode OTP melalui telepon atau chat.
          </div>
        </div>
        <div class="footer">
          © 2025 TaskMan · Email ini dikirim otomatis, jangan dibalas.
        </div>
      </div>
    </body>
    </html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"TaskMan <{MAIL_FROM}>"
    msg["To"]      = to_email
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP(MAIL_SERVER, MAIL_PORT, timeout=15, source_address=('0.0.0.0', 0)) as server:
            server.ehlo()
            server.starttls()
            server.login(MAIL_USERNAME, MAIL_PASSWORD)
            server.sendmail(MAIL_FROM, to_email, msg.as_string())
        logger.info(f"OTP email berhasil dikirim ke {to_email}")
        return True
    except smtplib.SMTPAuthenticationError:
        logger.error("Gmail SMTP auth gagal — periksa MAIL_USERNAME & MAIL_PASSWORD di .env")
        return False
    except Exception as exc:
        logger.error(f"Gagal kirim email OTP ke {to_email}: {exc}")
        return False
