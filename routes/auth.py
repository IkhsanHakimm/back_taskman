from flask import Blueprint, request, jsonify, current_app, g
from datetime import datetime, timedelta
import jwt
import random
import os
from mongoengine.errors import NotUniqueError, ValidationError

from extensions import db
from models.user import User
from utils_auth import token_required
from services.email_service import send_otp_email

auth_bp = Blueprint('auth', __name__)

OTP_EXPIRES_MINUTES = int(os.getenv("OTP_EXPIRES_MINUTES", "10"))


def _generate_otp() -> str:
    """Generate 6-digit OTP secara acak."""
    return str(random.randint(100000, 999999))


# ─── Register ─────────────────────────────────────────────────────────────────

@auth_bp.route('/register', methods=['POST'])
def register():
    """
    Daftarkan user baru.
    - Simpan user dengan is_verified=False
    - Generate OTP, simpan ke user, kirim ke email
    - Return 201 + email (untuk UI OTP)
    """
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    email    = data.get('email', '').strip().lower()
    password = data.get('password', '')

    if not username or not email or not password:
        return jsonify({'error': 'username, email dan password wajib diisi'}), 400

    # Cek duplikat sebelum buat user
    if User.objects(email=email).first():
        return jsonify({'error': 'Email sudah terdaftar'}), 400
    if User.objects(username=username).first():
        return jsonify({'error': 'Username sudah digunakan'}), 400

    # Generate OTP
    otp_code    = _generate_otp()
    otp_expires = datetime.utcnow() + timedelta(minutes=OTP_EXPIRES_MINUTES)

    try:
        user = User(
            username       = username,
            email          = email,
            is_verified    = False,
            otp_code       = otp_code,
            otp_expires_at = otp_expires,
        )
        user.set_password(password)
        user.save()
    except (NotUniqueError, ValidationError) as e:
        return jsonify({'error': 'username atau email sudah ada'}), 400

    # Kirim OTP ke email
    sent = send_otp_email(
        to_email  = email,
        username  = username,
        otp_code  = otp_code,
    )

    if not sent:
        # Jika gagal kirim email, hapus user yang baru dibuat agar bisa coba lagi
        user.delete()
        return jsonify({'error': 'Gagal mengirim OTP ke email. Periksa koneksi server.'}), 502

    return jsonify({
        'message': f'OTP telah dikirim ke {email}. Berlaku {OTP_EXPIRES_MINUTES} menit.',
        'email': email,
    }), 201


# ─── Resend OTP ────────────────────────────────────────────────────────────────

@auth_bp.route('/resend-otp', methods=['POST'])
def resend_otp():
    """
    Kirim ulang OTP ke email yang sudah terdaftar tapi belum diverifikasi.
    """
    data  = request.get_json() or {}
    email = data.get('email', '').strip().lower()

    if not email:
        return jsonify({'error': 'email wajib diisi'}), 400

    user = User.objects(email=email).first()
    if not user:
        return jsonify({'error': 'Email tidak ditemukan'}), 404
    if user.is_verified:
        return jsonify({'error': 'Akun sudah terverifikasi'}), 400

    # Generate OTP baru
    otp_code    = _generate_otp()
    otp_expires = datetime.utcnow() + timedelta(minutes=OTP_EXPIRES_MINUTES)

    user.otp_code       = otp_code
    user.otp_expires_at = otp_expires
    user.save()

    sent = send_otp_email(
        to_email = email,
        username = user.username,
        otp_code = otp_code,
    )

    if not sent:
        return jsonify({'error': 'Gagal mengirim OTP. Coba lagi.'}), 502

    return jsonify({
        'message': f'OTP baru telah dikirim ke {email}',
        'email': email,
    }), 200


# ─── Verify OTP ────────────────────────────────────────────────────────────────

@auth_bp.route('/verify-otp', methods=['POST'])
def verify_otp():
    """
    Verifikasi kode OTP.
    Jika valid: tandai is_verified=True, hapus OTP, kembalikan JWT token.
    """
    data     = request.get_json() or {}
    email    = data.get('email', '').strip().lower()
    otp_code = data.get('otp_code', '').strip()

    if not email or not otp_code:
        return jsonify({'error': 'email dan otp_code wajib diisi'}), 400

    user = User.objects(email=email).first()
    if not user:
        return jsonify({'error': 'Email tidak ditemukan'}), 404

    if user.is_verified:
        return jsonify({'error': 'Akun sudah terverifikasi, silakan login'}), 400

    # Cek apakah OTP ada
    if not user.otp_code:
        return jsonify({'error': 'Tidak ada OTP aktif. Minta OTP baru.'}), 400

    # Cek expiry
    if user.otp_expires_at and datetime.utcnow() > user.otp_expires_at:
        return jsonify({'error': 'OTP sudah kedaluwarsa. Minta OTP baru.'}), 400

    # Cek kode
    if user.otp_code != otp_code:
        return jsonify({'error': 'Kode OTP salah'}), 400

    # OTP valid — verifikasi akun
    user.is_verified    = True
    user.otp_code       = None
    user.otp_expires_at = None
    user.save()

    # Generate JWT token langsung (user tidak perlu login ulang)
    secret      = current_app.config.get('SECRET_KEY')
    exp_minutes = current_app.config.get('JWT_EXPIRES_MINUTES', 60)
    payload = {
        'sub': str(user.id),
        'iat': datetime.utcnow(),
        'exp': datetime.utcnow() + timedelta(minutes=exp_minutes),
    }
    token = jwt.encode(payload, secret, algorithm='HS256')

    return jsonify({
        'message': 'Akun berhasil diverifikasi!',
        'access_token': token,
        'user': user.to_dict(),
    }), 200


# ─── Login ─────────────────────────────────────────────────────────────────────

@auth_bp.route('/login', methods=['POST'])
def login():
    data       = request.get_json() or {}
    identifier = data.get('username') or data.get('email')
    password   = data.get('password')

    if not identifier or not password:
        return jsonify({'error': 'username/email dan password wajib diisi'}), 400

    # Cari user
    user = None
    if '@' in identifier:
        user = User.objects(email=identifier.lower()).first()
    if not user:
        user = User.objects(username=identifier).first()

    if not user or not user.check_password(password):
        return jsonify({'error': 'Email/username atau password salah'}), 401

    # Cek verifikasi — kecuali akun Google (login dengan password internal)
    if not user.is_verified and not user.google_connected:
        return jsonify({
            'error': 'Akun belum diverifikasi. Cek email Anda untuk kode OTP.',
            'needs_verification': True,
            'email': user.email,
        }), 403

    secret      = current_app.config.get('SECRET_KEY')
    exp_minutes = current_app.config.get('JWT_EXPIRES_MINUTES', 60)
    payload = {
        'sub': str(user.id),
        'iat': datetime.utcnow(),
        'exp': datetime.utcnow() + timedelta(minutes=exp_minutes),
    }
    token = jwt.encode(payload, secret, algorithm='HS256')

    return jsonify({
        'access_token': token,
        'user': user.to_dict(),
    })


# ─── Get Me ────────────────────────────────────────────────────────────────────

@auth_bp.route('/me', methods=['GET'])
@token_required
def get_me():
    """Return current logged-in user based on JWT token."""
    user = g.current_user
    return jsonify({'user': user.to_dict()})


# ─── Google Token ──────────────────────────────────────────────────────────────

@auth_bp.route('/google-token', methods=['POST'])
@token_required
def save_google_token():
    """
    Simpan status koneksi Google untuk user yang sudah login.
    Flutter mengirim email Google setelah berhasil OAuth2.
    """
    data         = request.get_json() or {}
    google_email = data.get('google_email', '').strip()

    if not google_email:
        return jsonify({'error': 'google_email wajib diisi'}), 400

    user = g.current_user
    User.objects(id=user.id).update_one(
        set__google_email    = google_email,
        set__google_connected= True,
        set__is_verified     = True,   # akun Google otomatis terverifikasi
    )

    return jsonify({
        'message': 'Akun Google berhasil dihubungkan',
        'google_email': google_email,
    }), 200


# ─── Google Disconnect ─────────────────────────────────────────────────────────

@auth_bp.route('/google-disconnect', methods=['POST'])
@token_required
def disconnect_google():
    """Lepas koneksi Google dari akun Taskman user."""
    User.objects(id=g.current_user.id).update_one(
        set__google_email    = '',
        set__google_connected= False,
    )
    return jsonify({'message': 'Koneksi Google dilepas'}), 200


# ─── Google Direct Login ───────────────────────────────────────────────────────

@auth_bp.route('/google-login', methods=['POST'])
def google_login():
    """
    Jalur khusus login menggunakan Google.
    Menerima email, google_id, dan display_name.
    Jika user ada, langsung izinkan masuk. Jika tidak ada, daftarkan otomatis.
    """
    data         = request.get_json() or {}
    email        = data.get('email', '').strip().lower()
    google_id    = data.get('google_id', '').strip()
    display_name = data.get('display_name', '').strip()

    if not email or not google_id:
        return jsonify({'error': 'email dan google_id wajib diisi'}), 400

    user = User.objects(email=email).first()

    if not user:
        # User belum ada, otomatis daftarkan
        base_username = display_name.replace(' ', '_').lower() if display_name else email.split('@')[0]
        username = base_username
        
        # Pastikan username unik
        counter = 1
        while User.objects(username=username).first():
            username = f"{base_username}{counter}"
            counter += 1

        import secrets
        user = User(
            username=username,
            email=email,
            is_verified=True,
            google_email=email,
            google_connected=True,
            nama_lengkap=display_name
        )
        user.set_password(f"g_{secrets.token_urlsafe(16)}")
        user.save()
    else:
        # Jika user sudah ada, pastikan status terverifikasi dan terkoneksi
        update_needed = False
        if not user.google_connected:
            user.google_connected = True
            user.google_email = email
            update_needed = True
        if not user.is_verified:
            user.is_verified = True
            update_needed = True
            
        if update_needed:
            user.save()

    # Generate JWT token
    secret      = current_app.config.get('SECRET_KEY')
    exp_minutes = current_app.config.get('JWT_EXPIRES_MINUTES', 60)
    payload = {
        'sub': str(user.id),
        'iat': datetime.utcnow(),
        'exp': datetime.utcnow() + timedelta(minutes=exp_minutes),
    }
    token = jwt.encode(payload, secret, algorithm='HS256')

    return jsonify({
        'message': 'Login Google berhasil',
        'access_token': token,
        'user': user.to_dict(),
    }), 200
