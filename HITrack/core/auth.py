from django.conf import settings
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

REFRESH_COOKIE = 'hitrack_refresh'


class CookieTokenObtainPairView(TokenObtainPairView):
    """Keep long-lived credentials out of JavaScript-accessible storage."""
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        refresh = response.data.pop('refresh', None)
        if refresh:
            response.set_cookie(REFRESH_COOKIE, refresh, httponly=True,
                                secure=not settings.DEBUG, samesite='Lax',
                                max_age=int(settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'].total_seconds()))
        return response


class CookieTokenRefreshView(TokenRefreshView):
    def post(self, request, *args, **kwargs):
        data = request.data.copy()
        data['refresh'] = data.get('refresh') or request.COOKIES.get(REFRESH_COOKIE)
        request._full_data = data
        response = super().post(request, *args, **kwargs)
        refresh = response.data.pop('refresh', None)
        if refresh:
            response.set_cookie(REFRESH_COOKIE, refresh, httponly=True,
                                secure=not settings.DEBUG, samesite='Lax')
        return response
