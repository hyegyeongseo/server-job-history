from .models import AuditLog


def create_audit_log(*, user, action, target_type, target_id,
                     description='', changes=None, request=None):
    """
    감사 로그 1 건 기록.

    * 키워드-온리 인자만 받음 — positional 호출 사고 방지.
    * request 가 있으면 IP / User-Agent 자동 추출.
    * changes 는 dict (e.g. {"name": {"old": "a", "new": "b"}}).
    """
    ip_address = None
    user_agent = None

    if request is not None:
        xff = request.META.get('HTTP_X_FORWARDED_FOR')
        if xff:
            ip_address = xff.split(',')[0].strip()
        else:
            ip_address = request.META.get('REMOTE_ADDR')

        user_agent = request.META.get('HTTP_USER_AGENT', '')[:512]

    return AuditLog.objects.create(
        user=user,
        action=action,
        target_type=target_type,
        target_id=target_id,
        description=description,
        changes=changes or {},
        ip_address=ip_address,
        user_agent=user_agent,
    )