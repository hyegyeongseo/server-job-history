"""
감사 로그 테스트.

두 가지 측면을 검증한다.
1. 기록(write): 서버/작업 생성이 AuditLog를 부수 효과로 남기는지,
   그리고 요청 메타(IP)가 X-Forwarded-For에서 올바로 추출되는지.
2. 조회(read) RBAC: admin은 전체, operator는 본인 기록만, viewer는 차단.
"""
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.core.models import User
from apps.servers.models import Server
from apps.audit.models import AuditLog

AUDIT_URL = "/api/audit-logs/"


def make_user(username, role):
    return User.objects.create_user(
        username=username, password="pw12345!", role=role
    )


class AuditLogWriteTest(APITestCase):
    def setUp(self):
        self.operator = make_user("operator", User.Role.OPERATOR)
        self.servers_url = reverse("servers-list")

    def test_server_create_writes_audit_log(self):
        self.client.force_authenticate(user=self.operator)
        res = self.client.post(
            self.servers_url,
            {"name": "web-1", "ip_address": "10.0.0.1", "environment": "dev"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        log = AuditLog.objects.get()  # 정확히 1건
        self.assertEqual(log.action, "create")
        self.assertEqual(log.target_type, "servers")
        self.assertEqual(log.target_id, res.data["id"])
        self.assertEqual(log.user_id, self.operator.id)

    def test_audit_log_records_forwarded_ip(self):
        """프록시/인그레스 뒤에서 X-Forwarded-For의 첫 IP를 기록해야 한다."""
        self.client.force_authenticate(user=self.operator)
        self.client.post(
            self.servers_url,
            {"name": "web-2", "ip_address": "10.0.0.2", "environment": "dev"},
            format="json",
            HTTP_X_FORWARDED_FOR="203.0.113.7, 10.0.0.254",
        )
        log = AuditLog.objects.get()
        self.assertEqual(log.ip_address, "203.0.113.7")


class AuditLogReadRBACTest(APITestCase):
    def setUp(self):
        self.admin = make_user("admin", User.Role.ADMIN)
        self.op1 = make_user("op1", User.Role.OPERATOR)
        self.op2 = make_user("op2", User.Role.OPERATOR)
        self.viewer = make_user("viewer", User.Role.VIEWER)

        # op1, op2가 각각 서버를 만들어 본인 명의의 감사 로그를 1건씩 생성
        self.servers_url = reverse("servers-list")
        self._create_server_as(self.op1, "srv-a", "10.0.0.11")
        self._create_server_as(self.op2, "srv-b", "10.0.0.12")

    def _create_server_as(self, user, name, ip):
        self.client.force_authenticate(user=user)
        self.client.post(
            self.servers_url,
            {"name": name, "ip_address": ip, "environment": "dev"},
            format="json",
        )
        self.client.force_authenticate(user=None)

    def test_admin_sees_all_logs(self):
        self.client.force_authenticate(user=self.admin)
        res = self.client.get(AUDIT_URL)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["count"], 2)

    def test_operator_sees_only_own_logs(self):
        self.client.force_authenticate(user=self.op1)
        res = self.client.get(AUDIT_URL)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["count"], 1)
        self.assertEqual(res.data["results"][0]["username"], "op1")

    def test_viewer_is_forbidden(self):
        self.client.force_authenticate(user=self.viewer)
        res = self.client.get(AUDIT_URL)
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)