from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    RepositoryViewSet, RepositoryTagViewSet, ImageViewSet,
    ComponentViewSet, ComponentVersionViewSet, VulnerabilityViewSet,
    StatsViewSet, JobViewSet, has_acr_registry, list_acr_registries
)

router = DefaultRouter()
router.register(r'repositories', RepositoryViewSet, basename='repository')
router.register(r'repository-tags', RepositoryTagViewSet, basename='repository-tag')
router.register(r'images', ImageViewSet, basename='image')
router.register(r'components', ComponentViewSet, basename='component')
router.register(r'component-versions', ComponentVersionViewSet)
router.register(r'vulnerabilities', VulnerabilityViewSet, basename='vulnerability')
router.register(r'stats', StatsViewSet, basename='stats')
router.register(r'jobs', JobViewSet, basename='job')

urlpatterns = [
    path('', include(router.urls)),
    path('has-acr-registry/', has_acr_registry, name='has-acr-registry'),
    path('list-acr-registries/', list_acr_registries, name='list-acr-registries'),
] 