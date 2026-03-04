from rest_framework import generics, views, status, viewsets
from rest_framework.response import Response
from rest_framework.request import Request
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.settings import api_settings
from .serializers import JWTLogInSerializer
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.decorators import action
from apps.audit.models import AuditLog

# Refresh 토큰을 쿠키에 저장
def set_refresh_token_cookie(response: Response, refresh_token: str) -> Response:
    response.set_cookie(
        key='refresh',
        value=refresh_token,
        path='/api/auth',        # /api/auth 하위에서만 전송
        httponly=True,
        secure=False,            # HTTPS 환경에서는 True
        max_age=int(api_settings.REFRESH_TOKEN_LIFETIME.total_seconds())
    )
    return response


# 로그인
class LogInView(generics.GenericAPIView):
    permission_classes = ()
    authentication_classes = ()
    serializer_class = JWTLogInSerializer

    def post(self, request: Request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        refresh_token = data.pop('refresh')
        response = Response(data, status=status.HTTP_200_OK)
        return set_refresh_token_cookie(response, refresh_token)


# 토큰 갱신
class RefreshView(views.APIView):
    permission_classes = ()
    authentication_classes = ()

    def post(self, request: Request):
        refresh_cookie = request.COOKIES.get('refresh')
        if not refresh_cookie:
            return Response({"detail": "인증 정보(Refresh Token)를 찾을 수 없습니다."},
                            status=status.HTTP_401_UNAUTHORIZED)
        try:
            refresh_token = RefreshToken(refresh_cookie)
        except Exception:
            return Response({"detail": "유효하지 않거나 만료된 인증 정보입니다."},
                            status=status.HTTP_401_UNAUTHORIZED)

        response = Response({"access": str(refresh_token.access_token)}, status=status.HTTP_200_OK)

        if api_settings.ROTATE_REFRESH_TOKENS:
            if api_settings.BLACKLIST_AFTER_ROTATION:
                try:
                    refresh_token.blacklist()
                except AttributeError:
                    pass

            refresh_token.set_jti()
            refresh_token.set_exp()
            refresh_token.set_iat()
            response = set_refresh_token_cookie(response, str(refresh_token))

        return response


# 로그아웃
class LogOutView(views.APIView):
    permission_classes = ()
    authentication_classes = ()

    def post(self, request: Request):
        response = Response({"message": "성공적으로 로그아웃되었습니다."}, status=status.HTTP_200_OK)
        response.delete_cookie('refresh', path='/api/auth')
        return response
    

