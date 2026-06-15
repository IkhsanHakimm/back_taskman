from flask import Blueprint, request, jsonify, g
from datetime import datetime

from models.task_group import TaskGroup, TaskGroupMember, GroupInvitation
from models.workspace import Workspace, WorkspaceMember
from models.user import User
from utils_auth import token_required

task_group_bp = Blueprint('task_group', __name__)


def _get_group_or_404(group_id: str, user_id: str):
    """Ambil group dan pastikan user adalah anggota."""
    grp = TaskGroup.objects(id=group_id, is_active=True).first()
    if not grp:
        return None, jsonify({'error': 'Grup tidak ditemukan'}), 404

    member_ids = [m.user_id for m in grp.members]
    if user_id not in member_ids and grp.owner_id != user_id:
        return None, jsonify({'error': 'Akses ditolak'}), 403

    return grp, None, None

# ─── Grup (CRUD) ─────────────────────────────────────────────────────────────

@task_group_bp.route('/task-groups', methods=['GET'])
@token_required
def list_groups():
    user_id = str(g.current_user.id)
    
    owned = TaskGroup.objects(owner_id=user_id, is_active=True)
    as_member = TaskGroup.objects(members__user_id=user_id, is_active=True)
    
    all_grp = {str(grp.id): grp for grp in list(owned) + list(as_member)}
    
    return jsonify({'groups': [grp.to_dict() for grp in all_grp.values()]}), 200

@task_group_bp.route('/task-groups', methods=['POST'])
@token_required
def create_group():
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Nama grup wajib diisi'}), 400

    user = g.current_user
    user_id = str(user.id)

    owner_member = TaskGroupMember(
        user_id=user_id,
        email=user.email,
        username=user.username,
        role='owner',
    )

    # Otomatis buatkan Workspace untuk Grup ini
    ws_owner_member = WorkspaceMember(
        user_id=user_id,
        email=user.email,
        username=user.username,
        role='owner',
    )
    ws = Workspace(
        name=f"Workspace - {name}",
        description=f"Workspace otomatis untuk grup {name}",
        owner_id=user_id,
        members=[ws_owner_member]
    )
    ws.save()

    grp = TaskGroup(
        name=name,
        description=data.get('description', ''),
        owner_id=user_id,
        members=[owner_member],
        workspace_id=str(ws.id),
        color=data.get('color', '#0891B2'),
    )
    grp.save()

    # Kirim undangan jika ada
    invites = data.get('invites', [])
    for email in invites:
        email = email.strip()
        if email and email != user.email:
            # Cek agar tidak ganda
            existing_invite = GroupInvitation.objects(group_id=str(grp.id), receiver_email=email, status='pending').first()
            if not existing_invite:
                inv = GroupInvitation(
                    group_id=str(grp.id),
                    group_name=grp.name,
                    sender_id=user_id,
                    sender_name=user.username or user.email,
                    receiver_email=email,
                    role='member'
                )
                inv.save()

    return jsonify({'group': grp.to_dict(), 'message': 'Grup berhasil dibuat'}), 201

# ─── Undangan Grup (Invitations) ─────────────────────────────────────────────

@task_group_bp.route('/task-groups/<group_id>/invite', methods=['POST'])
@token_required
def invite_to_group(group_id):
    user_id = str(g.current_user.id)
    grp, err, code = _get_group_or_404(group_id, user_id)
    if err:
        return err, code

    data = request.get_json() or {}
    invite_email = data.get('email', '').strip()
    role = data.get('role', 'member')

    if not invite_email:
        return jsonify({'error': 'Email wajib diisi'}), 400

    existing_emails = [m.email for m in grp.members]
    if invite_email in existing_emails:
        return jsonify({'error': 'User sudah ada di grup'}), 409

    existing_invite = GroupInvitation.objects(group_id=group_id, receiver_email=invite_email, status='pending').first()
    if existing_invite:
        return jsonify({'error': 'Undangan sudah dikirim sebelumnya dan masih pending'}), 409

    inv = GroupInvitation(
        group_id=group_id,
        group_name=grp.name,
        sender_id=user_id,
        sender_name=g.current_user.username or g.current_user.email,
        receiver_email=invite_email,
        role=role
    )
    inv.save()
    return jsonify({'message': f'Undangan berhasil dikirim ke {invite_email}', 'invitation': inv.to_dict()}), 201


@task_group_bp.route('/task-groups/invitations', methods=['GET'])
@token_required
def list_group_invitations():
    email = g.current_user.email
    invitations = GroupInvitation.objects(receiver_email=email, status='pending')
    return jsonify({'invitations': [inv.to_dict() for inv in invitations]}), 200


@task_group_bp.route('/task-groups/invitations/<invitation_id>/respond', methods=['POST'])
@token_required
def respond_group_invitation(invitation_id):
    data = request.get_json() or {}
    response = data.get('response', '').lower()
    
    if response not in ('accept', 'reject'):
        return jsonify({'error': 'Response harus accept atau reject'}), 400

    invitation = GroupInvitation.objects(id=invitation_id).first()
    if not invitation:
        return jsonify({'error': 'Undangan tidak ditemukan'}), 404

    if invitation.receiver_email != g.current_user.email:
        return jsonify({'error': 'Akses ditolak'}), 403

    if invitation.status != 'pending':
        return jsonify({'error': f'Undangan ini sudah di-{invitation.status}'}), 400

    if response == 'reject':
        invitation.status = 'rejected'
        invitation.save()
        return jsonify({'message': 'Undangan ditolak'}), 200

    # Accept
    grp = TaskGroup.objects(id=invitation.group_id, is_active=True).first()
    if not grp:
        invitation.status = 'rejected'
        invitation.save()
        return jsonify({'error': 'Grup sudah tidak ada'}), 404

    # Tambah user ke Grup
    existing_emails = [m.email for m in grp.members]
    if g.current_user.email not in existing_emails:
        new_grp_member = TaskGroupMember(
            user_id=str(g.current_user.id),
            email=g.current_user.email,
            username=g.current_user.username,
            role=invitation.role
        )
        grp.members.append(new_grp_member)
        grp.updated_at = datetime.utcnow()
        grp.save()

        # Tambahkan ke Workspace milik grup tersebut otomatis
        if grp.workspace_id:
            ws = Workspace.objects(id=grp.workspace_id, is_active=True).first()
            if ws:
                ws_member = WorkspaceMember(
                    user_id=str(g.current_user.id),
                    email=g.current_user.email,
                    username=g.current_user.username,
                    role='editor'  # Di workspace grup, member biasa punya akses edit
                )
                ws.members.append(ws_member)
                ws.updated_at = datetime.utcnow()
                ws.save()

    invitation.status = 'accepted'
    invitation.save()

    return jsonify({'message': 'Berhasil bergabung dengan grup', 'group': grp.to_dict()}), 200
