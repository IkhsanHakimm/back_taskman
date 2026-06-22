from extensions import db, hash_password, check_password
from datetime import datetime


class User(db.Document):
    username         = db.StringField(required=True, unique=True, max_length=80)
    email            = db.EmailField(required=True, unique=True)
    password_hash    = db.StringField(required=True)
    # Email verification
    is_verified      = db.BooleanField(default=False)
    otp_code         = db.StringField(default=None)
    otp_expires_at   = db.DateTimeField(default=None)
    # Google Workspace integration
    google_email     = db.StringField(default='')
    google_connected = db.BooleanField(default=False)
    # Extended Profile (Progressive Profiling)
    nama_lengkap     = db.StringField(default='')
    nomor_wa         = db.StringField(default='')
    alamat           = db.StringField(default='')
    tanggal_lahir    = db.StringField(default='')
    nim              = db.StringField(default='')
    program_studi    = db.StringField(default='')
    fakultas         = db.StringField(default='')
    
    created_at       = db.DateTimeField(default=datetime.utcnow)

    meta = {
        'collection': 'users',
        'indexes': [
            'username',
            'email',
            {'fields': ['username', 'email'], 'unique': True}
        ]
    }

    def set_password(self, password: str) -> None:
        self.password_hash = hash_password(password)

    def check_password(self, password: str) -> bool:
        return check_password(self.password_hash, password)

    def to_dict(self):
        return {
            'id': str(self.id),
            'username': self.username,
            'email': self.email,
            'is_verified': self.is_verified,
            'google_email': self.google_email or '',
            'google_connected': self.google_connected or False,
            'nama_lengkap': self.nama_lengkap or '',
            'nomor_wa': self.nomor_wa or '',
            'alamat': self.alamat or '',
            'tanggal_lahir': self.tanggal_lahir or '',
            'nim': self.nim or '',
            'program_studi': self.program_studi or '',
            'fakultas': self.fakultas or '',
            'created_at': self.created_at.isoformat()
        }

    def __repr__(self):
        return f"<User {self.username}>"
