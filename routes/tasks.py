from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request, g
from mongoengine.errors import ValidationError, DoesNotExist

from models.task import Task, TaskSchedule, ActivityLog, AIBreakdown, AIBreakdownStep
from services.mistral_service import generate_task_breakdown
from utils_auth import token_required


tasks_bp = Blueprint("tasks", __name__, url_prefix="/tasks")


def _log_activity(owner, task, activity_type: str, metadata: dict | None = None):
    ActivityLog(
        owner=owner,
        task=task,
        activity_type=activity_type,
        metadata=metadata or {},
    ).save()


@tasks_bp.route("", methods=["POST"])
@token_required
def create_task():
    data = request.get_json() or {}

    title = data.get("title")
    if not title:
        return jsonify({"error": "title is required"}), 400

    try:
        due_datetime = (
            datetime.fromisoformat(data["due_datetime"])
            if data.get("due_datetime")
            else None
        )
    except ValueError:
        return jsonify({"error": "invalid due_datetime format, use ISO 8601"}), 400

    task = Task(
        owner=g.current_user,
        title=title,
        description=data.get("description"),
        estimated_duration_minutes=data.get("estimated_duration_minutes"),
        due_datetime=due_datetime,
        priority=data.get("priority") or "medium",
        category=data.get("category"),
    )

    try:
        task.save()
    except ValidationError as exc:
        return jsonify({"error": "validation error", "details": str(exc)}), 400

    _log_activity(g.current_user, task, "task_created")
    return jsonify(task.to_dict()), 201


@tasks_bp.route("", methods=["GET"])
@token_required
def list_tasks():
    status = request.args.get("status")
    query = Task.objects(owner=g.current_user)
    if status:
        query = query.filter(status=status)

    tasks = [task.to_dict() for task in query.order_by("-created_at")]
    return jsonify(tasks)


@tasks_bp.route("/<task_id>", methods=["GET"])
@token_required
def get_task(task_id: str):
    try:
        task = Task.objects.get(id=task_id, owner=g.current_user)
    except DoesNotExist:
        return jsonify({"error": "task not found"}), 404

    return jsonify(task.to_dict())


@tasks_bp.route("/<task_id>", methods=["PATCH", "PUT"])
@token_required
def update_task(task_id: str):
    data = request.get_json() or {}

    try:
        task = Task.objects.get(id=task_id, owner=g.current_user)
    except DoesNotExist:
        return jsonify({"error": "task not found"}), 404

    if "title" in data:
        task.title = data["title"]
    if "description" in data:
        task.description = data["description"]
    if "estimated_duration_minutes" in data:
        task.estimated_duration_minutes = data["estimated_duration_minutes"]
    if "due_datetime" in data:
        try:
            task.due_datetime = (
                datetime.fromisoformat(data["due_datetime"])
                if data["due_datetime"]
                else None
            )
        except ValueError:
            return jsonify({"error": "invalid due_datetime format, use ISO 8601"}), 400
    if "priority" in data:
        task.priority = data["priority"]
    if "category" in data:
        task.category = data["category"]
    if "status" in data:
        task.status = data["status"]

    try:
        task.save()
    except ValidationError as exc:
        return jsonify({"error": "validation error", "details": str(exc)}), 400

    _log_activity(g.current_user, task, "task_updated")
    return jsonify(task.to_dict())


@tasks_bp.route("/<task_id>", methods=["DELETE"])
@token_required
def delete_task(task_id: str):
    try:
        task = Task.objects.get(id=task_id, owner=g.current_user)
    except DoesNotExist:
        return jsonify({"error": "task not found"}), 404

    task.delete()
    _log_activity(g.current_user, None, "task_deleted", {"task_id": task_id})
    return jsonify({"message": "task deleted"})


@tasks_bp.route("/<task_id>/start", methods=["POST"])
@token_required
def start_task(task_id: str):
    try:
        task = Task.objects.get(id=task_id, owner=g.current_user)
    except DoesNotExist:
        return jsonify({"error": "task not found"}), 404

    task.status = "in_progress"
    task.save()

    _log_activity(g.current_user, task, "task_started")
    return jsonify(task.to_dict())


@tasks_bp.route("/<task_id>/complete", methods=["POST"])
@token_required
def complete_task(task_id: str):
    data = request.get_json() or {}
    actual_duration_minutes = data.get("actual_duration_minutes")

    try:
        task = Task.objects.get(id=task_id, owner=g.current_user)
    except DoesNotExist:
        return jsonify({"error": "task not found"}), 404

    task.status = "done"
    task.save()

    _log_activity(
        g.current_user,
        task,
        "task_completed",
        {"actual_duration_minutes": actual_duration_minutes},
    )
    return jsonify(task.to_dict())


@tasks_bp.route("/schedule", methods=["GET"])
@token_required
def list_schedule():
    """List jadwal pengerjaan tugas user (bisa difilter tanggal)."""
    date_str = request.args.get("date")
    query = TaskSchedule.objects(owner=g.current_user)

    if date_str:
        try:
            target_date = datetime.fromisoformat(date_str).date()
        except ValueError:
            return jsonify({"error": "invalid date format, use ISO 8601"}), 400

        start = datetime.combine(target_date, datetime.min.time())
        end = datetime.combine(target_date, datetime.max.time())
        query = query.filter(start_datetime__gte=start, start_datetime__lte=end)

    schedules = [sched.to_dict() for sched in query.order_by("start_datetime")]
    return jsonify(schedules)


@tasks_bp.route("/<task_id>/schedule", methods=["POST"])
@token_required
def create_simple_schedule(task_id: str):
    """
    Buat jadwal sederhana (rule-based, tanpa AI) untuk sebuah task.

    Strategi sementara:
    - Jika ada due_datetime dan estimated_duration_minutes:
        jadwalkan di hari yang sama sebelum deadline (1 jam sebelum due).
    - Kalau tidak ada, jadwalkan 1 jam dari sekarang dengan durasi default 60 menit.
    """
    try:
        task = Task.objects.get(id=task_id, owner=g.current_user)
    except DoesNotExist:
        return jsonify({"error": "task not found"}), 404

    now = datetime.utcnow()
    duration = task.estimated_duration_minutes or 60

    if task.due_datetime:
        end = task.due_datetime - timedelta(minutes=60)
        start = end - timedelta(minutes=duration)
        if start < now:
            start = now + timedelta(minutes=5)
            end = start + timedelta(minutes=duration)
    else:
        start = now + timedelta(minutes=5)
        end = start + timedelta(minutes=duration)

    schedule = TaskSchedule(
        owner=g.current_user,
        task=task,
        start_datetime=start,
        end_datetime=end,
        source="rule_based",
    )
    try:
        schedule.save()
    except ValidationError as exc:
        return jsonify({"error": "validation error", "details": str(exc)}), 400

    _log_activity(g.current_user, task, "schedule_created", schedule.to_dict())
    return jsonify(schedule.to_dict()), 201

@tasks_bp.route("/<task_id>/generate-breakdown", methods=["POST"])
@token_required
def generate_breakdown(task_id: str):
    """
    Generate AI Breakdown untuk sebuah task menggunakan Mistral LLM.

    Jika breakdown sudah ada di database, langsung kembalikan (cache).
    Jika belum, panggil Mistral, simpan hasilnya, lalu kembalikan.

    Query param:
        refresh=true  => paksa generate ulang meskipun sudah ada
    """
    try:
        task = Task.objects.get(id=task_id, owner=g.current_user)
    except DoesNotExist:
        return jsonify({"error": "task not found"}), 404

    force_refresh = request.args.get("refresh", "").lower() == "true"

    # Kembalikan cached breakdown jika sudah ada dan tidak dipaksa refresh
    if task.ai_breakdown and not force_refresh:
        return jsonify(task.ai_breakdown.to_dict())

    # Panggil Mistral untuk generate breakdown
    try:
        breakdown_data = generate_task_breakdown(
            task_title=task.title,
            task_description=task.description,
        )
    except RuntimeError as exc:
        return jsonify({"error": "Gagal generate AI breakdown", "details": str(exc)}), 502

    # Bangun embedded document dari dict hasil Mistral
    steps = [
        AIBreakdownStep(
            title=s["title"],
            description=s.get("description", ""),
            estimasi=s.get("estimasi", ""),
            iconName=s.get("iconName", "task_alt"),
        )
        for s in breakdown_data.get("steps", [])
    ]

    task.ai_breakdown = AIBreakdown(
        summary=breakdown_data.get("summary", ""),
        estimasiTotal=breakdown_data.get("estimasiTotal", ""),
        tingkatKesulitan=breakdown_data.get("tingkatKesulitan", "Sedang"),
        steps=steps,
        tips=breakdown_data.get("tips", []),
        resources=breakdown_data.get("resources", []),
    )

    try:
        task.save()
    except ValidationError as exc:
        return jsonify({"error": "Gagal menyimpan breakdown", "details": str(exc)}), 400

    _log_activity(g.current_user, task, "task_updated", {"action": "ai_breakdown_generated"})
    return jsonify(task.ai_breakdown.to_dict()), 200
