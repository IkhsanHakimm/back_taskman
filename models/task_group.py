from mongoengine import (
    Document, EmbeddedDocument,
    StringField, ListField, EmbeddedDocumentField,
    DateTimeField, BooleanField
)
from datetime import datetime

class TaskGroupMember(EmbeddedDocument):
    user_id   = StringField(required=True)
    email     = StringField(required=True)
    username  = StringField(default='')
    role      = StringField(default='member', choices=['owner', 'admin', 'member'])
    joined_at = DateTimeField(default=datetime.utcnow)

class TaskGroup(Document):
    """
    Model wadah utama kolaborasi: Task Group.
    Setiap grup memiliki member dan 1 workspace terikat.
    """
    meta = {'collection': 'task_groups'}

    name             = StringField(required=True, max_length=100)
    description      = StringField(default='')
    owner_id         = StringField(required=True)
    members          = ListField(EmbeddedDocumentField(TaskGroupMember))
    workspace_id     = StringField(default='')  # ID dari koleksi Workspace
    color            = StringField(default='#0891B2')
    is_active        = BooleanField(default=True)
    created_at       = DateTimeField(default=datetime.utcnow)
    updated_at       = DateTimeField(default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': str(self.id),
            'name': self.name,
            'description': self.description,
            'owner_id': self.owner_id,
            'workspace_id': self.workspace_id,
            'color': self.color,
            'members': [
                {
                    'user_id': m.user_id,
                    'email': m.email,
                    'username': m.username,
                    'role': m.role,
                    'joined_at': m.joined_at.isoformat() if m.joined_at else None,
                }
                for m in self.members
            ],
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

class GroupInvitation(Document):
    """
    Model untuk melacak undangan masuk ke sebuah Task Group.
    """
    meta = {'collection': 'user_group_task'}

    group_id         = StringField(required=True)
    group_name       = StringField(required=True)
    sender_id        = StringField(required=True)
    sender_name      = StringField(default='')
    receiver_email   = StringField(required=True)
    role             = StringField(default='member', choices=['owner', 'admin', 'member'])
    status           = StringField(default='pending', choices=['pending', 'accepted', 'rejected'])
    created_at       = DateTimeField(default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': str(self.id),
            'group_id': self.group_id,
            'group_name': self.group_name,
            'sender_id': self.sender_id,
            'sender_name': self.sender_name,
            'receiver_email': self.receiver_email,
            'role': self.role,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
