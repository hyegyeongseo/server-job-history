from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken, TokenError
from django.contrib.auth import authenticate

# 로그인 시 Access/Refresh 토큰 발급용
class JWTLogInSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)
    access = serializers.CharField(read_only=True)
    refresh = serializers.CharField(read_only=True)

    def validate(self, attrs: dict):
        username = attrs.get('username')
        password = attrs.get('password')

        user = authenticate(username=username, password=password)
        if not user:
            raise serializers.ValidationError("사용자 인증 실패")

        try:
            refresh = RefreshToken.for_user(user)
        except TokenError as e:
            raise serializers.ValidationError(str(e))

        return {
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'username': user.username
        }
    
class EmptySerializer(serializers.Serializer):
    pass