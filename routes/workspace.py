from flask import Blueprint, request, jsonify, g
from datetime import datetime

from models.workspace import Workspace, WorkspaceMember, WorkspaceFile
from utils_auth import token_required

workspace_bp = Blueprint('workspace', __name__)


# ─── Helper ───────────────────────────────────────────────────────────────────

def _get_workspace_or_404(workspace_id: str, user_id: str):
    """Ambil workspace dan pastikan user adalah anggota."""
    ws = Workspace.objects(id=workspace_id, is_active=True).first()
    if not ws:
        return None, jsonify({'error': 'Workspace tidak ditemukan'}), 404

    member_ids = [m.user_id for m in ws.members]
    if user_id not in member_ids and ws.owner_id != user_id:
        return None, jsonify({'error': 'Akses ditolak'}), 403

    return ws, None, None


# ─── List Workspace ───────────────────────────────────────────────────────────

@workspace_bp.route('/workspace', methods=['GET'])
@token_required
def list_workspaces():
    """Daftar semua workspace yang dimiliki atau diikuti user."""
    user_id = str(g.current_user.id)

    # Workspace sebagai owner
    owned = Workspace.objects(owner_id=user_id, is_active=True)
    # Workspace sebagai member
    as_member = Workspace.objects(members__user_id=user_id, is_active=True)

    # Gabung dan hilangkan duplikat
    all_ws = {str(ws.id): ws for ws in list(owned) + list(as_member)}

    return jsonify({'workspaces': [ws.to_dict() for ws in all_ws.values()]}), 200


# ─── Buat Workspace ───────────────────────────────────────────────────────────

@workspace_bp.route('/workspace', methods=['POST'])
@token_required
def create_workspace():
    """Buat workspace baru. Owner otomatis jadi member pertama."""
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Nama workspace wajib diisi'}), 400

    user = g.current_user
    user_id = str(user.id)

    owner_member = WorkspaceMember(
        user_id=user_id,
        email=user.email,
        username=user.username,
        role='owner',
    )

    ws = Workspace(
        name=name,
        description=data.get('description', ''),
        owner_id=user_id,
        members=[owner_member],
        google_folder_id=data.get('google_folder_id', ''),
        color=data.get('color', '#7C3AED'),
    )
    ws.save()

    return jsonify({'workspace': ws.to_dict()}), 201


# ─── Detail Workspace ─────────────────────────────────────────────────────────

@workspace_bp.route('/workspace/<workspace_id>', methods=['GET'])
@token_required
def get_workspace(workspace_id):
    user_id = str(g.current_user.id)
    ws, err, code = _get_workspace_or_404(workspace_id, user_id)
    if err:
        return err, code
    return jsonify({'workspace': ws.to_dict()}), 200


# ─── Update Workspace ─────────────────────────────────────────────────────────

@workspace_bp.route('/workspace/<workspace_id>', methods=['PATCH'])
@token_required
def update_workspace(workspace_id):
    user_id = str(g.current_user.id)
    ws, err, code = _get_workspace_or_404(workspace_id, user_id)
    if err:
        return err, code

    # Hanya owner yang boleh update metadata workspace
    if ws.owner_id != user_id:
        return jsonify({'error': 'Hanya owner yang bisa mengubah workspace'}), 403

    data = request.get_json() or {}
    if 'name' in data:
        ws.name = data['name'].strip() or ws.name
    if 'description' in data:
        ws.description = data['description']
    if 'google_folder_id' in data:
        ws.google_folder_id = data['google_folder_id']
    if 'color' in data:
        ws.color = data['color']

    ws.updated_at = datetime.utcnow()
    ws.save()

    return jsonify({'workspace': ws.to_dict()}), 200


# ─── Hapus / Nonaktifkan Workspace ────────────────────────────────────────────

@workspace_bp.route('/workspace/<workspace_id>', methods=['DELETE'])
@token_required
def delete_workspace(workspace_id):
    user_id = str(g.current_user.id)
    ws, err, code = _get_workspace_or_404(workspace_id, user_id)
    if err:
        return err, code

    if ws.owner_id != user_id:
        return jsonify({'error': 'Hanya owner yang bisa menghapus workspace'}), 403

    ws.is_active = False
    ws.save()
    return jsonify({'message': 'Workspace dihapus'}), 200


# ─── File Management ──────────────────────────────────────────────────────────

@workspace_bp.route('/workspace/<workspace_id>/files', methods=['GET'])
@token_required
def list_files(workspace_id):
    user_id = str(g.current_user.id)
    ws, err, code = _get_workspace_or_404(workspace_id, user_id)
    if err:
        return err, code

    files = [
        {
            'file_id': f.file_id,
            'name': f.name,
            'file_type': f.file_type,
            'google_url': f.google_url,
            'created_by': f.created_by,
            'created_at': f.created_at.isoformat() if f.created_at else None,
            'last_modified': f.last_modified.isoformat() if f.last_modified else None,
        }
        for f in ws.files
    ]
    return jsonify({'files': files}), 200


@workspace_bp.route('/workspace/<workspace_id>/files', methods=['POST'])
@token_required
def add_file(workspace_id):
    """Tambah referensi file Google ke workspace."""
    user_id = str(g.current_user.id)
    ws, err, code = _get_workspace_or_404(workspace_id, user_id)
    if err:
        return err, code

    data = request.get_json() or {}
    file_id   = data.get('file_id', '').strip()
    name      = data.get('name', '').strip()
    file_type = data.get('file_type', '').strip()

    if not file_id or not name or not file_type:
        return jsonify({'error': 'file_id, name, dan file_type wajib diisi'}), 400

    if file_type not in ('doc', 'sheet', 'slides'):
        return jsonify({'error': 'file_type harus salah satu: doc, sheet, slides'}), 400

    # Cek duplikat
    existing_ids = [f.file_id for f in ws.files]
    if file_id in existing_ids:
        return jsonify({'error': 'File sudah ada di workspace ini'}), 409

    new_file = WorkspaceFile(
        file_id=file_id,
        name=name,
        file_type=file_type,
        google_url=data.get('google_url', ''),
        created_by=user_id,
    )
    ws.files.append(new_file)
    ws.updated_at = datetime.utcnow()
    ws.save()

    return jsonify({'message': 'File berhasil ditambahkan', 'file': {
        'file_id': new_file.file_id,
        'name': new_file.name,
        'file_type': new_file.file_type,
        'google_url': new_file.google_url,
    }}), 201


@workspace_bp.route('/workspace/<workspace_id>/files/<file_id>', methods=['DELETE'])
@token_required
def remove_file(workspace_id, file_id):
    """Hapus referensi file dari workspace (file Google tidak ikut dihapus)."""
    user_id = str(g.current_user.id)
    ws, err, code = _get_workspace_or_404(workspace_id, user_id)
    if err:
        return err, code

    original_count = len(ws.files)
    ws.files = [f for f in ws.files if f.file_id != file_id]

    if len(ws.files) == original_count:
        return jsonify({'error': 'File tidak ditemukan'}), 404

    ws.updated_at = datetime.utcnow()
    ws.save()
    return jsonify({'message': 'File dihapus dari workspace'}), 200


# ─── Member Management ────────────────────────────────────────────────────────

@workspace_bp.route('/workspace/<workspace_id>/members', methods=['POST'])
@token_required
def invite_member(workspace_id):
    """Undang anggota baru ke workspace."""
    user_id = str(g.current_user.id)
    ws, err, code = _get_workspace_or_404(workspace_id, user_id)
    if err:
        return err, code

    # Hanya owner/editor yang bisa undang
    requester = next((m for m in ws.members if m.user_id == user_id), None)
    if not requester or requester.role not in ('owner', 'editor'):
        return jsonify({'error': 'Tidak punya izin untuk mengundang anggota'}), 403

    data = request.get_json() or {}
    invite_email    = data.get('email', '').strip()
    invite_user_id  = data.get('user_id', '').strip()
    invite_username = data.get('username', '').strip()
    role            = data.get('role', 'editor')

    if not invite_email:
        return jsonify({'error': 'Email anggota wajib diisi'}), 400

    # Cek duplikat
    existing_emails = [m.email for m in ws.members]
    if invite_email in existing_emails:
        return jsonify({'error': 'User sudah menjadi anggota'}), 409

    new_member = WorkspaceMember(
        user_id=invite_user_id or invite_email,
        email=invite_email,
        username=invite_username,
        role=role,
    )
    ws.members.append(new_member)
    ws.updated_at = datetime.utcnow()
    ws.save()

    return jsonify({'message': f'{invite_email} berhasil diundang'}), 201



@workspace_bp.route('/workspace/<workspace_id>/members/<member_user_id>', methods=['DELETE'])
@token_required
def remove_member(workspace_id, member_user_id):
    """Keluarkan anggota dari workspace."""
    user_id = str(g.current_user.id)
    ws, err, code = _get_workspace_or_404(workspace_id, user_id)
    if err:
        return err, code

    if ws.owner_id != user_id:
        return jsonify({'error': 'Hanya owner yang bisa mengeluarkan anggota'}), 403

    if member_user_id == ws.owner_id:
        return jsonify({'error': 'Owner tidak bisa dikeluarkan'}), 400

    original_count = len(ws.members)
    ws.members = [m for m in ws.members if m.user_id != member_user_id]

    if len(ws.members) == original_count:
        return jsonify({'error': 'Anggota tidak ditemukan'}), 404

    ws.updated_at = datetime.utcnow()
    ws.save()
    return jsonify({'message': 'Anggota berhasil dikeluarkan'}), 200
