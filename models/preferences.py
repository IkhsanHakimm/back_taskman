from extensions import db
from models.user import User


class UserPreference(db.Document):
    owner = db.ReferenceField(User, required=True, unique=True, reverse_delete_rule=db.CASCADE)
    work_start_hour = db.IntField(min_value=0, max_value=23, default=8)
    work_end_hour = db.IntField(min_value=0, max_value=23, default=21)
    days_off = db.ListField(db.IntField(min_value=0, max_value=6), default=list)  # 0=Senin, 6=Minggu

    meta = {
        "collection": "user_preferences",
        "indexes": ["owner"],
    }

    def to_dict(self):
        return {
            "owner_id": str(self.owner.id) if self.owner else None,
            "work_start_hour": self.work_start_hour,
            "work_end_hour": self.work_end_hour,
            "days_off": self.days_off,
        }

