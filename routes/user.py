from flask import Blueprint, request, jsonify, g
from models.user import User
from utils_auth import token_required
from datetime import datetime, timedelta
import os
from services.email_service import send_otp_email
import random

user_bp = Blueprint('user', __name__)

OTP_EXPIRES_MINUTES = int(os.getenv("OTP_EXPIRES_MINUTES", "10"))

def _generate_otp() -> str:
    return str(random.randint(100000, 999999))


# ─── Get Profile ──────────────────────────────────────────────────────────────

@user_bp.route('/profile', methods=['GET'])
@token_required
def get_profile():
    """Ambil profil user yang sedang login."""
    user = g.current_user
    return jsonify({'user': user.to_dict()}), 200


# ─── Update Profile ───────────────────────────────────────────────────────────

@user_bp.route('/profile', methods=['PUT'])
@token_required
def update_profile():
    """
    Update username dan/atau email user yang sedang login.
    Body: { "username": "...", "email": "..." }
    """
    data     = request.get_json() or {}
    username = data.get('username', '').strip()
    email    = data.get('email', '').strip().lower()
    
    # Extended profile fields
    nama_lengkap  = data.get('nama_lengkap', '').strip()
    nomor_wa      = data.get('nomor_wa', '').strip()
    alamat        = data.get('alamat', '').strip()
    tanggal_lahir = data.get('tanggal_lahir', '').strip()
    nim           = data.get('nim', '').strip()
    program_studi = data.get('program_studi', '').strip()
    fakultas      = data.get('fakultas', '').strip()
    
    user     = g.current_user

    if not username and not email and not any([nama_lengkap, nomor_wa, alamat, tanggal_lahir, nim, program_studi, fakultas]):
        return jsonify({'error': 'Tidak ada data yang diperbarui'}), 400

    # Cek duplikat username (jika berubah)
    if username and username != user.username:
        if User.objects(username=username).first():
            return jsonify({'error': 'Username sudah digunakan'}), 400

    # Cek duplikat email (jika berubah)
    if email and email != user.email:
        if User.objects(email=email).first():
            return jsonify({'error': 'Email sudah terdaftar'}), 400

    # Update field
    if username:
        user.username = username
    if email:
        user.email = email
        
    if 'nama_lengkap' in data: user.nama_lengkap = nama_lengkap
    if 'nomor_wa' in data: user.nomor_wa = nomor_wa
    if 'alamat' in data: user.alamat = alamat
    if 'tanggal_lahir' in data: user.tanggal_lahir = tanggal_lahir
    if 'nim' in data: user.nim = nim
    if 'program_studi' in data: user.program_studi = program_studi
    if 'fakultas' in data: user.fakultas = fakultas

    user.save()

    return jsonify({
        'message': 'Profil berhasil diperbarui',
        'user': user.to_dict(),
    }), 200


# ─── Change Password ──────────────────────────────────────────────────────────

@user_bp.route('/change-password', methods=['PUT'])
@token_required
def change_password():
    """
    Ubah password user yang sedang login.
    Body: { "current_password": "...", "new_password": "..." }
    """
    data             = request.get_json() or {}
    current_password = data.get('current_password', '')
    new_password     = data.get('new_password', '')
    user             = g.current_user

    if not current_password or not new_password:
        return jsonify({'error': 'current_password dan new_password wajib diisi'}), 400

    if len(new_password) < 6:
        return jsonify({'error': 'Password baru minimal 6 karakter'}), 400

    # Verifikasi password lama
    if not user.check_password(current_password):
        return jsonify({'error': 'Password saat ini salah'}), 401

    if current_password == new_password:
        return jsonify({'error': 'Password baru tidak boleh sama dengan password lama'}), 400

    user.set_password(new_password)
    user.save()

    return jsonify({'message': 'Password berhasil diubah'}), 200


# ─── Forgot Password — Request OTP ───────────────────────────────────────────

@user_bp.route('/forgot-password', methods=['POST'])
def forgot_password():
    """
    Kirim OTP ke email untuk reset password.
    Body: { "email": "..." }
    """
    data  = request.get_json() or {}
    email = data.get('email', '').strip().lower()

    if not email:
        return jsonify({'error': 'email wajib diisi'}), 400

    user = User.objects(email=email).first()
    if not user:
        # Jangan beri tahu apakah email ada atau tidak (security best practice)
        return jsonify({'message': f'Jika email {email} terdaftar, OTP akan dikirim'}), 200

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
        'message': f'OTP untuk reset password dikirim ke {email}',
        'email': email,
    }), 200


# ─── Forgot Password — Verify OTP & Reset ────────────────────────────────────

@user_bp.route('/reset-password', methods=['POST'])
def reset_password():
    """
    Verifikasi OTP dan set password baru.
    Body: { "email": "...", "otp_code": "...", "new_password": "..." }
    """
    data         = request.get_json() or {}
    email        = data.get('email', '').strip().lower()
    otp_code     = data.get('otp_code', '').strip()
    new_password = data.get('new_password', '')

    if not email or not otp_code or not new_password:
        return jsonify({'error': 'email, otp_code, dan new_password wajib diisi'}), 400

    if len(new_password) < 6:
        return jsonify({'error': 'Password baru minimal 6 karakter'}), 400

    user = User.objects(email=email).first()
    if not user:
        return jsonify({'error': 'Email tidak ditemukan'}), 404

    if not user.otp_code:
        return jsonify({'error': 'Tidak ada OTP aktif. Minta OTP baru.'}), 400

    if user.otp_expires_at and datetime.utcnow() > user.otp_expires_at:
        return jsonify({'error': 'OTP sudah kedaluwarsa. Minta OTP baru.'}), 400

    if user.otp_code != otp_code:
        return jsonify({'error': 'Kode OTP salah'}), 400

    # OTP valid — reset password
    user.set_password(new_password)
    user.otp_code       = None
    user.otp_expires_at = None
    user.save()

    return jsonify({'message': 'Password berhasil direset. Silakan login.'}), 200
