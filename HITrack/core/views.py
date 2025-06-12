from rest_framework import viewsets, filters, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.generics import ListAPIView, GenericAPIView
from django_filters.rest_framework import DjangoFilterBackend
from .models import Repository, RepositoryTag, Image, Component, ComponentVersion, Vulnerability, ContainerRegistry
from .serializers import (
    RepositorySerializer, RepositoryTagSerializer, ImageSerializer, ImageListSerializer,
    ComponentSerializer, ComponentVersionSerializer, VulnerabilitySerializer, ComponentListSerializer,
    RepositoryListSerializer, RepositoryTagListSerializer, ComponentVersionListSerializer,
    HasACRRegistryResponseSerializer, ListACRRegistriesResponseSerializer,
    StatsResponseSerializer, JobAddRepositoriesRequestSerializer,
    JobAddRepositoriesResponseSerializer
)
from django.db import models
from .pagination import CustomPageNumberPagination
from django.db.models import Q, Count
from django.utils import timezone
from datetime import timedelta

# Create your views here.

class BaseViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    ordering_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']  # Default ordering
    lookup_field = 'uuid'
    pagination_class = CustomPageNumberPagination

class RepositoryViewSet(BaseViewSet):
    queryset = Repository.objects.all()
    filterset_fields = ['name']
    search_fields = ['name', 'url']
    ordering_fields = ['name', 'created_at', 'updated_at']

    def get_serializer_class(self):
        if self.action == 'list':
            return RepositoryListSerializer
        return RepositorySerializer

    @action(detail=True, methods=['get'])
    def tags(self, request, pk=None):
        repository = self.get_object()
        tags = repository.tags.all()
        serializer = RepositoryTagSerializer(tags, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def get_acr_repos(self, request):
        """
        Get repositories from Azure Container Registry with pagination.
        Uses ACR's native pagination to efficiently fetch repositories.
        """
        from .models import ContainerRegistry
        from .utils.acr import get_repositories, get_bearer_token

        registry_uuid = request.query_params.get('registry_uuid')
        provider = request.query_params.get('provider', 'acr')
        page_size = int(request.query_params.get('page_size', 50))
        last_repo = request.query_params.get('last')
        
        try:
            if registry_uuid:
                registry = ContainerRegistry.objects.get(uuid=registry_uuid)
            else:
                registry = ContainerRegistry.objects.get(provider=provider)
                
            token = get_bearer_token(registry.api_url, registry.login, registry.password)
            
            # Get repositories with pagination
            repos, next_page = get_repositories(
                registry.api_url,
                token,
                page_size=page_size,
                last_repo=last_repo
            )
            
            return Response({
                "repositories": [
                    {
                        "name": repo[0],
                        "url": repo[1]
                    }
                    for repo in repos
                ],
                "pagination": {
                    "next_page": next_page,
                    "page_size": page_size
                }
            })
        except ContainerRegistry.DoesNotExist:
            return Response(
                {"error": f"Registry not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    def scan_tags(self, request, uuid=None):
        repository = self.get_object()
        if repository.scan_status == 'in_process':
            return Response(
                {'error': 'Repository is already being scanned'}, 
                status=status.HTTP_409_CONFLICT
            )
        
        repository.scan_status = 'pending'
        repository.save()
        
        try:
            from .tasks import scan_repository_tags
            scan_repository_tags.delay(str(repository.uuid))
            return Response({
                'status': 'success',
                'message': 'Repository tags scan scheduled successfully'
            })
        except Exception as e:
            repository.scan_status = 'error'
            repository.save()
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['get'], url_path='paginated-tags')
    def paginated_tags(self, request, uuid=None):
        """
        Returns paginated, searchable, and sortable list of tags for a repository.
        """
        repository = self.get_object()
        tags = repository.tags.all()

        # Search
        search = request.query_params.get('search')
        if search:
            tags = tags.filter(Q(tag__icontains=search))

        # Ordering
        ordering = request.query_params.get('ordering', '-created_at')
        if ordering:
            tags = tags.order_by(ordering)

        # Pagination
        paginator = CustomPageNumberPagination()
        page = paginator.paginate_queryset(tags, request)
        serializer = RepositoryTagListSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    @action(detail=True, methods=['get'], url_path='tags-graph')
    def tags_graph(self, request, uuid=None):
        """
        Returns 30 tags for repository for use in charts (fields: uuid, tag, findings, components, created_at)
        """
        repository = self.get_object()
        tags = repository.tags.order_by('-tag')[:30]
        serializer = RepositoryTagListSerializer(tags, many=True)
        return Response(serializer.data)

class RepositoryTagViewSet(BaseViewSet):
    queryset = RepositoryTag.objects.all()
    serializer_class = RepositoryTagSerializer
    filterset_fields = ['repository', 'tag']
    search_fields = ['tag', 'repository__name']
    ordering_fields = ['tag', 'created_at', 'updated_at']
    lookup_field = 'uuid'

    def _check_time_restriction(self, tag):
        """Check if 5 minutes have passed since last update"""
        if tag.updated_at:
            time_diff = timezone.now() - tag.updated_at
            if time_diff < timedelta(minutes=5):
                remaining_seconds = int((timedelta(minutes=5) - time_diff).total_seconds())
                return False, f"Please wait {remaining_seconds} seconds before trying again"
        return True, None

    @action(detail=True, methods=['get'])
    def images(self, request, uuid=None):
        tag = self.get_object()
        images = tag.images.all()
        
        # Apply ordering if provided
        ordering = request.query_params.get('ordering', '-updated_at')
        if ordering:
            images = images.order_by(ordering)
            
        page = self.paginate_queryset(images)
        if page is not None:
            serializer = ImageListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = ImageListSerializer(images, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def process(self, request, uuid=None):
        tag = self.get_object()
        if tag.processing_status in ['in_process', 'pending']:
            return Response(
                {'error': 'Tag is already queued for processing'}, 
                status=status.HTTP_409_CONFLICT
            )
        
        tag.processing_status = 'pending'
        tag.save()
        
        try:
            from .tasks import process_single_tag
            process_single_tag.delay(str(tag.uuid))
            return Response({
                'status': 'success',
                'message': 'Tag processing scheduled successfully'
            })
        except Exception as e:
            tag.processing_status = 'error'
            tag.save()
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'], url_path='rescan-images')
    def rescan_images(self, request, uuid=None):
        tag = self.get_object()
        images = tag.images.all()
        # Check if any image is already being scanned or queued
        if images.filter(scan_status__in=['in_process', 'pending']).exists():
            return Response(
                {'error': 'At least one image is already being scanned or queued for scanning'},
                status=status.HTTP_409_CONFLICT
            )
        started = 0
        from .tasks import generate_sbom_and_create_components
        for image in images:
            if image.scan_status != 'in_process':
                image.scan_status = 'pending'
                image.save()
                repo_tag = image.repository_tags.first()
                art_type = repo_tag.repository.repository_type if repo_tag else 'docker'
                generate_sbom_and_create_components.delay(
                    image_uuid=str(image.uuid),
                    art_type=art_type
                )
                started += 1
        return Response({
            'status': 'success',
            'message': f'Rescan started for {started} images',
            'count': started
        })

class ImageViewSet(BaseViewSet):
    queryset = Image.objects.all()
    filterset_fields = ['repository_tags', 'component_versions']
    search_fields = ['name', 'digest']
    ordering_fields = ['name', 'created_at', 'updated_at']
    pagination_class = CustomPageNumberPagination

    def get_serializer_class(self):
        if self.action == 'list':
            return ImageListSerializer
        return ImageSerializer

    @action(detail=True, methods=['get'])
    def vulnerabilities(self, request, pk=None):
        image = self.get_object()
        vulnerabilities = Vulnerability.objects.filter(
            component_versions__images=image
        ).distinct()
        serializer = VulnerabilitySerializer(vulnerabilities, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def rescan(self, request, uuid=None):
        image = self.get_object()
        if image.scan_status in ['in_process', 'pending']:
            return Response(
                {'error': 'Image is already being scanned or queued for scanning'}, 
                status=status.HTTP_409_CONFLICT
            )
        image.scan_status = 'pending'
        image.save()
        try:
            repo_tag = image.repository_tags.first()
            if repo_tag:
                art_type = repo_tag.repository.repository_type
            else:
                art_type = 'docker'  # fallback default
            from .tasks import generate_sbom_and_create_components
            generate_sbom_and_create_components.delay(
                image_uuid=str(image.uuid),
                art_type=art_type
            )
            return Response({
                'status': 'success',
                'message': 'SBOM generation scheduled successfully'
            })
        except Exception as e:
            image.scan_status = 'error'
            image.save()
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['get'])
    def sbom(self, request, uuid=None):
        image = self.get_object()
        if image.sbom_data:
            return Response(image.sbom_data)
        return Response({'error': 'No SBOM data available.'}, status=404)

    @action(detail=True, methods=['get'], url_path='components')
    def components(self, request, uuid=None):
        """
        Paginated list of component versions for a given image, with search and ordering support.
        """
        image = self.get_object()
        # Get all component versions linked to this image, with their components
        component_versions = image.component_versions.select_related('component').all()

        # Search
        search = request.query_params.get('search')
        if search:
            component_versions = component_versions.filter(
                Q(version__icontains=search) |
                Q(component__name__icontains=search) |
                Q(component__type__icontains=search)
            )

        # Ordering
        ordering = request.query_params.get('ordering')
        if ordering:
            # Support ordering by version, component name, or type
            ordering_map = {
                'version': 'version',
                '-version': '-version',
                'name': 'component__name',
                '-name': '-component__name',
                'type': 'component__type',
                '-type': '-component__type',
                'created_at': 'created_at',
                '-created_at': '-created_at',
                'updated_at': 'updated_at',
                '-updated_at': '-updated_at',
            }
            ordering_field = ordering_map.get(ordering, ordering)
            component_versions = component_versions.order_by(ordering_field)
        else:
            component_versions = component_versions.order_by('-created_at')

        # Pagination
        paginator = CustomPageNumberPagination()
        page = paginator.paginate_queryset(component_versions, request)
        serializer = ComponentVersionSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

class ComponentViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Component.objects.all()
    filterset_fields = ['name', 'type']
    search_fields = ['name', 'type']
    ordering_fields = ['name', 'type', 'created_at', 'updated_at']
    pagination_class = CustomPageNumberPagination

    def get_serializer_class(self):
        if self.action == 'list':
            return ComponentListSerializer
        return ComponentSerializer

    @action(detail=True, methods=['get'])
    def versions(self, request, pk=None):
        component = self.get_object()
        versions = component.versions.select_related(
            'component'
        ).prefetch_related(
            'images',
            'vulnerabilities'
        ).all().order_by('-version')
        serializer = ComponentVersionSerializer(versions, many=True)
        return Response(serializer.data)

class ComponentVersionViewSet(BaseViewSet):
    queryset = ComponentVersion.objects.all()
    serializer_class = ComponentVersionSerializer
    filterset_fields = ['component', 'images', 'vulnerabilities']
    search_fields = ['version', 'component__name']
    ordering_fields = ['version', 'created_at', 'updated_at', 'vulnerabilities_count']

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.annotate(vulnerabilities_count=Count('vulnerabilities'))

    def get_serializer_class(self):
        if self.action == 'list':
            return ComponentVersionListSerializer
        return ComponentVersionSerializer

    @action(detail=True, methods=['get'])
    def vulnerabilities(self, request, pk=None):
        version = self.get_object()
        vulnerabilities = version.vulnerabilities.all()
        serializer = VulnerabilitySerializer(vulnerabilities, many=True)
        return Response(serializer.data)

class VulnerabilityViewSet(BaseViewSet):
    """
    API endpoint for managing vulnerabilities.
    
    list:
    Return a list of all vulnerabilities.
    
    retrieve:
    Return the details of a specific vulnerability.
    
    create:
    Create a new vulnerability.
    
    update:
    Update an existing vulnerability.
    
    partial_update:
    Partially update an existing vulnerability.
    
    destroy:
    Delete a vulnerability.
    
    severity_stats:
    Return statistics about vulnerabilities grouped by severity.
    """
    queryset = Vulnerability.objects.all()
    serializer_class = VulnerabilitySerializer
    filterset_fields = ['severity', 'component_versions']
    search_fields = ['cve_id', 'description']
    ordering_fields = ['cve_id', 'severity', 'epss', 'created_at', 'updated_at']

    @action(detail=False, methods=['get'])
    def severity_stats(self, request):
        """
        Return statistics about vulnerabilities grouped by severity.
        
        Returns a count of vulnerabilities for each severity level.
        """
        stats = Vulnerability.objects.values('severity').annotate(
            count=models.Count('id')
        ).order_by('severity')
        return Response(stats)

class HasACRRegistryView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = HasACRRegistryResponseSerializer

    def get(self, request):
        exists = ContainerRegistry.objects.filter(provider='acr').exists()
        return Response({'has_acr': exists})

class ListACRRegistriesView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ListACRRegistriesResponseSerializer

    def get(self, request):
        registries = ContainerRegistry.objects.filter(provider='acr')
        data = [
            {
                'uuid': str(r.uuid),
                'name': r.name,
                'api_url': r.api_url
            }
            for r in registries
        ]
        return Response({'registries': data})

class StatsViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = StatsResponseSerializer

    def list(self, request):
        data = {
            'repositories': Repository.objects.count(),
            'images': Image.objects.count(),
            'vulnerabilities': Vulnerability.objects.count(),
            'components': Component.objects.count(),
        }
        return Response(data)

class JobViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = JobAddRepositoriesResponseSerializer

    @action(detail=False, methods=['post'], url_path='add-repositories')
    def add_repositories(self, request):
        """
        Add new repositories if they do not exist in the system yet.
        Repository is uniquely identified by the combination of name and url.
        The registry_uuid should be provided to link repositories to the correct registry.
        """
        serializer = JobAddRepositoriesRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            repositories = serializer.validated_data['repositories']
            registry_uuid = serializer.validated_data.get('registry_uuid')

            # Get the registry by uuid or fallback to first acr
            registry = None
            if registry_uuid:
                registry = ContainerRegistry.objects.filter(uuid=registry_uuid).first()
            else:
                registry = ContainerRegistry.objects.filter(provider='acr').first()
            if not registry:
                return Response(
                    {'error': 'No ACR registry found'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            results = []
            for repo_data in repositories:
                repository, created = Repository.objects.get_or_create(
                    url=repo_data['repository_url'],
                    name=repo_data['repository_name'],
                    defaults={
                        'status': True,
                        'repository_type': 'none',
                        'container_registry': registry
                    }
                )
                result = {
                    'repository': repo_data['repository_name'],
                    'repository_id': str(repository.uuid),
                    'created': created
                }
                if not created:
                    result['message'] = 'Repository already exists'
                results.append(result)

            return Response({
                'status': 'success',
                'message': f'Processed {len(repositories)} repositories',
                'results': results
            })

        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class RepositoryTagListForRepositoryView(ListAPIView):
    serializer_class = RepositoryTagListSerializer
    pagination_class = CustomPageNumberPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['tag']
    ordering_fields = ['created_at', 'updated_at', 'tag']
    ordering = ['-updated_at']

    def get_queryset(self):
        repository_uuid = self.kwargs['repository_uuid']
        return RepositoryTag.objects.filter(repository__uuid=repository_uuid)
