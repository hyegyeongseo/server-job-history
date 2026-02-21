from .models import AuditLog

def create_audit_log(user, action, target_type, target_id, description=None):
    AuditLog.objects.create(
        user=user,
        action=action,
        target_type=target_type,
        target_id=target_id,
        description=description
    )