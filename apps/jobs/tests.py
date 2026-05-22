"""
Job 도메인 테스트.

커버 범위
---------
1. RBAC
   - VIEWER: 조회만, 생성/수정 불가
   - OPERATOR: 생성 가능, '본인' 작업만 수정 가능
   - ADMIN: 남의 작업도 수정 가능
   - DELETE: ViewSet에서 비활성화(405)
2. 작업 체인 (root_job / previous_job / chain 엔드포인트)
3. 30분 편집 윈도우 (정정 작업 모델)
"""
from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.core.models import User
from apps.servers.models import Server
from apps.jobs.models import Job


def make_user(username, role):
    return User.objects.create_user(
        username=username, password="pw12345!", role=role
    )


class JobTestBase(APITestCase):
    def setUp(self):
        self.server = Server.objects.create(
            name="web-1", ip_address="10.0.0.1", environment="dev"
        )
        self.admin = make_user("admin", User.Role.ADMIN)
        self.op1 = make_user("op1", User.Role.OPERATOR)
        self.op2 = make_user("op2", User.Role.OPERATOR)
        self.viewer = make_user("viewer", User.Role.VIEWER)

        self.list_url = reverse("job-list")

    def _create_payload(self, **overrides):
        payload = {
            "server": self.server.id,
            "action_type": "backup",
            "description": "nightly backup",
        }
        payload.update(overrides)
        return payload

    def _make_job(self, owner, **overrides):
        """ORM으로 직접 Job 생성 (소유자 지정 + root_job 자기참조)."""
        job = Job.objects.create(
            server=self.server,
            action_type=overrides.pop("action_type", "backup"),
            description=overrides.pop("description", "desc"),
            created_by=owner,
            **overrides,
        )
        if job.root_job_id is None:
            job.root_job = job
            job.save(update_fields=["root_job"])
        return job


class JobRBACTest(JobTestBase):
    def test_viewer_can_read_but_not_create(self):
        self.client.force_authenticate(user=self.viewer)

        # 조회 OK
        self.assertEqual(self.client.get(self.list_url).status_code, status.HTTP_200_OK)

        # 생성 거부
        res = self.client.post(self.list_url, self._create_payload(), format="json")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_operator_can_create_and_owns_job(self):
        self.client.force_authenticate(user=self.op1)
        res = self.client.post(self.list_url, self._create_payload(), format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        job = Job.objects.get(pk=res.data["id"])
        self.assertEqual(job.created_by_id, self.op1.id)
        # 신규 root → root_job이 자기 자신
        self.assertEqual(job.root_job_id, job.id)

    def test_operator_can_edit_own_job(self):
        job = self._make_job(self.op1)
        self.client.force_authenticate(user=self.op1)
        url = reverse("job-detail", args=[job.id])

        res = self.client.patch(url, {"status": "running"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        job.refresh_from_db()
        self.assertEqual(job.status, "running")

    def test_operator_cannot_edit_others_job(self):
        job = self._make_job(self.op1)  # op1 소유
        self.client.force_authenticate(user=self.op2)  # op2가 시도
        url = reverse("job-detail", args=[job.id])

        res = self.client.patch(url, {"status": "running"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_edit_others_job(self):
        job = self._make_job(self.op1)  # op1 소유
        self.client.force_authenticate(user=self.admin)
        url = reverse("job-detail", args=[job.id])

        res = self.client.patch(url, {"status": "completed"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        job.refresh_from_db()
        self.assertEqual(job.status, "completed")

    def test_delete_is_disabled(self):
        """
        DELETE는 두 겹으로 막힌다.
        - 비관리자: 권한 게이트(JobPermission)에서 먼저 막혀 403.
        - 관리자: 권한은 통과하지만 ViewSet이 DELETE 메서드 자체를
          비활성화(http_method_names)했으므로 405.
        DRF는 핸들러 해석보다 권한 검사를 먼저 하기 때문에 이 순서가 나온다.
        """
        job = self._make_job(self.op1)
        url = reverse("job-detail", args=[job.id])

        self.client.force_authenticate(user=self.op1)
        self.assertEqual(
            self.client.delete(url).status_code, status.HTTP_403_FORBIDDEN
        )

        self.client.force_authenticate(user=self.admin)
        self.assertEqual(
            self.client.delete(url).status_code, status.HTTP_405_METHOD_NOT_ALLOWED
        )


class JobChainTest(JobTestBase):
    def test_correction_inherits_root_job(self):
        self.client.force_authenticate(user=self.op1)

        root_res = self.client.post(self.list_url, self._create_payload(), format="json")
        root_id = root_res.data["id"]

        corr_res = self.client.post(
            self.list_url,
            self._create_payload(description="corrected", previous_job=root_id),
            format="json",
        )
        self.assertEqual(corr_res.status_code, status.HTTP_201_CREATED)

        corr = Job.objects.get(pk=corr_res.data["id"])
        # 정정 작업은 이전 작업의 root_job을 그대로 물려받는다
        self.assertEqual(corr.root_job_id, root_id)
        self.assertEqual(corr.previous_job_id, root_id)

    def test_chain_endpoint_returns_full_chain_in_order(self):
        root = self._make_job(self.op1, action_type="a1")
        second = Job.objects.create(
            server=self.server, action_type="a2", description="d",
            created_by=self.op1, previous_job=root, root_job=root.root_job,
        )

        self.client.force_authenticate(user=self.op1)
        url = reverse("job-chain", args=[second.id])
        res = self.client.get(url)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        returned_ids = [row["id"] for row in res.data]
        # created_at 오름차순 → root가 먼저
        self.assertEqual(returned_ids, [root.id, second.id])


class JobEditWindowTest(JobTestBase):
    def test_edit_blocked_after_30_minutes(self):
        job = self._make_job(self.op1)
        # auto_now_add 우회: created_at을 31분 전으로 강제
        Job.objects.filter(pk=job.id).update(
            created_at=timezone.now() - timedelta(minutes=31)
        )

        self.client.force_authenticate(user=self.op1)  # 본인이라 권한은 통과
        url = reverse("job-detail", args=[job.id])
        res = self.client.patch(url, {"status": "running"}, format="json")

        # 권한(403)이 아니라 비즈니스 규칙(400)으로 막혀야 한다
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_edit_allowed_within_30_minutes(self):
        job = self._make_job(self.op1)  # 방금 생성 → 윈도우 내
        self.client.force_authenticate(user=self.op1)
        url = reverse("job-detail", args=[job.id])
        res = self.client.patch(url, {"status": "running"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)