"""
인증 흐름 테스트 (login / refresh / logout + 토큰 블랙리스트).

설계 포인트
-----------
- refresh 토큰은 응답 본문이 아니라 httponly 쿠키('refresh')로 오간다.
- ROTATE_REFRESH_TOKENS + BLACKLIST_AFTER_ROTATION이 켜져 있어,
  refresh를 한 번 쓰면 이전 토큰은 블랙리스트에 올라 재사용이 막힌다.
- 로그인/갱신/로그아웃 엔드포인트는 인증·권한이 비어 있다(공개).
"""
from rest_framework import status
from rest_framework.test import APITestCase

from apps.core.models import User

LOGIN_URL = "/api/auth/login/"
REFRESH_URL = "/api/auth/refresh/"
LOGOUT_URL = "/api/auth/logout/"


class AuthFlowTest(APITestCase):
    def setUp(self):
        self.password = "pw12345!"
        self.user = User.objects.create_user(
            username="alice", password=self.password, role=User.Role.OPERATOR
        )

    def _login(self):
        return self.client.post(
            LOGIN_URL,
            {"username": self.user.username, "password": self.password},
            format="json",
        )

    def test_login_success_sets_refresh_cookie(self):
        res = self._login()
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("access", res.data)        # access는 본문으로
        self.assertIn("refresh", res.cookies)     # refresh는 쿠키로
        self.assertNotIn("refresh", res.data)     # refresh가 본문에 노출되면 안 됨

    def test_login_failure_returns_400(self):
        res = self.client.post(
            LOGIN_URL,
            {"username": self.user.username, "password": "wrong-password"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_refresh_without_cookie_returns_401(self):
        # 로그인하지 않아 쿠키가 없는 상태
        res = self.client.post(REFRESH_URL)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_success_rotates_cookie(self):
        self._login()
        old_refresh = self.client.cookies["refresh"].value

        res = self.client.post(REFRESH_URL)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("access", res.data)

        new_refresh = res.cookies["refresh"].value
        self.assertNotEqual(new_refresh, old_refresh)  # 토큰이 회전됨

    def test_rotated_refresh_token_is_blacklisted(self):
        self._login()
        old_refresh = self.client.cookies["refresh"].value

        # 1차 갱신 → old_refresh는 블랙리스트, 쿠키는 새 토큰으로 교체
        first = self.client.post(REFRESH_URL)
        self.assertEqual(first.status_code, status.HTTP_200_OK)

        # 블랙리스트된 이전 토큰을 다시 사용하면 거부되어야 한다
        self.client.cookies["refresh"] = old_refresh
        reused = self.client.post(REFRESH_URL)
        self.assertEqual(reused.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_clears_refresh_cookie(self):
        self._login()
        res = self.client.post(LOGOUT_URL)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        # delete_cookie → 빈 값으로 덮어써짐
        self.assertEqual(res.cookies["refresh"].value, "")