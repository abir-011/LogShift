from rest_framework.permissions import BasePermission


def can_manage_logs(user):
    """Return whether a user may access destructive log management."""

    return bool(
        user
        and user.is_authenticated
        and user.is_active
        and user.is_staff
        and user.has_perm("logs.delete_logevent")
    )


class CanManageLogs(BasePermission):
    message = "You do not have permission to manage logs."

    def has_permission(self, request, view):
        return can_manage_logs(request.user)
