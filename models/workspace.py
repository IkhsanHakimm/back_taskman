from mongoengine import (
    Document, EmbeddedDocument,
    StringField, ListField, EmbeddedDocumentField,
    DateTimeField, BooleanField, ReferenceField
)
from datetime import datetime


class WorkspaceMember(EmbeddedDocument):
    """Anggota workspace dengan role tertentu."""
    user_id   = StringField(required=True)   # ObjectId user sebagai string
    email     = StringField(required=True)
    username  = StringField(default='')
    role      = StringField(default='member', choices=['owner', 'editor', 'viewer'])
    joined_at = DateTimeField(default=datetime.utcnow)


class WorkspaceFile(EmbeddedDocument):
    """Referensi ke file Google (Docs/Sheets/Slides) yang terhubung ke workspace."""
    file_id       = StringField(required=True)   # Google Drive file ID
    name          = StringField(required=True)
    file_type     = StringField(
        required=True,
        choices=['doc', 'sheet', 'slides']
    )
    google_url    = StringField(default='')      # webViewLink dari Drive
    created_by    = StringField(required=True)   # user_id
    created_at    = DateTimeField(default=datetime.utcnow)
    last_modified = DateTimeField(default=datetime.utcnow)


class Workspace(Document):
    """
    Model workspace kolaboratif.
    Setiap workspace punya folder Google Drive sendiri,
    dan bisa berisi banyak file Google.
    """
    meta = {'collection': 'workspaces'}

    name             = StringField(required=True, max_length=100)
    description      = StringField(default='')
    owner_id         = StringField(required=True)   # user_id pemilik
    members          = ListField(EmbeddedDocumentField(WorkspaceMember))
    files            = ListField(EmbeddedDocumentField(WorkspaceFile))
    google_folder_id = StringField(default='')      # ID folder di Google Drive
    color            = StringField(default='#7C3AED')  # warna UI
    is_active        = BooleanField(default=True)
    created_at       = DateTimeField(default=datetime.utcnow)
    updated_at       = DateTimeField(default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': str(self.id),
            'name': self.name,
            'description': self.description,
            'owner_id': self.owner_id,
            'google_folder_id': self.google_folder_id,
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
            'files': [
                {
                    'file_id': f.file_id,
                    'name': f.name,
                    'file_type': f.file_type,
                    'google_url': f.google_url,
                    'created_by': f.created_by,
                    'created_at': f.created_at.isoformat() if f.created_at else None,
                    'last_modified': f.last_modified.isoformat() if f.last_modified else None,
                }
                for f in self.files
            ],
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

