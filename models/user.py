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
            'created_at': self.created_at.isoformat()
        }

    def __repr__(self):
        return f"<User {self.username}>"
