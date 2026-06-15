from functools import wraps

import jwt
from flask import request, jsonify, current_app, g

from models.user import User


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        token = None

        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1].strip()

        if not token:
            return (
                jsonify({"error": "Authorization header with Bearer token is required"}),
                401,
            )

        try:
            payload = jwt.decode(
                token,
                current_app.config.get("SECRET_KEY"),
                algorithms=["HS256"],
            )
            user_id = payload.get("sub")
            if not user_id:
                raise ValueError("Missing subject in token")

            user = User.objects(id=user_id).first()
            if not user:
                raise ValueError("User not found")
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, ValueError) as exc:
            current_app.logger.warning(f"JWT error: {exc}")
            return jsonify({"error": "Invalid or expired token"}), 401

        g.current_user = user
        return f(*args, **kwargs)

    return decorated

