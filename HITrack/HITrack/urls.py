"""
URL configuration for HITrack project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
from rest_framework_simplejwt.views import TokenVerifyView
from core.auth import (
    CookieTokenLogoutView,
    CookieTokenObtainPairView,
    CookieTokenRefreshView,
    CurrentUserView,
    HealthView,
)
from core.views import HasACRRegistryView, ListACRRegistriesView

urlpatterns = [
    path('api/health/', HealthView.as_view(), name='health'),
    path('admin/', admin.site.urls),
    path('api/', include('core.urls')),
    
    # JWT authentication URLs
    path('api/auth/token/', CookieTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/auth/token/refresh/', CookieTokenRefreshView.as_view(), name='token_refresh'),
    path('api/auth/token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    path('api/auth/logout/', CookieTokenLogoutView.as_view(), name='token_logout'),
    path('api/auth/me/', CurrentUserView.as_view(), name='current_user'),
    
    # OpenAPI documentation URLs
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

    # ACR registry endpoints
    path('api/acr/check/', HasACRRegistryView.as_view(), name='has_acr_registry'),
    path('api/acr/list/', ListACRRegistriesView.as_view(), name='list_acr_registries'),
]
