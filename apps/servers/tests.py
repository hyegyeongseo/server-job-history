"""
Server 도메인 RBAC 테스트.

서버 쪽 admin/operator 구분은 다음 지점에서 드러난다.
    - 생성/수정/삭제(soft) : OPERATOR, ADMIN
    - 복구(restore)        : ADMIN 전용
"""
from rest_framework import status
from rest_framework.test import APITestCase
from django.urls import reverse

from apps.core.models import User
from apps.servers.models import Server


def make_user(username, role):
    return User.objects.create_user(
        username=username, password="pw12345!", role=role
    )


class ServerRBACTest(APITestCase):
    def setUp(self):
        self.admin = make_user("admin", User.Role.ADMIN)
        self.operator = make_user("operator", User.Role.OPERATOR)
        self.viewer = make_user("viewer", User.Role.VIEWER)
        self.list_url = reverse("servers-list")

    def _payload(self, **overrides):
        p = {"name": "db-1", "ip_address": "10.0.0.9", "environment": "dev"}
        p.update(overrides)
        return p

    def test_viewer_cannot_create_server(self):
        self.client.force_authenticate(user=self.viewer)
        res = self.client.post(self.list_url, self._payload(), format="json")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_operator_can_create_server(self):
        self.client.force_authenticate(user=self.operator)
        res = self.client.post(self.list_url, self._payload(), format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

    def test_operator_can_soft_delete_but_not_restore(self):
        server = Server.objects.create(
            name="cache-1", ip_address="10.0.0.10", environment="stg"
        )
        detail_url = reverse("servers-detail", args=[server.id])
        restore_url = reverse("servers-restore", args=[server.id])

        # operator soft-delete OK
        self.client.force_authenticate(user=self.operator)
        del_res = self.client.delete(detail_url)
        self.assertEqual(del_res.status_code, status.HTTP_204_NO_CONTENT)
        server.refresh_from_db()
        self.assertTrue(server.is_deleted)

        # operator restore 시도 → 404
        # 삭제된 서버는 operator의 queryset(is_deleted=False)에 안 보이므로
        # get_object()에서 404가 난다. 결과적으로 복구가 차단되며,
        # 삭제 서버 조회/복구는 ADMIN 전용임을 보여준다.
        res = self.client.patch(restore_url)
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_admin_can_restore(self):
        server = Server.objects.create(
            name="cache-2", ip_address="10.0.0.11", environment="stg",
            is_deleted=True,
        )
        restore_url = reverse("servers-restore", args=[server.id])

        self.client.force_authenticate(user=self.admin)
        res = self.client.patch(restore_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        server.refresh_from_db()
        self.assertFalse(server.is_deleted)