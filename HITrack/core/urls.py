from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    RepositoryViewSet, RepositoryTagViewSet, ImageViewSet,
    ComponentViewSet, ComponentVersionViewSet, VulnerabilityViewSet,
    StatsViewSet, JobViewSet, HasACRRegistryView, ListACRRegistriesView,
    ListRegistriesView,
    RepositoryTagListForRepositoryView, ReportGeneratorView,
    ComponentMatrixView, ReleaseViewSet, VulnerabilityDetailsViewSet,
    TaskManagementViewSet, PeriodicTaskViewSet, TestTaskViewSet, TestViewSet
)

router = DefaultRouter()
router.register(r'repositories', RepositoryViewSet, basename='repository')
router.register(r'repository-tags', RepositoryTagViewSet, basename='repository-tag')
router.register(r'images', ImageViewSet, basename='image')
router.register(r'components', ComponentViewSet, basename='component')
router.register(r'component-versions', ComponentVersionViewSet)
router.register(r'vulnerabilities', VulnerabilityViewSet, basename='vulnerability')
router.register(r'vulnerability-details', VulnerabilityDetailsViewSet, basename='vulnerability-details')
router.register(r'releases', ReleaseViewSet, basename='release')
router.register(r'stats', StatsViewSet, basename='stats')
router.register(r'jobs', JobViewSet, basename='job')
router.register(r'tasks', TaskManagementViewSet, basename='task')
router.register(r'periodic-tasks', PeriodicTaskViewSet, basename='periodic-task')
router.register(r'test-tasks', TestTaskViewSet, basename='test-task')
router.register(r'test', TestViewSet, basename='test')

urlpatterns = [
    path('', include(router.urls)),
    path('has-acr-registry/', HasACRRegistryView.as_view(), name='has-acr-registry'),
    path('list-acr-registries/', ListACRRegistriesView.as_view(), name='list-acr-registries'),
    path('registries/', ListRegistriesView.as_view(), name='list-registries'),
    path('repositories/<uuid:repository_uuid>/tags-list/', RepositoryTagListForRepositoryView.as_view(), name='repository-tags-list'),
    path('reports/generate/', ReportGeneratorView.as_view(), name='generate-report'),
    path('component-matrix/', ComponentMatrixView.as_view(), name='component-matrix'),
] 