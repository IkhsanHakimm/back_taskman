"""
email_service.py
----------------
Service untuk mengirim email OTP ke user menggunakan Brevo HTTP API.
Menggantikan SMTP untuk menghindari blokir dari server cloud (seperti Railway).
"""

import os
import requests
import logging

logger = logging.getLogger(__name__)

BREVO_API_KEY = os.getenv("BREVO_API_KEY", "")
# Default MAIL_FROM jika tidak ada di env, gunakan email gmail default user
MAIL_FROM = os.getenv("MAIL_FROM", "9a.13.dwinata1@gmail.com")

def send_otp_email(to_email: str, username: str, otp_code: str) -> bool:
    """
    Kirim email OTP ke user menggunakan Brevo API.
    """
    if not BREVO_API_KEY:
        logger.error("BREVO_API_KEY belum diset di .env")
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

    url = "https://api.brevo.com/v3/smtp/email"
    headers = {
        "accept": "application/json",
        "api-key": BREVO_API_KEY,
        "content-type": "application/json"
    }
    payload = {
        "sender": {
            "name": "TaskMan App",
            "email": MAIL_FROM
        },
        "to": [
            {
                "email": to_email,
                "name": username
            }
        ],
        "subject": subject,
        "htmlContent": html_body
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        if response.status_code in (200, 201, 202):
            logger.info(f"OTP email berhasil dikirim ke {to_email} via Brevo API")
            return True
        else:
            logger.error(f"Gagal kirim email OTP via Brevo API: {response.status_code} - {response.text}")
            return False
    except Exception as exc:
        logger.error(f"Exception saat kirim email OTP ke {to_email} via Brevo API: {exc}")
        return False
