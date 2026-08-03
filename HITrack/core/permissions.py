from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsOperatorOrReadOnly(BasePermission):
    """Viewers can inspect exposure; operators (or staff) may change it."""
    message = 'Operator role is required for this operation.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        return request.user.is_staff or request.user.is_superuser or request.user.groups.filter(
            name__in=('operator', 'admin')
        ).exists()


class IsSecurityAdmin(BasePermission):
    message = 'Security administrator role is required for this operation.'

    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated and (
                request.user.is_superuser or request.user.groups.filter(name='admin').exists()
            )
        )
