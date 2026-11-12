from rest_framework.permissions import BasePermission, SAFE_METHODS

from .models import Role


class IsAdminRole(BasePermission):
    """Only Admin users."""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == Role.ADMIN
        )


class IsManagerOrAbove(BasePermission):
    """Admin or Manager."""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in (Role.ADMIN, Role.MANAGER)
        )


class CanManageFinance(BasePermission):
    """Admin, Manager, or Accountant."""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in (Role.ADMIN, Role.MANAGER, Role.ACCOUNTANT)
        )


class CanWrite(BasePermission):
    """Read-only for all authenticated; write for Admin/Manager/Accountant/Agent."""

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return request.user.role in (Role.ADMIN, Role.MANAGER, Role.ACCOUNTANT, Role.AGENT)


class IsAuthenticatedReadOnly(BasePermission):
    """Any authenticated user can read; nobody can write via API (admin-only mutations)."""

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return request.method in SAFE_METHODS


class CanWriteManagerDelete(BasePermission):
    """Read: any authenticated user. Create/update: writers. Delete: admin or manager.

    Deleting is irreversible, so accountants and agents keep create/update but
    cannot remove records.
    """

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        if request.method == "DELETE":
            return request.user.role in (Role.ADMIN, Role.MANAGER)
        return request.user.role in (Role.ADMIN, Role.MANAGER, Role.ACCOUNTANT, Role.AGENT)
