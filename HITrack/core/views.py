from rest_framework import viewsets, filters, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.generics import ListAPIView, GenericAPIView
from django_filters.rest_framework import DjangoFilterBackend
from .models import Repository, RepositoryTag, Image, Component, ComponentVersion, Vulnerability, ContainerRegistry, ComponentVersionVulnerability, Release, RepositoryTagRelease, VulnerabilityDetails, ComponentLocation
from .serializers import (
    RepositorySerializer, RepositoryTagSerializer, ImageSerializer, ImageListSerializer,
    ComponentSerializer, ComponentVersionSerializer, VulnerabilitySerializer, VulnerabilityShortSerializer, ComponentListSerializer,
    RepositoryListSerializer, RepositoryTagListSerializer, ComponentVersionListSerializer,
    HasACRRegistryResponseSerializer, ListACRRegistriesResponseSerializer,
    StatsResponseSerializer, JobAddRepositoriesRequestSerializer,
    JobAddRepositoriesResponseSerializer, ImageDropdownSerializer,
    ReleaseSerializer, RepositoryTagReleaseSerializer, ReleaseAssignmentSerializer,
    VulnerabilityListSerializer, VulnerabilityDetailsSerializer,
    TaskResultSerializer, TaskResultListSerializer, PeriodicTaskSerializer, TaskStatisticsSerializer,
    ComponentLocationSerializer
)
from django.db import models
from .pagination import CustomPageNumberPagination
from django.db.models import Q, Count
from django.utils import timezone
from datetime import timedelta, datetime
from io import BytesIO
from rest_framework.views import APIView
from django.http import HttpResponse
from openpyxl import Workbook
from django.shortcuts import render
from packaging import version as packaging_version
import re

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
    def tags(self, request, uuid=None):
        repository = self.get_object()
        tags = repository.tags.all()
        serializer = RepositoryTagSerializer(tags, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def create_tag(self, request, uuid=None):
        """
        Create a new tag for the repository.
        """
        repository = self.get_object()
        tag_name = request.data.get('tag')
        description = request.data.get('description', '')
        
        print(f"Creating tag: repository={repository.name}, tag={tag_name}, description={description}")
        print(f"Request data: {request.data}")
        
        if not tag_name:
            return Response(
                {'error': 'Tag name is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if tag already exists
        if repository.tags.filter(tag=tag_name).exists():
            return Response(
                {'error': 'Tag already exists'}, 
                status=status.HTTP_409_CONFLICT
            )
        
        try:
            # Create new tag
            tag = RepositoryTag.objects.create(
                repository=repository,
                tag=tag_name
            )
            
            serializer = RepositoryTagSerializer(tag)
            return Response(
                serializer.data, 
                status=status.HTTP_201_CREATED
            )
        except Exception as e:
            return Response(
                {'error': f'Failed to create tag: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'])
    def create_release_with_tags(self, request):
        """
        Create a new release and link it with repository tags.
        """
        release_name = request.data.get('release_name')
        release_description = request.data.get('release_description', '')
        tag_uuids = request.data.get('tag_uuids', [])
        
        print(f"Creating release: name={release_name}, description={release_description}")
        print(f"Tag UUIDs: {tag_uuids}")
        
        if not release_name:
            return Response(
                {'error': 'Release name is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not tag_uuids:
            return Response(
                {'error': 'At least one tag UUID is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Check if release name already exists (case-insensitive)
            if Release.objects.filter(name__iexact=release_name).exists():
                return Response(
                    {'release_name': ['Release with this name already exists.']}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Create new release
            release = Release.objects.create(
                name=release_name,
                description=release_description
            )
            
            # Get repository tags and create links
            repository_tags = RepositoryTag.objects.filter(uuid__in=tag_uuids)
            created_links = []
            
            for tag in repository_tags:
                # Check if link already exists
                if not RepositoryTagRelease.objects.filter(
                    repository_tag=tag, 
                    release=release
                ).exists():
                    link = RepositoryTagRelease.objects.create(
                        repository_tag=tag,
                        release=release
                    )
                    created_links.append(link)
            
            # Return success response
            return Response({
                'release_uuid': str(release.uuid),
                'release_name': release.name,
                'tags_linked': len(created_links),
                'total_tags': len(tag_uuids)
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response(
                {'error': f'Failed to create release: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'])
    def check_helm_releases(self, request):
        """
        Check multiple Helm releases against the database.
        Expects a list of objects with 'name' and 'app_version' fields.
        """
        releases_data = request.data.get('releases', [])
        
        if not releases_data:
            return Response(
                {'error': 'Releases data is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            results = []
            
            # Get all repositories and tags in one query
            all_repositories = Repository.objects.all()
            all_tags = RepositoryTag.objects.select_related('repository').all()
            
            # Create lookup dictionaries for faster access
            repos_by_name = {repo.name: repo for repo in all_repositories}
            tags_by_repo_and_version = {}
            
            for tag in all_tags:
                key = f"{tag.repository.uuid}_{tag.tag}"
                tags_by_repo_and_version[key] = tag
            
            for release in releases_data:
                name = release.get('name')
                app_version = release.get('app_version')
                
                if not name or not app_version:
                    results.append({
                        'name': name,
                        'app_version': app_version,
                        'repository_status': 'Error',
                        'tag_status': 'Error',
                        'error': 'Missing name or app_version'
                    })
                    continue
                
                # Check if repository exists
                repository = repos_by_name.get(name)
                repository_status = 'Found' if repository else 'Not Found'
                
                # Check if tag exists (only if repository exists)
                tag_status = 'Not Found'
                tag_uuid = None
                if repository:
                    tag_key = f"{repository.uuid}_{app_version}"
                    tag = tags_by_repo_and_version.get(tag_key)
                    if tag:
                        tag_status = 'Found'
                        tag_uuid = str(tag.uuid)
                
                results.append({
                    'name': name,
                    'app_version': app_version,
                    'repository_status': repository_status,
                    'tag_status': tag_status,
                    'repository_uuid': str(repository.uuid) if repository else None,
                    'tag_uuid': tag_uuid
                })
            
            return Response({
                'results': results,
                'total_checked': len(results),
                'repositories_found': len([r for r in results if r['repository_status'] == 'Found']),
                'tags_found': len([r for r in results if r['tag_status'] == 'Found'])
            })
            
        except Exception as e:
            return Response(
                {'error': f'Failed to check releases: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

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
        page_size = int(request.query_params.get('page_size', 100))
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
            scan_repository_tags.apply_async(args=[str(repository.uuid)], task_name="Scan Repository Tags")
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
        Returns the latest 30 tags for repository for use in charts (fields: uuid, tag, findings, components, created_at)
        Tags are sorted by semantic version (numeric part) and then by suffix, returning the most recent 30 tags.
        """
        repository = self.get_object()
        tags = list(repository.tags.all())
        
        version_regex = re.compile(r'^(\d+\.\d+\.\d+)')
        def version_key(tag):
            match = version_regex.match(tag.tag)
            if match:
                try:
                    ver = packaging_version.parse(match.group(1))
                except Exception:
                    ver = packaging_version.Version('0.0.0')
                suffix = tag.tag[len(match.group(1)):] or ''
                return (ver, suffix)
            else:
                return (packaging_version.Version('0.0.0'), tag.tag)
        
        sorted_tags = sorted(tags, key=version_key)[-30:]
        serializer = RepositoryTagListSerializer(sorted_tags, many=True)
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
            process_single_tag.apply_async(args=[str(tag.uuid)], task_name="Process Single Tag")
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
                generate_sbom_and_create_components.apply_async(
                    kwargs={
                        'image_uuid': str(image.uuid),
                        'art_type': art_type
                    },
                    task_name="Generate SBOM and Create Components"
                )
                started += 1
        return Response({
            'status': 'success',
            'message': f'Rescan started for {started} images',
            'count': started
        })

    @action(detail=True, methods=['post'])
    def add_to_release(self, request, uuid=None):
        """Add repository tag to release"""
        repository_tag = self.get_object()
        serializer = ReleaseAssignmentSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            release_id = serializer.validated_data['release_id']
            release = Release.objects.get(uuid=release_id)
            
            # Check if assignment already exists
            assignment, created = RepositoryTagRelease.objects.get_or_create(
                repository_tag=repository_tag,
                release=release
            )
            
            if created:
                return Response({
                    'message': f'Repository tag added to release "{release.name}"',
                    'release': ReleaseSerializer(release).data
                })
            else:
                return Response({
                    'message': f'Repository tag already assigned to release "{release.name}"',
                    'release': ReleaseSerializer(release).data
                })
                
        except Release.DoesNotExist:
            return Response(
                {'error': 'Release not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['delete'])
    def remove_from_release(self, request, uuid=None):
        """Remove repository tag from release"""
        repository_tag = self.get_object()
        serializer = ReleaseAssignmentSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            release_id = serializer.validated_data['release_id']
            assignment = RepositoryTagRelease.objects.filter(
                repository_tag=repository_tag,
                release_id=release_id
            ).first()
            
            if assignment:
                release_name = assignment.release.name
                assignment.delete()
                return Response({
                    'message': f'Repository tag removed from release "{release_name}"'
                })
            else:
                return Response({
                    'message': 'Repository tag not assigned to this release'
                })
                
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class ImageViewSet(BaseViewSet):
    queryset = Image.objects.all()
    filterset_fields = ['repository_tags', 'component_versions']
    search_fields = ['name']
    ordering_fields = ['name', 'created_at', 'updated_at']
    pagination_class = CustomPageNumberPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]

    def get_serializer_class(self):
        if self.action == 'list' and self.request and self.request.query_params.get('dropdown') == '1':
            return ImageDropdownSerializer
        if self.action == 'list':
            return ImageListSerializer
        return ImageSerializer

    def get_queryset(self):
        # Always apply search and filters, even for dropdown
        queryset = super().get_queryset()
        
        # Optimize for repository_info by prefetching repository_tags and their repositories
        if self.action == 'retrieve':
            queryset = queryset.prefetch_related(
                'repository_tags__repository'
            )
        
        return queryset

    @action(detail=True, methods=['post'])
    def update_latest_versions(self, request, uuid=None):
        """
        Update latest versions for all components in this image.
        This will check all package registries for the latest available versions.
        """
        image = self.get_object()
        try:
            from .tasks import update_components_latest_versions
            update_components_latest_versions.delay(str(image.uuid))
            return Response({
                'status': 'success',
                'message': 'Latest versions update scheduled successfully'
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['get'], url_path='vulnerabilities')
    def vulnerabilities(self, request, uuid=None):
        """
        Paginated list of vulnerabilities for a given image, with search and ordering support.
        """
        # Temporarily disable search filter for this action
        original_filter_backends = self.filter_backends
        self.filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
        
        try:
            image = self.get_object()
        except Exception:
            self.filter_backends = original_filter_backends
            return Response({'error': 'Image not found'}, status=404)
        
        # Restore original filter_backends
        self.filter_backends = original_filter_backends
        
        # Get all vulnerabilities linked to this image through component versions
        vulnerabilities = Vulnerability.objects.filter(
            component_versions__images=image
        ).distinct()

        # Search
        search = request.query_params.get('search')
        if search:
            vulnerabilities = vulnerabilities.filter(
                vulnerability_id__icontains=search
            )

        # Ordering
        ordering = request.query_params.get('ordering')
        if ordering:
            # Support ordering by vulnerability fields
            ordering_map = {
                'vulnerability_id': 'vulnerability_id',
                '-vulnerability_id': '-vulnerability_id',
                'vulnerability_type': 'vulnerability_type',
                '-vulnerability_type': '-vulnerability_type',
                'severity': 'severity',
                '-severity': '-severity',
                'epss': 'epss',
                '-epss': '-epss',
                'created_at': 'created_at',
                '-created_at': '-created_at',
                'updated_at': 'updated_at',
                '-updated_at': '-updated_at',
            }
            ordering_field = ordering_map.get(ordering, ordering)
            vulnerabilities = vulnerabilities.order_by(ordering_field)
        else:
            vulnerabilities = vulnerabilities.order_by('-created_at')

        # Pagination
        paginator = CustomPageNumberPagination()
        page = paginator.paginate_queryset(vulnerabilities, request)
        
        # Serialize with fix information from ComponentVersionVulnerability
        vuln_data = []
        for vuln in page:
            vuln_dict = VulnerabilitySerializer(vuln).data
            # Get fix information from ComponentVersionVulnerability
            cvv = ComponentVersionVulnerability.objects.filter(
                vulnerability=vuln,
                component_version__images=image
            ).first()
            if cvv:
                vuln_dict['fixable'] = cvv.fixable
                vuln_dict['fix'] = cvv.fix
            else:
                vuln_dict['fixable'] = False
                vuln_dict['fix'] = ''
            vuln_data.append(vuln_dict)
        
        return paginator.get_paginated_response(vuln_data)

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

    @action(detail=True, methods=['post'], url_path='rescan-grype')
    def rescan_grype(self, request, uuid=None):
        """
        Re-analyze SBOM for this image using Grype.
        """
        image = self.get_object()
        if not image.sbom_data:
            return Response({'error': 'No SBOM data available for this image.'}, status=400)
        try:
            from .tasks import scan_image_with_grype
            scan_image_with_grype.delay(str(image.uuid))
            return Response({'status': 'success', 'message': 'Grype scan scheduled successfully'})
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    @action(detail=True, methods=['get'], url_path='component-locations')
    def component_locations(self, request, uuid=None):
        """
        Get detailed location information for all components in an image.
        """
        image = self.get_object()
        
        # Get all component locations for this image
        locations = ComponentLocation.objects.filter(
            image=image
        ).select_related('component_version', 'component_version__component')
        
        # Group by component version
        component_locations = {}
        for location in locations:
            component_version = location.component_version
            component_key = f"{component_version.component.name}:{component_version.version}"
            
            if component_key not in component_locations:
                component_locations[component_key] = {
                    'component_name': component_version.component.name,
                    'component_version': component_version.version,
                    'component_type': component_version.component.type,
                    'purl': component_version.purl,
                    'cpes': component_version.cpes,
                    'locations': []
                }
            
            component_locations[component_key]['locations'].append({
                'path': location.path,
                'layer_id': location.layer_id,
                'access_path': location.access_path,
                'evidence_type': location.evidence_type,
                'annotations': location.annotations
            })
        
        return Response({
            'image_uuid': str(image.uuid),
            'image_name': image.name,
            'component_locations': list(component_locations.values())
        })

class ComponentViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Component.objects.all()
    filterset_fields = ['name', 'type']
    search_fields = ['name', 'type']
    ordering_fields = ['name', 'type', 'created_at', 'updated_at']
    pagination_class = CustomPageNumberPagination
    lookup_field = 'uuid'

    def get_serializer_class(self):
        if self.action == 'list':
            return ComponentListSerializer
        return ComponentSerializer

    @action(detail=True, methods=['get'])
    def versions(self, request, uuid=None):
        component = self.get_object()
        versions = component.versions.select_related(
            'component'
        ).prefetch_related(
            'images',
            'vulnerabilities',
            'componentversionvulnerability_set__vulnerability'
        ).annotate(
            vulnerabilities_count=Count('vulnerabilities')
        ).all().order_by('-version')
        serializer = ComponentVersionSerializer(versions, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def locations(self, request, uuid=None):
        """
        Get location information for all versions of this component.
        """
        component = self.get_object()
        
        # Get all component locations for this component
        locations = ComponentLocation.objects.filter(
            component_version__component=component
        ).select_related('component_version', 'image')
        
        # Group by component version and image
        location_data = []
        for location in locations:
            location_data.append({
                'component_version': {
                    'uuid': str(location.component_version.uuid),
                    'version': location.component_version.version,
                    'purl': location.component_version.purl,
                    'cpes': location.component_version.cpes
                },
                'image': {
                    'uuid': str(location.image.uuid),
                    'name': location.image.name
                },
                'path': location.path,
                'layer_id': location.layer_id,
                'access_path': location.access_path,
                'evidence_type': location.evidence_type,
                'annotations': location.annotations
            })
        
        return Response({
            'component_uuid': str(component.uuid),
            'component_name': component.name,
            'component_type': component.type,
            'locations': location_data
        })

    @action(detail=True, methods=['get'])
    def vulnerabilities(self, request, uuid=None):
        """
        Get all vulnerabilities for this component across all versions.
        """
        component = self.get_object()
        
        # Get all vulnerabilities through component versions with optimized queries
        vulnerabilities = Vulnerability.objects.filter(
            component_versions__component=component
        ).select_related('details').prefetch_related(
            'component_versions__component'
        ).distinct()
        
        serializer = VulnerabilitySerializer(vulnerabilities, many=True)
        return Response(serializer.data)

class ComponentVersionViewSet(BaseViewSet):
    queryset = ComponentVersion.objects.all()
    serializer_class = ComponentVersionSerializer
    filterset_fields = ['component', 'images', 'vulnerabilities']
    search_fields = ['version', 'component__name']
    ordering_fields = ['version', 'created_at', 'updated_at', 'vulnerabilities_count']

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.annotate(vulnerabilities_count=Count('vulnerabilities')).order_by('component__name', 'version', 'created_at')

    def get_serializer_class(self):
        if self.action == 'list':
            return ComponentVersionListSerializer
        return ComponentVersionSerializer

    @action(detail=True, methods=['get'])
    def vulnerabilities(self, request, uuid=None):
        version = self.get_object()
        vulnerabilities = version.vulnerabilities.all()
        serializer = VulnerabilityShortSerializer(vulnerabilities, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def locations(self, request, uuid=None):
        """
        Get location information for this specific component version.
        """
        version = self.get_object()
        
        # Get all component locations for this version
        locations = ComponentLocation.objects.filter(
            component_version=version
        ).select_related('image')
        
        # Format location data
        location_data = []
        for location in locations:
            location_data.append({
                'image': {
                    'uuid': str(location.image.uuid),
                    'name': location.image.name
                },
                'path': location.path,
                'layer_id': location.layer_id,
                'access_path': location.access_path,
                'evidence_type': location.evidence_type,
                'annotations': location.annotations
            })
        
        return Response({
            'version_uuid': str(version.uuid),
            'version': version.version,
            'component_name': version.component.name,
            'locations': location_data
        })

class ReleaseViewSet(BaseViewSet):
    """
    API endpoint for managing releases.
    
    list:
    Return a list of all releases.
    
    retrieve:
    Return the details of a specific release.
    
    create:
    Create a new release.
    
    update:
    Update an existing release.
    
    partial_update:
    Partially update an existing release.
    
    destroy:
    Delete a release.
    """
    queryset = Release.objects.all()
    serializer_class = ReleaseSerializer
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']
    
    @action(detail=False, methods=['get'])
    def with_stats(self, request):
        """Get all releases with repository tag counts and vulnerability stats"""
        releases = Release.objects.annotate(
            tag_count=Count('repository_tags')
        ).prefetch_related('repository_tags')
        
        release_data = []
        for release in releases:
            # Get vulnerability stats for this release through RepositoryTagRelease
            critical_vulns = Vulnerability.objects.filter(
                component_versions__images__repository_tags__releases__release=release,
                severity='CRITICAL'
            ).distinct().count()
            
            high_vulns = Vulnerability.objects.filter(
                component_versions__images__repository_tags__releases__release=release,
                severity='HIGH'
            ).distinct().count()
            
            release_data.append({
                'uuid': str(release.uuid),
                'name': release.name,
                'description': release.description,
                'tag_count': release.tag_count,
                'critical_vulnerabilities': critical_vulns,
                'high_vulnerabilities': high_vulns,
                'created_at': release.created_at
            })
        
        return Response(release_data)

    @action(detail=False, methods=['get'])
    def names(self, request):
        """Get only release names and UUIDs for validation purposes"""
        releases = Release.objects.values('uuid', 'name').order_by('name')
        return Response(list(releases))


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
    
    update_details:
    Update detailed information for a vulnerability from external sources.
    
    exploit_stats:
    Return statistics about vulnerabilities with exploit information.
    """
    queryset = Vulnerability.objects.all()
    serializer_class = VulnerabilitySerializer
    filterset_fields = ['severity', 'vulnerability_type']
    search_fields = ['vulnerability_id']
    ordering_fields = ['vulnerability_id', 'severity', 'epss', 'created_at', 'updated_at']

    def get_queryset(self):
        queryset = Vulnerability.objects.all()

        
        # Add filters for exploit information
        exploit_available = self.request.query_params.get('exploit_available', None)
        if exploit_available is not None:
            exploit_available = exploit_available.lower() == 'true'
            if exploit_available:
                queryset = queryset.filter(details__exploit_available=True)
            else:
                queryset = queryset.filter(
                    Q(details__exploit_available=False) | Q(details__isnull=True)
                )
        
        # Add filter for vulnerabilities with details
        has_details = self.request.query_params.get('has_details', None)
        if has_details is not None:
            has_details = has_details.lower() == 'true'
            if has_details:
                queryset = queryset.filter(details__isnull=False)
            else:
                queryset = queryset.filter(details__isnull=True)
        
        # Add filter for CISA KEV vulnerabilities
        cisa_kev = self.request.query_params.get('cisa_kev', None)
        if cisa_kev is not None:
            cisa_kev = cisa_kev.lower() == 'true'
            if cisa_kev:
                queryset = queryset.filter(details__cisa_kev_known_exploited=True)
            else:
                queryset = queryset.filter(
                    Q(details__cisa_kev_known_exploited=False) | Q(details__isnull=True)
                )
        
        # Add filter for ransomware vulnerabilities
        ransomware = self.request.query_params.get('ransomware', None)
        if ransomware is not None:
            ransomware = ransomware.lower() == 'true'
            if ransomware:
                queryset = queryset.filter(details__cisa_kev_ransomware_use='Known')
            else:
                queryset = queryset.filter(
                    Q(details__cisa_kev_ransomware_use__in=['Unknown', 'None']) | Q(details__isnull=True)
                )
        
        return queryset

    def get_serializer_class(self):
        if self.action == 'list':
            return VulnerabilityListSerializer
        return VulnerabilitySerializer

    @action(detail=False, methods=['get'])
    def severity_stats(self, request):
        """Return statistics about vulnerabilities grouped by severity."""
        stats = Vulnerability.objects.values('severity').annotate(
            count=Count('id')
        ).order_by('severity')
        
        return Response({
            'severity_stats': list(stats),
            'total_vulnerabilities': Vulnerability.objects.count()
        })

    @action(detail=True, methods=['post'])
    def update_details(self, request, uuid=None):
        """
        Update detailed information for a vulnerability from external sources.
        """
        from .tasks import update_vulnerability_details
        
        vulnerability = self.get_object()
        
        # Trigger the update task
        task = update_vulnerability_details.delay(str(vulnerability.uuid))
        
        return Response({
            'status': 'task_started',
            'task_id': task.id,
            'vulnerability_id': vulnerability.vulnerability_id,
            'message': 'Vulnerability details update started'
        })

    @action(detail=False, methods=['get'])
    def exploit_stats(self, request):
        """Return statistics about vulnerabilities with exploit information."""
        total_vulns = Vulnerability.objects.count()
        vulns_with_details = Vulnerability.objects.filter(details__isnull=False).count()
        vulns_with_exploits = Vulnerability.objects.filter(details__exploit_available=True).count()
        vulns_with_public_exploits = Vulnerability.objects.filter(details__exploit_public=True).count()
        vulns_with_verified_exploits = Vulnerability.objects.filter(details__exploit_verified=True).count()
        
        return Response({
            'total_vulnerabilities': total_vulns,
            'vulnerabilities_with_details': vulns_with_details,
            'vulnerabilities_with_exploits': vulns_with_exploits,
            'vulnerabilities_with_public_exploits': vulns_with_public_exploits,
            'vulnerabilities_with_verified_exploits': vulns_with_verified_exploits,
            'percentage_with_details': round((vulns_with_details / total_vulns * 100), 2) if total_vulns > 0 else 0,
            'percentage_with_exploits': round((vulns_with_exploits / total_vulns * 100), 2) if total_vulns > 0 else 0
        })

    @action(detail=False, methods=['post'])
    def bulk_update_details(self, request):
        """
        Update detailed information for all vulnerabilities.
        """
        from .tasks import update_all_vulnerability_details
        
        # Trigger the bulk update task
        task = update_all_vulnerability_details.delay()
        
        return Response({
            'status': 'task_started',
            'task_id': task.id,
            'message': 'Bulk vulnerability details update started'
        })

    @action(detail=False, methods=['post'])
    def update_critical_details(self, request):
        """
        Update detailed information for critical and high severity vulnerabilities.
        """
        from .tasks import update_critical_vulnerability_details
        
        # Trigger the critical update task
        task = update_critical_vulnerability_details.delay()
        
        return Response({
            'status': 'task_started',
            'task_id': task.id,
            'message': 'Critical vulnerability details update started'
        })

    @action(detail=True, methods=['get'])
    def images(self, request, uuid=None):
        """
        Get all images that contain this vulnerability.
        """
        vulnerability = self.get_object()
        
        # Optimized query with prefetch_related and annotations
        images = Image.objects.filter(
            component_versions__vulnerabilities=vulnerability
        ).distinct().prefetch_related(
            'repository_tags__repository',
            'component_versions'
        ).annotate(
            findings_count=models.Count(
                'component_versions__componentversionvulnerability',
                filter=models.Q(component_versions__componentversionvulnerability__vulnerability=vulnerability)
            ),
            unique_findings_count=models.Count(
                'component_versions__componentversionvulnerability__vulnerability',
                filter=models.Q(component_versions__componentversionvulnerability__vulnerability=vulnerability),
                distinct=True
            ),
            components_count=models.Count('component_versions', distinct=True)
        ).order_by('name', 'created_at')
        
        # Apply pagination
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(images, request)
        
        if page is not None:
            serializer = ImageListSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)
        
        serializer = ImageListSerializer(images, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def components(self, request, uuid=None):
        """
        Get all component versions that contain this vulnerability.
        """
        vulnerability = self.get_object()
        
        # Get component versions that have this vulnerability with proper ordering and annotations
        component_versions = ComponentVersion.objects.filter(
            vulnerabilities=vulnerability
        ).select_related('component').prefetch_related('images').annotate(
            vulnerabilities_count=models.Count('vulnerabilities', distinct=True)
        ).order_by(
            'component__name', 'version', 'created_at'
        )
        
        # Apply pagination
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(component_versions, request)
        
        if page is not None:
            serializer = ComponentVersionListSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)
        
        serializer = ComponentVersionListSerializer(component_versions, many=True)
        return Response(serializer.data)


class VulnerabilityDetailsViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for viewing vulnerability details.
    
    list:
    Return a list of all vulnerability details.
    
    retrieve:
    Return the details of a specific vulnerability detail record.
    """
    queryset = VulnerabilityDetails.objects.all()
    serializer_class = VulnerabilityDetailsSerializer
    filterset_fields = ['exploit_available', 'exploit_public', 'exploit_verified', 'data_source']
    ordering_fields = ['last_updated', 'cve_details_score']
    ordering = ['-last_updated']

    @action(detail=False, methods=['get'])
    def exploit_summary(self, request):
        """Return summary of exploit information."""
        total_details = VulnerabilityDetails.objects.count()
        with_exploits = VulnerabilityDetails.objects.filter(exploit_available=True).count()
        with_public_exploits = VulnerabilityDetails.objects.filter(exploit_public=True).count()
        with_verified_exploits = VulnerabilityDetails.objects.filter(exploit_verified=True).count()
        
        return Response({
            'total_details': total_details,
            'with_exploits': with_exploits,
            'with_public_exploits': with_public_exploits,
            'with_verified_exploits': with_verified_exploits,
            'percentage_with_exploits': round((with_exploits / total_details * 100), 2) if total_details > 0 else 0
        })

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

    @action(detail=False, methods=['get'])
    def dashboard_metrics(self, request):
        """Get comprehensive dashboard metrics with optimized queries"""
        from django.db.models import Count, Avg, Q
        from django.utils import timezone
        from datetime import timedelta
        
        # Calculate date once
        thirty_days_ago = timezone.now() - timedelta(days=30)
        
        # Optimized basic counts with select_related/prefetch_related
        total_repositories = Repository.objects.count()
        total_images = Image.objects.count()
        
        # Optimized severity distribution - single query
        severity_distribution = Vulnerability.objects.values('severity').annotate(
            count=Count('uuid')
        ).order_by('severity')
        
        # Optimized vulnerability trends - indexed date field
        vulnerability_trends = Vulnerability.objects.filter(
            created_at__gte=thirty_days_ago
        ).values('created_at__date').annotate(
            count=Count('uuid')
        ).order_by('created_at__date')
        
        # Optimized top vulnerable components - avoid N+1 with select_related
        top_vulnerable_components = ComponentVersion.objects.select_related('component').annotate(
            vuln_count=Count('vulnerabilities')
        ).filter(vuln_count__gt=0).order_by('-vuln_count')[:10]
        
        # Optimized top vulnerabilities by EPSS - limit fields
        top_vulnerabilities_by_epss = Vulnerability.objects.filter(
            epss__isnull=False
        ).only('uuid', 'vulnerability_id', 'severity', 'epss', 'description').order_by('-epss')[:10]
        
        # Optimized security metrics - single aggregation query
        security_metrics = Vulnerability.objects.aggregate(
            critical_count=Count('uuid', filter=Q(severity='CRITICAL')),
            total_count=Count('uuid')
        )
        
        # Optimized fixable vulnerabilities count - count unique vulnerabilities that are fixable
        fixable_vulns = ComponentVersionVulnerability.objects.filter(
            fixable=True
        ).values('vulnerability').distinct().count()
        
        # Calculate percentage based on unique vulnerabilities
        total_vulns = security_metrics['total_count']
        fixable_percentage = (fixable_vulns / total_vulns * 100) if total_vulns > 0 else 0
        
        # Additional security metrics
        cisa_kev_vulns = Vulnerability.objects.filter(details__cisa_kev_known_exploited=True).count()
        exploit_available_vulns = Vulnerability.objects.filter(details__exploit_available=True).count()
        ransomware_vulns = Vulnerability.objects.filter(details__cisa_kev_ransomware_use='Known').count()
        vulns_with_details = Vulnerability.objects.filter(details__isnull=False).count()
        
        # Calculate percentages
        cisa_kev_percentage = (cisa_kev_vulns / total_vulns * 100) if total_vulns > 0 else 0
        exploit_percentage = (exploit_available_vulns / total_vulns * 100) if total_vulns > 0 else 0
        ransomware_percentage = (ransomware_vulns / total_vulns * 100) if total_vulns > 0 else 0
        details_percentage = (vulns_with_details / total_vulns * 100) if total_vulns > 0 else 0
        
        # Optimized recent activities - single query with union
        recent_activities = []
        
        # Recent repository scans - optimized with only needed fields
        recent_scans = Repository.objects.filter(
            updated_at__gte=thirty_days_ago
        ).only('name', 'updated_at', 'scan_status').order_by('-updated_at')[:5]
        
        for repo in recent_scans:
            recent_activities.append({
                'type': 'scan',
                'title': f'Repository "{repo.name}" scanned',
                'timestamp': repo.updated_at,
                'status': repo.scan_status
            })
        
        # Recent vulnerabilities - optimized with only needed fields
        recent_vulns = Vulnerability.objects.filter(
            created_at__gte=thirty_days_ago
        ).only('vulnerability_id', 'created_at', 'severity').order_by('-created_at')[:5]
        
        for vuln in recent_vulns:
            recent_activities.append({
                'type': 'vulnerability',
                'title': f'New vulnerability: {vuln.vulnerability_id}',
                'timestamp': vuln.created_at,
                'severity': vuln.severity
            })
        
        # Sort activities by timestamp
        recent_activities.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return Response({
            'basic_stats': {
                'repositories': total_repositories,
                'images': total_images
            },
            'security_metrics': {
                'critical_vulnerabilities': security_metrics['critical_count'],
                'fixable_vulnerabilities': fixable_vulns,
                'fixable_percentage': round(fixable_percentage, 1),
                'cisa_kev_vulnerabilities': cisa_kev_vulns,
                'cisa_kev_percentage': round(cisa_kev_percentage, 1),
                'exploit_available_vulnerabilities': exploit_available_vulns,
                'exploit_percentage': round(exploit_percentage, 1),
                'ransomware_vulnerabilities': ransomware_vulns,
                'ransomware_percentage': round(ransomware_percentage, 1),
                'vulnerabilities_with_details': vulns_with_details,
                'details_percentage': round(details_percentage, 1)
            },
            'severity_distribution': list(severity_distribution),
            'vulnerability_trends': list(vulnerability_trends),
            'top_vulnerable_components': [
                {
                    'name': cv.component.name,
                    'version': cv.version,
                    'vulnerability_count': cv.vuln_count
                }
                for cv in top_vulnerable_components
            ],
            'top_vulnerabilities_by_epss': [
                {
                    'uuid': str(vuln.uuid),
                    'vulnerability_id': vuln.vulnerability_id,
                    'severity': vuln.severity,
                    'epss': round(vuln.epss, 3),
                    'description': vuln.description[:100] + '...' if len(vuln.description) > 100 else vuln.description
                }
                for vuln in top_vulnerabilities_by_epss
            ],
            'recent_activities': recent_activities[:10]
        })

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

class ReportGeneratorView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Generate a vulnerability report for selected images or a release.
        Returns an Excel file with vulnerability data.
        
        Request body:
        - For images: {"image_uuids": ["uuid1", "uuid2", ...]}
        - For release: {"release_uuid": "uuid"}
        """
        image_uuids = request.data.get('image_uuids', [])
        release_uuid = request.data.get('release_uuid')
        
        if not image_uuids and not release_uuid:
            return Response(
                {'error': 'No images or release selected'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # If release_uuid is provided, get all images from that release
        if release_uuid:
            try:
                release = Release.objects.get(uuid=release_uuid)
                # Get all images from repository tags in this release
                images = Image.objects.filter(
                    repository_tags__releases__release=release
                ).distinct()
            except Release.DoesNotExist:
                return Response(
                    {'error': 'Release not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        else:
            # Use provided image UUIDs
            images = Image.objects.filter(uuid__in=image_uuids)

        try:
            # Create Excel file in memory
            output = BytesIO()
            wb = Workbook()
            ws = wb.active
            ws.title = 'Vulnerability Report'
            ws.append([
                'Image Name', 'Component Name', 'Component Type', 'Component Version',
                'Vulnerability ID', 'Vulnerability Severity', 'Fixed In'
            ])

            for image in images:
                findings_qs = ComponentVersionVulnerability.objects.filter(
                    component_version__images=image
                ).select_related(
                    'component_version',
                    'component_version__component',
                    'vulnerability'
                )
                if findings_qs.exists():
                    for cvv in findings_qs:
                        ws.append([
                            image.name,
                            cvv.component_version.component.name,
                            cvv.component_version.component.type,
                            cvv.component_version.version,
                            cvv.vulnerability.vulnerability_id,
                            cvv.vulnerability.severity,
                            cvv.fix if cvv.fixable else 'No fix available'
                        ])
                else:
                    ws.append([
                        image.name, '', '', '', '', '', ''
                    ])

            wb.save(output)
            output.seek(0)

            from datetime import datetime
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            
            # Generate appropriate filename based on report type
            if release_uuid:
                release_name = Release.objects.get(uuid=release_uuid).name
                filename = f"release_{release_name}_vulnerability_report_{timestamp}.xlsx"
            else:
                filename = f"vulnerability_report_{timestamp}.xlsx"

            response = HttpResponse(
                output.getvalue(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            response['Access-Control-Expose-Headers'] = 'Content-Disposition'
            return response

        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class ComponentMatrixView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Generate a component matrix for selected repositories or images.
        Returns JSON: columns are repo:tag or image names, rows are components, cells are versions.
        
        Request body:
        {
            "type": "repository" | "image",  # Type of comparison
            "repository_tags": [{"repo_uuid": "uuid1", "tag": "tag1"}, ...],  # For repository comparison
            "image_uuids": ["uuid1", "uuid2"]  # For image comparison
        }
        """
        comparison_type = request.data.get('type', 'repository')
        repo_tags = request.data.get('repository_tags', [])
        image_uuids = request.data.get('image_uuids', [])

        if comparison_type == 'repository' and not repo_tags:
            return Response({'error': 'No repositories selected'}, status=400)
        elif comparison_type == 'image' and not image_uuids:
            return Response({'error': 'No images selected'}, status=400)

        # Get all relevant data with a single query
        from core.models import Repository, RepositoryTag, Image, ComponentVersion, ComponentVersionVulnerability
        from django.db.models import Max, Prefetch, Subquery, OuterRef

        if comparison_type == 'repository':
            tags = RepositoryTag.objects.filter(
                repository__uuid__in=[rt['repo_uuid'] for rt in repo_tags],
                tag__in=[rt['tag'] for rt in repo_tags]
            ).select_related('repository').order_by('repository__uuid', '-tag')

            tag_mapping = {
                f"{tag.repository.uuid}:{tag.tag}": tag
                for tag in tags
            }

            columns = []
            component_set = set()
            image_components = {}
            seen_col_labels = set()
            for repo_tag in repo_tags:
                repo_uuid = repo_tag['repo_uuid']
                tag_name = repo_tag['tag']
                tag_key = f"{repo_uuid}:{tag_name}"
                tag = tag_mapping.get(tag_key)
                if not tag:
                    continue
                col_label = f"{tag.repository.name}:{tag.tag}"
                if col_label in seen_col_labels:
                    continue  # avoid duplicate columns
                seen_col_labels.add(col_label)
                columns.append({
                    'repo': tag.repository.name,
                    'tag': tag.tag,
                    'label': col_label,
                    'type': 'repository'
                })
                images_for_tag = Image.objects.filter(repository_tags=tag, sbom_data__isnull=False).order_by('-updated_at')
                image_components[col_label] = {}
                for image in images_for_tag:
                    cvs = image.component_versions.all()
                    for cv in cvs:
                        cname = cv.component.name
                        component_set.add(cname)
                        if cname not in image_components[col_label]:
                            image_components[col_label][cname] = {
                                'version': cv.version,
                                'has_vuln': cv.componentversionvulnerability_set.exists(),
                                'latest_version': cv.latest_version
                            }

        else:  # comparison_type == 'image'
            # Get all relevant images with SBOM in one query
            images = Image.objects.filter(
                uuid__in=image_uuids,
                sbom_data__isnull=False
            ).prefetch_related(
                'component_versions',
                'component_versions__component',
                'component_versions__componentversionvulnerability_set'
            ).order_by('-updated_at')

            # Build columns and collect all component versions in one go
            columns = []
            component_set = set()
            image_components = {}
            
            for image in images:
                col_label = image.name
                columns.append({
                    'name': image.name,
                    'digest': image.digest,
                    'label': col_label,
                    'type': 'image'
                })
                
                # Get all component versions for this image with their vulnerabilities
                cvs = image.component_versions.all()
                image_components[col_label] = {}
                
                for cv in cvs:
                    cname = cv.component.name
                    component_set.add(cname)
                    image_components[col_label][cname] = {
                        'version': cv.version,
                        'has_vuln': cv.componentversionvulnerability_set.exists(),
                        'latest_version': cv.latest_version
                    }

        components = sorted(component_set)

        # Build matrix using the pre-fetched data
        matrix = {}
        for cname in components:
            matrix[cname] = {}
            for col in columns:
                col_label = col['label']
                if col_label in image_components and cname in image_components[col_label]:
                    matrix[cname][col_label] = image_components[col_label][cname]
                else:
                    matrix[cname][col_label] = {'version': '', 'has_vuln': False, 'latest_version': None}

        # Get component types
        component_types = {}
        for component in Component.objects.filter(name__in=components):
            component_types[component.name] = component.type

        return Response({
            'components': components,
            'columns': columns,
            'matrix': matrix,
            'type': comparison_type,
            'component_types': component_types
        })

# Celery Task Views
from django_celery_results.models import TaskResult
from django_celery_beat.models import PeriodicTask
from django.db.models import Q, Avg, Count
from django.utils import timezone
from datetime import timedelta
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from celery import current_app
import json

# Import task serializers after they are defined
from .serializers import (
    TaskResultSerializer, TaskResultListSerializer, 
    PeriodicTaskSerializer, TaskStatisticsSerializer
)

class TestViewSet(viewsets.ViewSet):
    """
    Simple test viewset to check if imports work
    """
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def test(self, request):
        """Simple test endpoint"""
        return Response({
            'message': 'Test endpoint works!',
            'task_count': TaskResult.objects.count(),
            'periodic_task_count': PeriodicTask.objects.count()
        })
    
    @action(detail=False, methods=['get'], url_path='endpoint')
    def test_endpoint(self, request):
        """Simple test endpoint for frontend"""
        return Response({
            'message': 'Test endpoint works!',
            'status': 'success'
        })
    
    @action(detail=False, methods=['get'], url_path='direct')
    def test_direct(self, request):
        """Direct test endpoint"""
        return Response({
            'message': 'Direct API test works!',
            'status': 'success',
            'timestamp': timezone.now().isoformat()
        })

class TaskManagementViewSet(BaseViewSet):
    """
    ViewSet for managing and monitoring Celery tasks
    """
    queryset = TaskResult.objects.all().order_by('-date_created')
    serializer_class = TaskResultSerializer
    filterset_fields = ['status', 'task_name']
    search_fields = ['task_id', 'task_name']
    ordering_fields = ['date_created', 'date_done', 'status']
    ordering = ['-date_created']
    lookup_field = 'task_id'
    
    def get_serializer_class(self):
        """Use different serializers for list and detail views"""
        if self.action == 'list':
            return TaskResultListSerializer
        return TaskResultSerializer
    
    def list(self, request):
        """List tasks with proper pagination and filtering"""
        # Use the parent class's list method which handles pagination, filtering, and search
        return super().list(request)
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by date range
        days = self.request.query_params.get('days', None)
        if days:
            try:
                days = int(days)
                cutoff_date = timezone.now() - timedelta(days=days)
                queryset = queryset.filter(date_created__gte=cutoff_date)
            except ValueError:
                pass
        
        # Filter by status
        status_filter = self.request.query_params.get('status', None)
        if status_filter:
            if status_filter == 'success':
                queryset = queryset.filter(status='SUCCESS')
            elif status_filter == 'error':
                queryset = queryset.filter(status='FAILURE')
            elif status_filter == 'pending':
                queryset = queryset.filter(status='PENDING')
            elif status_filter == 'in_process':
                queryset = queryset.filter(status='STARTED')
        
        return queryset
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get task statistics"""
        # Get date range
        days = int(request.query_params.get('days', 7))
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Get tasks in date range
        tasks = TaskResult.objects.filter(date_created__gte=cutoff_date)
        
        # Calculate statistics
        total_tasks = tasks.count()
        successful_tasks = tasks.filter(status='SUCCESS').count()
        failed_tasks = tasks.filter(status='FAILURE').count()
        pending_tasks = tasks.filter(status='PENDING').count()
        running_tasks = tasks.filter(status='STARTED').count()
        
        # Calculate average duration
        completed_tasks = tasks.filter(status='SUCCESS', date_done__isnull=False)
        if completed_tasks.exists():
            # Calculate duration for each task and then average
            total_duration = 0
            count = 0
            for task in completed_tasks:
                if task.date_done and task.date_created:
                    duration = task.date_done - task.date_created
                    total_duration += duration.total_seconds()
                    count += 1
            
            avg_duration = total_duration / count if count > 0 else 0.0
        else:
            avg_duration = 0.0
        
        # Get recent tasks
        recent_tasks = tasks.order_by('-date_created')[:10]
        recent_tasks_data = []
        for task in recent_tasks:
            duration = None
            if task.date_done and task.date_created:
                duration = (task.date_done - task.date_created).total_seconds()
            
                    # Get proper task name
        task_name = task.task_name
        if not task_name:
            try:
                from celery import current_app
                task_func = current_app.tasks.get(task.task_id)
                if task_func:
                    task_name = task_func.name
            except:
                pass
        
        if not task_name:
            # Try to extract from task_id by looking for known patterns
            if task.task_id:
                if 'generate_sbom' in task.task_id or 'sbom' in task.task_id:
                    task_name = "Generate SBOM and Create Components"
                elif 'scan' in task.task_id and 'grype' in task.task_id:
                    task_name = "Scan Image with Grype"
                elif 'vulnerability' in task.task_id and 'update' in task.task_id:
                    task_name = "Update Vulnerability Details"
                elif 'process' in task.task_id and 'tag' in task.task_id:
                    task_name = "Process Single Tag"
                elif 'repository' in task.task_id and 'scan' in task.task_id:
                    task_name = "Scan Repository"
                elif 'parse' in task.task_id and 'sbom' in task.task_id:
                    task_name = "Parse SBOM and Create Components"
                elif 'update' in task.task_id and 'component' in task.task_id:
                    task_name = "Update Components Latest Versions"
                elif 'process' in task.task_id and 'grype' in task.task_id:
                    task_name = "Process Grype Scan Results"
                elif 'cleanup' in task.task_id:
                    task_name = "Cleanup Old Vulnerability Data"
                elif 'cisa' in task.task_id or 'kev' in task.task_id:
                    task_name = "Update CISA KEV Vulnerabilities"
                elif 'test' in task.task_id:
                    task_name = "Test Task"
                else:
                    task_name = f"Task-{task.task_id[:8]}"
            else:
                task_name = 'Unknown'
            
            recent_tasks_data.append({
                'task_id': task.task_id,
                'task_name': task_name,
                'status': task.status,
                'duration': duration,
                'created': task.date_created
            })
        
        data = {
            'total_tasks': total_tasks,
            'successful_tasks': successful_tasks,
            'failed_tasks': failed_tasks,
            'pending_tasks': pending_tasks,
            'running_tasks': running_tasks,
            'average_duration': avg_duration,
            'recent_tasks': recent_tasks_data
        }
        
        return Response(data)
    
    @action(detail=False, methods=['get'])
    def task_types(self, request):
        """Get statistics by task type"""
        days = int(request.query_params.get('days', 7))
        cutoff_date = timezone.now() - timedelta(days=days)
        
        tasks = TaskResult.objects.filter(date_created__gte=cutoff_date)
        
        # Group by task name and status
        task_stats = tasks.values('task_name').annotate(
            total=Count('id'),
            success=Count('id', filter=Q(status='SUCCESS')),
            failure=Count('id', filter=Q(status='FAILURE')),
            pending=Count('id', filter=Q(status='PENDING')),
            running=Count('id', filter=Q(status='STARTED'))
        ).order_by('-total')
        
        return Response(task_stats)
    
    @action(detail=True, methods=['get'])
    def result_details(self, request, pk=None):
        """Get detailed result information for a task"""
        task = self.get_object()
        
        # Parse result if it's JSON
        result_data = None
        if task.result:
            try:
                result_data = json.loads(task.result)
            except (json.JSONDecodeError, TypeError):
                result_data = str(task.result)
        
        data = {
            'task_id': task.task_id,
            'task_name': task.task_name,
            'status': task.status,
            'created': task.date_created,
            'updated': task.date_done,
            'duration': (task.date_done - task.date_created).total_seconds() if task.date_done else None,
            'result': result_data,
            'traceback': task.traceback,
            'meta': task.meta
        }
        
        return Response(data)
    
    @action(detail=True, methods=['post'])
    def retry_task(self, request, task_id=None):
        """Retry a failed task"""
        try:
            task = TaskResult.objects.get(task_id=task_id)
            if task.status != 'FAILURE':
                return Response(
                    {'error': 'Only failed tasks can be retried'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Retry the task
            celery_app = current_app
            celery_app.control.revoke(task_id, terminate=True)
            
            # Get the task function and retry it
            if task.task_name:
                task_func = celery_app.tasks.get(task.task_name)
                if task_func:
                    # Retry the task
                    result = task_func.delay()
                    return Response({
                        'message': 'Task retry initiated',
                        'new_task_id': result.id
                    })
            
            return Response(
                {'error': 'Could not retry task'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        except TaskResult.DoesNotExist:
            return Response(
                {'error': 'Task not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=True, methods=['post'])
    def stop_task(self, request, task_id=None):
        """Stop a running task"""
        try:
            # Get the task result
            task_result = TaskResult.objects.get(task_id=task_id)
            
            # Check if task is running
            if task_result.status not in ['STARTED', 'PENDING']:
                return Response(
                    {'error': f'Task is in {task_result.status} state and cannot be stopped'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Revoke the task in Celery
            from celery import current_app
            current_app.control.revoke(task_id, terminate=True)
            
            # Update the task status in database
            task_result.status = 'REVOKED'
            task_result.save()
            
            return Response({
                'message': 'Task stopped successfully',
                'task_id': task_id,
                'status': 'REVOKED'
            })
            
        except TaskResult.DoesNotExist:
            return Response(
                {'error': 'Task not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': f'Failed to stop task: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class PeriodicTaskViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for managing periodic tasks
    """
    queryset = PeriodicTask.objects.all().order_by('name')
    serializer_class = PeriodicTaskSerializer
    filterset_fields = ['enabled', 'task']
    search_fields = ['name', 'task']
    ordering_fields = ['name', 'last_run_at', 'total_run_count']
    ordering = ['name']
    
    @action(detail=True, methods=['post'])
    def toggle_enabled(self, request, pk=None):
        """Toggle periodic task enabled/disabled status"""
        task = self.get_object()
        task.enabled = not task.enabled
        task.save()
        
        return Response({
            'id': task.id,
            'name': task.name,
            'enabled': task.enabled
        })
    
    @action(detail=True, methods=['post'])
    def run_now(self, request, pk=None):
        """Run a periodic task immediately"""
        task = self.get_object()
        
        try:
            # Get the task function and run it
            celery_app = current_app
            task_func = celery_app.tasks.get(task.task)
            if task_func:
                result = task_func.delay()
                return Response({
                    'message': 'Task started',
                    'task_id': result.id
                })
            else:
                return Response(
                    {'error': 'Task function not found'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

class TestTaskViewSet(viewsets.ViewSet):
    """
    ViewSet for testing tasks
    """
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['post'])
    def run_test_task(self, request):
        """Run a simple test task"""
        from .tasks import test_task
        
        try:
            # Use apply_async with explicit task name
            result = test_task.apply_async(task_name="Test Task")
            return Response({
                'message': 'Test task started',
                'task_id': result.id
            })
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['post'])
    def run_failing_task(self, request):
        """Run a task that will fail"""
        from .tasks import test_failing_task
        
        try:
            # Use apply_async with explicit task name
            result = test_failing_task.apply_async(task_name="Test Failing Task")
            return Response({
                'message': 'Failing test task started',
                'task_id': result.id
            })
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['post'])
    def update_all_components_latest_versions(self, request):
        """Update latest versions for all components in the system"""
        from .tasks import update_all_components_latest_versions
        
        try:
            result = update_all_components_latest_versions.delay()
            return Response({
                'message': 'All components latest versions update started',
                'task_id': result.id
            })
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['post'])
    def rescan_all_images_with_sbom(self, request):
        """Re-analyze all images that have SBOM data using Grype"""
        from .tasks import rescan_all_images_with_sbom
        
        try:
            result = rescan_all_images_with_sbom.delay()
            return Response({
                'message': 'Mass rescan of all images with SBOM started',
                'task_id': result.id
            })
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )
