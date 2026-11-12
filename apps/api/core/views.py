from django.contrib.auth import get_user_model
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from .pagination import StandardPagination
from .permissions import IsAdminRole
from .serializers import (
    AdminSetPasswordSerializer,
    UserCreateSerializer,
    UserSerializer,
    UserUpdateSerializer,
)

User = get_user_model()


# ── Auth ────────────────────────────────────────────────────────────────

class LoginView(TokenObtainPairView):
    """JWT login — returns access + refresh tokens."""
    permission_classes = [AllowAny]


class LogoutView(APIView):
    """Blacklist the refresh token on logout."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response({"detail": "refresh token required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except Exception:
            pass
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    """Return the current authenticated user."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)

    def patch(self, request):
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        # Only allow updating safe fields for self
        allowed = {"first_name", "last_name", "email"}
        for field in list(serializer.validated_data.keys()):
            if field not in allowed:
                serializer.validated_data.pop(field)
        serializer.save()
        return Response(serializer.data)


# ── User Management (admin-only) ───────────────────────────────────────

class UserListCreateView(generics.ListCreateAPIView):
    """Admin-only: list all users (paginated) / create a new user."""
    permission_classes = [IsAuthenticated, IsAdminRole]
    pagination_class = StandardPagination
    queryset = User.objects.all().order_by("username")

    def get_serializer_class(self):
        if self.request.method == "POST":
            return UserCreateSerializer
        return UserSerializer

    def create(self, request, *args, **kwargs):
        serializer = UserCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


class UserDetailView(APIView):
    """Admin-only: retrieve, update, or soft-delete a single user."""
    permission_classes = [IsAuthenticated, IsAdminRole]

    def _get_user(self, pk):
        try:
            return User.objects.get(pk=pk)
        except User.DoesNotExist:
            return None

    def get(self, request, pk):
        user = self._get_user(pk)
        if not user:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(UserSerializer(user).data)

    def patch(self, request, pk):
        user = self._get_user(pk)
        if not user:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = UserUpdateSerializer(user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        # Self-protection: admin cannot deactivate or demote themselves
        if user.pk == request.user.pk:
            if "is_active" in serializer.validated_data and not serializer.validated_data["is_active"]:
                return Response(
                    {"detail": "You cannot deactivate your own account."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if "role" in serializer.validated_data and serializer.validated_data["role"] != "admin":
                return Response(
                    {"detail": "You cannot change your own role."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        serializer.save()
        return Response(UserSerializer(user).data)

    def delete(self, request, pk):
        user = self._get_user(pk)
        if not user:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        if user.pk == request.user.pk:
            return Response(
                {"detail": "You cannot delete your own account."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Soft-delete: deactivate instead of hard-delete to preserve FK integrity
        user.is_active = False
        user.save(update_fields=["is_active"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class UserSetPasswordView(APIView):
    """Admin-only: set a new password for any user (no old password required)."""
    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request, pk):
        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = AdminSetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password"])
        return Response({"detail": "Password updated successfully."})
