from django.conf import settings
from django.core.cache import cache
from django.db import connection
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

REFRESH_COOKIE = 'hitrack_refresh'


class HealthView(APIView):
    """Dependency-aware readiness check without configuration disclosure."""
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = []

    def get(self, request):
        checks = {'database': False, 'cache': False}
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
                checks['database'] = cursor.fetchone()[0] == 1
        except Exception:
            pass
        try:
            cache.set('hitrack-health', 'ok', timeout=5)
            checks['cache'] = cache.get('hitrack-health') == 'ok'
        except Exception:
            pass
        healthy = all(checks.values())
        return Response(
            {'status': 'ok' if healthy else 'unavailable', 'checks': checks},
            status=status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE,
        )


def _set_refresh_cookie(response, refresh, *, max_age=None):
    response.set_cookie(
        REFRESH_COOKIE,
        refresh,
        httponly=True,
        secure=not settings.DEBUG,
        samesite='Lax',
        max_age=max_age,
        path='/',
    )


class CookieTokenObtainPairView(TokenObtainPairView):
    """Keep long-lived credentials out of JavaScript-accessible storage."""
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        refresh = response.data.pop('refresh', None)
        if refresh:
            _set_refresh_cookie(
                response,
                refresh,
                max_age=int(settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'].total_seconds()),
            )
        return response


class CookieTokenRefreshView(TokenRefreshView):
    def post(self, request, *args, **kwargs):
        data = request.data.copy()
        data['refresh'] = data.get('refresh') or request.COOKIES.get(REFRESH_COOKIE)
        if not data['refresh']:
            return Response(
                {'detail': 'No active refresh session.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        request._full_data = data
        response = super().post(request, *args, **kwargs)
        refresh = response.data.pop('refresh', None)
        if refresh:
            _set_refresh_cookie(response, refresh)
        return response


class CookieTokenLogoutView(APIView):
    """Invalidate the refresh token and remove its HttpOnly cookie."""
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        refresh = request.COOKIES.get(REFRESH_COOKIE)
        if refresh:
            try:
                RefreshToken(refresh).blacklist()
            except Exception:
                # Logout is intentionally idempotent, including for expired or
                # already-blacklisted cookies.
                pass
        response = Response(status=status.HTTP_204_NO_CONTENT)
        response.delete_cookie(
            REFRESH_COOKIE,
            path='/',
            samesite='Lax',
        )
        return response


class CurrentUserView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        groups = list(request.user.groups.values_list('name', flat=True))
        is_admin = request.user.is_superuser or 'admin' in groups
        can_write = request.user.is_staff or is_admin or 'operator' in groups
        return Response({
            'id': request.user.pk,
            'username': request.user.get_username(),
            'email': request.user.email,
            'groups': groups,
            'can_write': can_write,
            'is_admin': is_admin,
        })
