from datetime import datetime

from extensions import db
from models.user import User


# ─── Embedded documents untuk AI Breakdown ───────────────────────────────────

class AIBreakdownStep(db.EmbeddedDocument):
    """Satu langkah dalam roadmap pengerjaan task dari Mistral."""
    title = db.StringField(required=True)
    description = db.StringField()
    estimasi = db.StringField()       # contoh: "1–2 jam"
    iconName = db.StringField()       # nama icon Flutter, contoh: "architecture"

    def to_dict(self):
        return {
            "title": self.title,
            "description": self.description,
            "estimasi": self.estimasi,
            "iconName": self.iconName,
        }


class AIBreakdown(db.EmbeddedDocument):
    """Hasil lengkap AI Breakdown dari Mistral untuk sebuah task."""
    summary = db.StringField()
    estimasiTotal = db.StringField()         # contoh: "6–10 jam"
    tingkatKesulitan = db.StringField()      # "Rendah" | "Sedang" | "Tinggi"
    steps = db.EmbeddedDocumentListField(AIBreakdownStep)
    tips = db.ListField(db.StringField())
    resources = db.ListField(db.StringField())

    def to_dict(self):
        return {
            "summary": self.summary,
            "estimasiTotal": self.estimasiTotal,
            "tingkatKesulitan": self.tingkatKesulitan,
            "steps": [s.to_dict() for s in self.steps],
            "tips": list(self.tips),
            "resources": list(self.resources),
        }


# ─── Model utama Task ─────────────────────────────────────────────────────────

class Task(db.Document):
    owner = db.ReferenceField(User, required=True, reverse_delete_rule=db.CASCADE)
    title = db.StringField(required=True, max_length=255)
    description = db.StringField()
    estimated_duration_minutes = db.IntField(min_value=0)  # perkiraan durasi pengerjaan
    due_datetime = db.DateTimeField()  # deadline tugas
    priority = db.StringField(choices=("low", "medium", "high"), default="medium")
    category = db.StringField()  # misal: kuliah, kerja, pribadi
    status = db.StringField(
        choices=("pending", "in_progress", "done", "cancelled"),
        default="pending",
    )
    # Hasil AI breakdown dari Mistral (None jika belum di-generate)
    ai_breakdown = db.EmbeddedDocumentField(AIBreakdown, default=None)
    created_at = db.DateTimeField(default=datetime.utcnow)
    updated_at = db.DateTimeField(default=datetime.utcnow)

    meta = {
        "collection": "tasks",
        "indexes": [
            "owner",
            "status",
            "due_datetime",
        ],
    }

    def save(self, *args, **kwargs):
        self.updated_at = datetime.utcnow()
        return super().save(*args, **kwargs)

    def to_dict(self):
        return {
            "id": str(self.id),
            "owner_id": str(self.owner.id) if self.owner else None,
            "title": self.title,
            "description": self.description,
            "estimated_duration_minutes": self.estimated_duration_minutes,
            "due_datetime": self.due_datetime.isoformat() if self.due_datetime else None,
            "priority": self.priority,
            "category": self.category,
            "status": self.status,
            "ai_breakdown": self.ai_breakdown.to_dict() if self.ai_breakdown else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }



class TaskSchedule(db.Document):
    owner = db.ReferenceField(User, required=True, reverse_delete_rule=db.CASCADE)
    task = db.ReferenceField(Task, required=True, reverse_delete_rule=db.CASCADE)
    start_datetime = db.DateTimeField(required=True)
    end_datetime = db.DateTimeField(required=True)
    source = db.StringField(
        choices=("manual", "rule_based", "model"),
        default="rule_based",
    )

    meta = {
        "collection": "task_schedules",
        "indexes": [
            "owner",
            "task",
            "start_datetime",
            "end_datetime",
        ],
    }

    def to_dict(self):
        return {
            "id": str(self.id),
            "owner_id": str(self.owner.id) if self.owner else None,
            "task_id": str(self.task.id) if self.task else None,
            "start_datetime": self.start_datetime.isoformat()
            if self.start_datetime
            else None,
            "end_datetime": self.end_datetime.isoformat()
            if self.end_datetime
            else None,
            "source": self.source,
        }


class ActivityLog(db.Document):
    owner = db.ReferenceField(User, required=True, reverse_delete_rule=db.CASCADE)
    task = db.ReferenceField(Task, required=False, reverse_delete_rule=db.NULLIFY)
    activity_type = db.StringField(
        required=True,
        choices=(
            "task_created",
            "task_updated",
            "task_started",
            "task_completed",
            "task_deleted",
            "schedule_created",
            "schedule_updated",
        ),
    )
    timestamp = db.DateTimeField(default=datetime.utcnow)
    metadata = db.DictField()  # tempat menyimpan info tambahan (durasi real, dsb)

    meta = {
        "collection": "activity_logs",
        "indexes": [
            "owner",
            "task",
            "-timestamp",
            "activity_type",
        ],
    }

    def to_dict(self):
        return {
            "id": str(self.id),
            "owner_id": str(self.owner.id) if self.owner else None,
            "task_id": str(self.task.id) if self.task else None,
            "activity_type": self.activity_type,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "metadata": self.metadata or {},
        }

