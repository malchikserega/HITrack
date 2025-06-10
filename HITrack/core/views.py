from rest_framework import viewsets, filters, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from .models import Repository, RepositoryTag, Image, Component, ComponentVersion, Vulnerability, ContainerRegistry
from .serializers import (
    RepositorySerializer, RepositoryTagSerializer, ImageSerializer, ImageListSerializer,
    ComponentSerializer, ComponentVersionSerializer, VulnerabilitySerializer, ComponentListSerializer,
    RepositoryListSerializer
)
from django.db import models
from .tasks import scan_repository
from .pagination import CustomPageNumberPagination

# Create your views here.

class BaseViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    ordering_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']  # Default ordering
    lookup_field = 'uuid'

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

class RepositoryTagViewSet(BaseViewSet):
    queryset = RepositoryTag.objects.all()
    serializer_class = RepositoryTagSerializer
    filterset_fields = ['repository', 'tag']
    search_fields = ['tag', 'repository__name']
    ordering_fields = ['tag', 'created_at', 'updated_at']

    @action(detail=True, methods=['get'])
    def images(self, request, pk=None):
        tag = self.get_object()
        images = tag.images.all()
        serializer = ImageSerializer(images, many=True)
        return Response(serializer.data)

class ImageViewSet(BaseViewSet):
    queryset = Image.objects.all()
    filterset_fields = ['repository_tags', 'component_versions']
    search_fields = ['name', 'digest']
    ordering_fields = ['name', 'created_at', 'updated_at']

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
        if image.scan_status == 'in_process':
            return Response({'error': 'Scan already in process'}, status=409)
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
        from django.db.models import Q
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
        ).all()
        serializer = ComponentVersionSerializer(versions, many=True)
        return Response(serializer.data)

class ComponentVersionViewSet(BaseViewSet):
    queryset = ComponentVersion.objects.all()
    serializer_class = ComponentVersionSerializer
    filterset_fields = ['component', 'images', 'vulnerabilities']
    search_fields = ['version', 'component__name']
    ordering_fields = ['version', 'created_at', 'updated_at']

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

class StatsViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

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

    @action(detail=False, methods=['post'], url_path='add-repositories')
    def add_repositories(self, request):
        """
        Add new repositories if they do not exist in the system yet.
        Repository is uniquely identified by the combination of name and url.
        The registry_uuid should be provided to link repositories to the correct registry.
        """
        from .models import ContainerRegistry
        try:
            repositories = request.data.get('repositories', [])
            registry_uuid = request.data.get('registry_uuid')
            if not repositories:
                return Response(
                    {'error': 'No repositories provided'},
                    status=status.HTTP_400_BAD_REQUEST
                )

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

@api_view(['GET'])
def has_acr_registry(request):
    exists = ContainerRegistry.objects.filter(provider='acr').exists()
    return Response({'has_acr': exists})

@api_view(['GET'])
def list_acr_registries(request):
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
