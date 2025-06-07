from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    RepositoryViewSet, RepositoryTagViewSet, ImageViewSet,
    ComponentViewSet, ComponentVersionViewSet, VulnerabilityViewSet,
    StatsViewSet, JobViewSet
)

router = DefaultRouter()
router.register(r'repositories', RepositoryViewSet)
router.register(r'repository-tags', RepositoryTagViewSet)
router.register(r'images', ImageViewSet)
router.register(r'components', ComponentViewSet)
router.register(r'component-versions', ComponentVersionViewSet)
router.register(r'vulnerabilities', VulnerabilityViewSet)
router.register(r'stats', StatsViewSet, basename='stats')
router.register(r'jobs', JobViewSet, basename='jobs')

urlpatterns = [
    path('', include(router.urls)),
] 