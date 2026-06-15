from flask import Blueprint, jsonify, request, g
from mongoengine.errors import ValidationError

from models.preferences import UserPreference
from utils_auth import token_required


preferences_bp = Blueprint("preferences", __name__, url_prefix="/me/preferences")


def _get_or_create_preferences(user):
    prefs = UserPreference.objects(owner=user).first()
    if not prefs:
        prefs = UserPreference(owner=user)
        prefs.save()
    return prefs


@preferences_bp.route("", methods=["GET"])
@token_required
def get_preferences():
    prefs = _get_or_create_preferences(g.current_user)
    return jsonify(prefs.to_dict())


@preferences_bp.route("", methods=["PUT", "PATCH"])
@token_required
def update_preferences():
    data = request.get_json() or {}
    prefs = _get_or_create_preferences(g.current_user)

    if "work_start_hour" in data:
        prefs.work_start_hour = data["work_start_hour"]
    if "work_end_hour" in data:
        prefs.work_end_hour = data["work_end_hour"]
    if "days_off" in data:
        prefs.days_off = data["days_off"]

    try:
        prefs.save()
    except ValidationError as exc:
        return jsonify({"error": "validation error", "details": str(exc)}), 400

    return jsonify(prefs.to_dict())

