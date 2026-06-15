from flask_mongoengine import MongoEngine
from werkzeug.security import generate_password_hash, check_password_hash


db = MongoEngine()

def hash_password(password: str) -> str:
    return generate_password_hash(password)

def check_password(hash: str, password: str) -> bool:
    return check_password_hash(hash, password)
