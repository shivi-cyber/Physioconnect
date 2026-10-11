from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from core.audit import audit
from core.exceptions import ApiError

from .serializers import LoginSerializer, RegisterSerializer, UserSerializer

User = get_user_model()


def token_payload(user):
    refresh = RefreshToken.for_user(user)
    return {
        'access': str(refresh.access_token),
        'refresh': str(refresh),
        'user': UserSerializer(user).data,
    }


class RegisterView(APIView):
    """POST /api/v1/auth/register/  - patient self-registration."""
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth'

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(token_payload(user), status=status.HTTP_201_CREATED)


class LoginView(APIView):
    """POST /api/v1/auth/login/  - body: {"email": "...", "password": "..."}"""
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth'

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        identifier = serializer.validated_data['identifier']
        password = serializer.validated_data['password']

        user = (
            User.objects.filter(email__iexact=identifier).first()
            or User.objects.filter(username__iexact=identifier).first()
            or User.objects.filter(phone=identifier).first()
        )
        if not user or not user.check_password(password):
            raise ApiError('INVALID_CREDENTIALS', 'Incorrect email/phone or password.', 401)
        if not user.is_active or user.status != 'active':
            raise ApiError('ACCOUNT_DISABLED', 'This account is not active. Please contact the clinic.', 403)

        audit(request, 'auth.login', 'user', user.id)
        return Response(token_payload(user))


class MeView(APIView):
    """GET /api/v1/auth/me/  - who am I?"""

    def get(self, request):
        return Response(UserSerializer(request.user).data)
