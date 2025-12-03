from . import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

ph = PasswordHasher()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, index=True)
    password_hash = db.Column(db.String(256))
    is_admin = db.Column(db.Boolean, default=False)
    quota_bytes = db.Column(db.BigInteger, default=100 * 1024 * 1024) # Default 100MB
    used_bytes = db.Column(db.BigInteger, default=0)

    def set_password(self, password):
        self.password_hash = ph.hash(password)

    def check_password(self, password):
        try:
            return ph.verify(self.password_hash, password)
        except VerifyMismatchError:
            return False
        except Exception:
            return False

    def get_remaining_quota(self):
        return self.quota_bytes - self.used_bytes

    def has_space(self, size):
        return (self.used_bytes + size) <= self.quota_bytes
