from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from drf_spectacular.utils import extend_schema_field
from .models import Repository, RepositoryTag, Image, Component, ComponentVersion, Vulnerability, ComponentVersionVulnerability, Release, RepositoryTagRelease, VulnerabilityDetails, ComponentLocation
# Celery Task Serializers
from django_celery_results.models import TaskResult
from django_celery_beat.models import PeriodicTask, IntervalSchedule, CrontabSchedule
from datetime import datetime
import json

class ComponentLocationSerializer(serializers.ModelSerializer):
    """Serializer for component location information"""
    class Meta:
        model = ComponentLocation
        fields = [
            'uuid', 'path', 'layer_id', 'access_path', 'evidence_type', 
            'annotations', 'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'created_at', 'updated_at']


class VulnerabilityDetailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = VulnerabilityDetails
        fields = [
            'uuid', 'cve_details_score', 'cve_details_severity', 'cve_details_published_date',
            'cve_details_updated_date', 'cve_details_summary', 'cve_details_references',
            'exploit_available', 'exploit_public', 'exploit_verified', 'exploit_links',
            'cisa_kev_known_exploited', 'cisa_kev_date_added', 'cisa_kev_vendor_project',
            'cisa_kev_product', 'cisa_kev_vulnerability_name', 'cisa_kev_short_description',
            'cisa_kev_required_action', 'cisa_kev_due_date', 'cisa_kev_ransomware_use',
            'cisa_kev_notes', 'cisa_kev_cwes', 
            'exploit_db_available', 'exploit_db_verified', 'exploit_db_count', 
            'exploit_db_verified_count', 'exploit_db_working_count', 'exploit_db_links',
            'last_updated', 'data_source',
            'epss_score', 'epss_percentile', 'epss_date', 'epss_data_source', 'epss_last_updated'
        ]
        read_only_fields = ['uuid', 'last_updated']


class VulnerabilitySerializer(serializers.ModelSerializer):
    details = VulnerabilityDetailsSerializer(read_only=True)
    has_details = serializers.SerializerMethodField()

    class Meta:
        model = Vulnerability
        fields = [
            'uuid', 'vulnerability_id', 'vulnerability_type', 'severity', 'description', 
            'epss', 'details', 'has_details', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'uuid']

    @extend_schema_field(serializers.BooleanField())
    def get_has_details(self, obj):
        try:
            return bool(obj.details)
        except VulnerabilityDetails.DoesNotExist:
            return False


class VulnerabilityListSerializer(serializers.ModelSerializer):
    has_details = serializers.SerializerMethodField()
    exploit_available = serializers.SerializerMethodField()
    cisa_kev = serializers.SerializerMethodField()
    details = VulnerabilityDetailsSerializer(read_only=True)

    class Meta:
        model = Vulnerability
        fields = [
            'uuid', 'vulnerability_id', 'vulnerability_type', 'severity', 'description',
            'epss', 'has_details', 'exploit_available', 'cisa_kev', 'details', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'uuid']

    @extend_schema_field(serializers.BooleanField())
    def get_has_details(self, obj):
        try:
            return bool(obj.details)
        except VulnerabilityDetails.DoesNotExist:
            return False

    @extend_schema_field(serializers.BooleanField())
    def get_exploit_available(self, obj):
        try:
            details = obj.details
            return bool(details.exploit_available) if details else False
        except VulnerabilityDetails.DoesNotExist:
            return False

    @extend_schema_field(serializers.BooleanField())
    def get_cisa_kev(self, obj):
        try:
            details = obj.details
            return bool(details.cisa_kev_known_exploited) if details else False
        except VulnerabilityDetails.DoesNotExist:
            return False


class ComponentListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Component
        fields = [
            'uuid', 'name', 'type', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'uuid']


class ComponentDetailOptimizedSerializer(serializers.ModelSerializer):
    """Optimized serializer for component detail view - returns only basic component info"""
    total_images = serializers.SerializerMethodField()
    versions_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Component
        fields = ['uuid', 'name', 'type', 'total_images', 'versions_count', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at', 'uuid']
    
    @extend_schema_field(serializers.IntegerField())
    def get_total_images(self, obj):
        # Get unique images across all versions of this component
        from .models import Image
        
        # Get all images that contain any version of this component
        # Using correct related name: component_versions
        images_qs = Image.objects.filter(
            component_versions__component=obj
        ).distinct()
        
        return images_qs.count()
    
    @extend_schema_field(serializers.IntegerField())
    def get_versions_count(self, obj):
        return obj.versions.count()


class ComponentVersionOptimizedSerializer(serializers.ModelSerializer):
    """Optimized serializer for component versions list - excludes heavy fields"""
    vulnerabilities_count = serializers.IntegerField(read_only=True)
    used_count = serializers.SerializerMethodField()

    class Meta:
        model = ComponentVersion
        fields = ['uuid', 'version', 'vulnerabilities_count', 'used_count', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at', 'uuid']

    @extend_schema_field(serializers.IntegerField())
    def get_used_count(self, obj):
        # Use annotated field if available, otherwise count
        if hasattr(obj, 'images_count'):
            return obj.images_count
        return obj.images.count()





class VulnerabilityShortSerializer(serializers.ModelSerializer):
    """Optimized serializer for vulnerabilities in component-versions context"""
    class Meta:
        model = Vulnerability
        fields = ['uuid', 'vulnerability_id', 'severity', 'description']
        read_only_fields = ['uuid']


class ImageShortSerializer(serializers.ModelSerializer):
    """Short serializer for images in component-versions context"""
    class Meta:
        model = Image
        fields = ['uuid', 'name', 'digest']
        read_only_fields = ['uuid']


class ComponentVersionVulnerabilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = ComponentVersionVulnerability
        fields = ['fixable', 'fix']


class ComponentVersionSerializer(serializers.ModelSerializer):
    component = ComponentListSerializer(read_only=True)
    vulnerabilities = serializers.SerializerMethodField()
    vulnerabilities_count = serializers.SerializerMethodField()
    used_count = serializers.SerializerMethodField()
    locations = serializers.SerializerMethodField()
    images = serializers.SerializerMethodField()

    class Meta:
        model = ComponentVersion
        fields = ['uuid', 'version', 'component', 'images', 'vulnerabilities', 'vulnerabilities_count', 'used_count', 'locations', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at', 'uuid']

    @extend_schema_field(serializers.ListField(child=VulnerabilityShortSerializer()))
    def get_vulnerabilities(self, obj):
        # Get vulnerabilities with their fix information through the through model
        # Using optimized serializer that returns uuid, vulnerability_id, severity, and description
        vulns = []
        for cvv in obj.componentversionvulnerability_set.select_related('vulnerability').all():
            vuln_data = VulnerabilityShortSerializer(cvv.vulnerability).data
            vuln_data['fixable'] = cvv.fixable
            vuln_data['fix'] = cvv.fix
            vulns.append(vuln_data)
        return vulns

    @extend_schema_field(serializers.IntegerField())
    def get_vulnerabilities_count(self, obj):
        return obj.vulnerabilities.count()

    @extend_schema_field(serializers.IntegerField())
    def get_used_count(self, obj):
        return obj.images.count()

    @extend_schema_field(serializers.ListField(child=ImageShortSerializer()))
    def get_images(self, obj):
        # Get images with full information for this component version
        images = obj.images.all()
        return ImageShortSerializer(images, many=True).data

    @extend_schema_field(serializers.ListField(child=ComponentLocationSerializer()))
    def get_locations(self, obj):
        # Get locations for this component version
        locations = ComponentLocation.objects.filter(component_version=obj).select_related('image')
        return ComponentLocationSerializer(locations, many=True).data


class ComponentSerializer(serializers.ModelSerializer):
    versions = ComponentVersionSerializer(many=True, read_only=True)

    class Meta:
        model = Component
        fields = [
            'uuid', 'name', 'type',
            'versions', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'uuid']


class ImageSerializer(serializers.ModelSerializer):
    findings = serializers.SerializerMethodField()
    unique_findings = serializers.SerializerMethodField()
    severity_counts = serializers.SerializerMethodField()
    components_count = serializers.SerializerMethodField()
    fully_fixable_components_count = serializers.SerializerMethodField()
    fixable_findings = serializers.SerializerMethodField()
    fixable_unique_findings = serializers.SerializerMethodField()
    fixable_severity_counts = serializers.SerializerMethodField()
    unique_severity_counts = serializers.SerializerMethodField()
    fixable_unique_severity_counts = serializers.SerializerMethodField()
    has_sbom = serializers.SerializerMethodField()
    has_grype = serializers.SerializerMethodField()
    repository_info = serializers.SerializerMethodField()

    class Meta:
        model = Image
        fields = [
            'uuid', 'name', 'digest', 'scan_status',
            'findings', 'unique_findings', 'severity_counts', 'components_count',
            'fully_fixable_components_count',
            'fixable_findings', 'fixable_unique_findings', 'fixable_severity_counts',
            'unique_severity_counts', 'fixable_unique_severity_counts',
            'has_sbom', 'has_grype',
            'repository_info', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'uuid']

    def get_vulnerabilities(self, obj):
        """
        Get all vulnerabilities for an image through its component versions.
        Returns a list of vulnerability dictionaries with fix information.
        """
        vulnerabilities = []
        for cv in obj.component_versions.all():
            for cvv in cv.componentversionvulnerability_set.select_related('vulnerability').all():
                vuln_data = VulnerabilitySerializer(cvv.vulnerability).data
                vuln_data['fixable'] = cvv.fixable
                vuln_data['fix'] = cvv.fix
                vulnerabilities.append(vuln_data)
        return vulnerabilities

    @extend_schema_field(serializers.IntegerField())
    def get_findings(self, obj):
        # Count only vulnerabilities that are linked through ComponentVersionVulnerability
        return ComponentVersionVulnerability.objects.filter(
            component_version__images=obj
        ).count()

    @extend_schema_field(serializers.IntegerField())
    def get_unique_findings(self, obj):
        # Count unique vulnerabilities through ComponentVersionVulnerability
        return ComponentVersionVulnerability.objects.filter(
            component_version__images=obj
        ).values('vulnerability').distinct().count()

    @extend_schema_field(serializers.DictField(child=serializers.IntegerField()))
    def get_severity_counts(self, obj):
        from collections import Counter
        # Get all vulnerabilities related to this image through ComponentVersionVulnerability
        qs = ComponentVersionVulnerability.objects.filter(
            component_version__images=obj
        ).values_list('vulnerability__severity', flat=True)
        # qs may contain None, filter and convert to uppercase
        severities = [s.upper() if s else 'UNKNOWN' for s in qs]
        counter = Counter(severities)
        # Ensure all keys are present
        all_sevs = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'UNKNOWN']
        return {sev: counter.get(sev, 0) for sev in all_sevs}

    @extend_schema_field(serializers.IntegerField())
    def get_components_count(self, obj):
        # Return the number of unique component versions linked to this image
        return obj.component_versions.count()

    @extend_schema_field(serializers.IntegerField())
    def get_fully_fixable_components_count(self, obj):
        count = 0
        for cv in obj.component_versions.all():
            vulns = cv.componentversionvulnerability_set.all()
            if vulns.exists() and all(v.fixable for v in vulns):
                count += 1
        return count

    @extend_schema_field(serializers.IntegerField())
    def get_fixable_findings(self, obj):
        # All fixable vulnerabilities (including duplicates by components)
        fixable_vulns = [v for v in self.get_vulnerabilities(obj) if v['fixable']]
        return len(fixable_vulns)

    @extend_schema_field(serializers.IntegerField())
    def get_fixable_unique_findings(self, obj):
        # Unique fixable vulnerabilities
        fixable_vulns = [v for v in self.get_vulnerabilities(obj) if v['fixable']]
        unique_fixable_vulns = list({v['vulnerability_id']: v for v in fixable_vulns}.values())
        return len(unique_fixable_vulns)

    @extend_schema_field(serializers.DictField(child=serializers.IntegerField()))
    def get_fixable_severity_counts(self, obj):
        from collections import Counter
        qs = ComponentVersionVulnerability.objects.filter(
            component_version__images=obj,
            fixable=True
        ).values_list('vulnerability__uuid', 'vulnerability__severity')
        seen = set()
        severities = []
        for uuid, sev in qs:
            if uuid and uuid not in seen:
                seen.add(uuid)
                severities.append(sev.upper() if sev else 'UNKNOWN')
        counter = Counter(severities)
        all_sevs = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'UNKNOWN']
        return {sev: counter.get(sev, 0) for sev in all_sevs}

    @extend_schema_field(serializers.DictField(child=serializers.IntegerField()))
    def get_unique_severity_counts(self, obj):
        from collections import Counter
        qs = ComponentVersionVulnerability.objects.filter(
            component_version__images=obj
        ).values_list('vulnerability__uuid', 'vulnerability__severity')
        seen = set()
        severities = []
        for uuid, sev in qs:
            if uuid and uuid not in seen:
                seen.add(uuid)
                severities.append(sev.upper() if sev else 'UNKNOWN')
        counter = Counter(severities)
        all_sevs = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'UNKNOWN']
        return {sev: counter.get(sev, 0) for sev in all_sevs}

    @extend_schema_field(serializers.DictField(child=serializers.IntegerField()))
    def get_fixable_unique_severity_counts(self, obj):
        from collections import Counter
        qs = ComponentVersionVulnerability.objects.filter(
            component_version__images=obj,
            fixable=True
        ).values_list('vulnerability__uuid', 'vulnerability__severity')
        seen = set()
        severities = []
        for uuid, sev in qs:
            if uuid and uuid not in seen:
                seen.add(uuid)
                severities.append(sev.upper() if sev else 'UNKNOWN')
        counter = Counter(severities)
        all_sevs = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'UNKNOWN']
        return {sev: counter.get(sev, 0) for sev in all_sevs}

    @extend_schema_field(serializers.BooleanField())
    def get_has_sbom(self, obj):
        return bool(obj.sbom_data)

    @extend_schema_field(serializers.BooleanField())
    def get_has_grype(self, obj):
        return bool(obj.grype_data)

    @extend_schema_field(serializers.DictField())
    def get_repository_info(self, obj):
        # Get repository and tag information for this image
        # Use prefetched data if available
        if hasattr(obj, 'repository_tags'):
            tags = obj.repository_tags.all()
        else:
            tags = obj.repository_tags.all()
        
        if tags.exists():
            tag = tags.first()
            return {
                'repository_name': tag.repository.name,
                'repository_uuid': tag.repository.uuid,
                'tag': tag.tag,
                'tag_uuid': tag.uuid,
                'repository_type': tag.repository.repository_type
            }
        else:
            # Try to extract repository info from image name if no tags found
            if ':' in obj.name:
                # Format: registry/repo:tag
                parts = obj.name.split(':')
                if len(parts) == 2:
                    repo_part = parts[0]
                    tag_part = parts[1]
                    # Extract repository name from repo part
                    repo_parts = repo_part.split('/')
                    if len(repo_parts) >= 2:
                        repo_name = repo_parts[-1]  # Last part is repository name
                        return {
                            'repository_name': repo_name,
                            'repository_uuid': '',  # Unknown UUID
                            'tag': tag_part,
                            'tag_uuid': '',  # Unknown UUID
                            'repository_type': 'docker'
                        }
        return None


class ImageListSerializer(serializers.ModelSerializer):
    has_sbom = serializers.SerializerMethodField()
    has_grype = serializers.SerializerMethodField()
    findings = serializers.SerializerMethodField()
    unique_findings = serializers.SerializerMethodField()
    components_count = serializers.SerializerMethodField()
    repository_info = serializers.SerializerMethodField()

    class Meta:
        model = Image
        fields = ['uuid', 'name', 'digest', 'scan_status', 'has_sbom', 'has_grype', 'findings', 'unique_findings', 'components_count', 'repository_info', 'updated_at']
        read_only_fields = ['uuid', 'updated_at']

    @extend_schema_field(serializers.BooleanField())
    def get_has_sbom(self, obj):
        return bool(obj.sbom_data)

    @extend_schema_field(serializers.BooleanField())
    def get_has_grype(self, obj):
        return bool(obj.grype_data)

    @extend_schema_field(serializers.IntegerField())
    def get_findings(self, obj):
        # Use annotated field if available, otherwise fallback to query
        if hasattr(obj, 'findings_count'):
            return obj.findings_count
        return ComponentVersionVulnerability.objects.filter(
            component_version__images=obj
        ).count()

    @extend_schema_field(serializers.IntegerField())
    def get_unique_findings(self, obj):
        # Use annotated field if available, otherwise fallback to query
        if hasattr(obj, 'unique_findings_count'):
            return obj.unique_findings_count
        return ComponentVersionVulnerability.objects.filter(
            component_version__images=obj
        ).values('vulnerability').distinct().count()

    @extend_schema_field(serializers.IntegerField())
    def get_components_count(self, obj):
        # Use annotated field if available, otherwise fallback to query
        if hasattr(obj, 'components_count'):
            return obj.components_count
        return obj.component_versions.count()

    @extend_schema_field(serializers.DictField())
    def get_repository_info(self, obj):
        # Get repository and tag information for this image
        # Use prefetched data if available
        if hasattr(obj, 'repository_tags'):
            tags = obj.repository_tags.all()
        else:
            tags = obj.repository_tags.all()
        
        if tags.exists():
            tag = tags.first()
            return {
                'repository_name': tag.repository.name,
                'tag': tag.tag,
                'repository_type': tag.repository.repository_type
            }
        return None


class TagImageShortSerializer(serializers.ModelSerializer):
    findings = serializers.SerializerMethodField()
    components_count = serializers.SerializerMethodField()

    class Meta:
        model = Image
        fields = ['uuid', 'findings', 'components_count', 'name']

    @extend_schema_field(serializers.IntegerField())
    def get_findings(self, obj):
        # Count only vulnerabilities that are linked through ComponentVersionVulnerability
        return ComponentVersionVulnerability.objects.filter(
            component_version__images=obj
        ).count()

    @extend_schema_field(serializers.IntegerField())
    def get_components_count(self, obj):
        # Return the number of unique component versions linked to this image
        return obj.component_versions.count()


class RepositoryTagSerializer(serializers.ModelSerializer):
    images = TagImageShortSerializer(many=True, read_only=True)
    vulnerabilities_count = serializers.SerializerMethodField()
    findings = serializers.SerializerMethodField()
    components = serializers.SerializerMethodField()
    releases = serializers.SerializerMethodField()

    class Meta:
        model = RepositoryTag
        fields = ['uuid', 'tag', 'repository', 'images', 'created_at', 'updated_at', 'vulnerabilities_count', 'processing_status', 'findings', 'components', 'releases']
        read_only_fields = ['created_at', 'updated_at', 'uuid']

    def get_releases(self, obj):
        releases = []
        for rtr in obj.releases.select_related('release').all():
            releases.append({
                'uuid': rtr.release.uuid,
                'name': rtr.release.name,
                'description': rtr.release.description,
                'added_at': rtr.added_at
            })
        return releases

    @extend_schema_field(serializers.IntegerField())
    def get_vulnerabilities_count(self, obj):
        # Count unique vulnerabilities across all images in this tag
        vulnerability_ids = set()
        for image in obj.images.all():
            # Get vulnerabilities through ComponentVersionVulnerability
            for cvv in ComponentVersionVulnerability.objects.filter(
                component_version__images=image
            ).values_list('vulnerability__vulnerability_id', flat=True):
                vulnerability_ids.add(cvv)
        return len(vulnerability_ids)

    @extend_schema_field(serializers.IntegerField())
    def get_findings(self, obj):
        # Count all vulnerabilities across all images in this tag
        # Each image's vulnerabilities should be counted separately
        from .models import ComponentVersionVulnerability
        
        total_findings = 0
        for image in obj.images.all():
            total_findings += ComponentVersionVulnerability.objects.filter(
                component_version__images=image
            ).count()
        
        return total_findings

    @extend_schema_field(serializers.IntegerField())
    def get_components(self, obj):
        # Count all component versions across all images in this tag
        # Each image's components should be counted separately
        total_components = 0
        for image in obj.images.all():
            total_components += image.component_versions.count()
        
        return total_components


class RepositoryTagListSerializer(serializers.ModelSerializer):
    findings = serializers.SerializerMethodField()
    components = serializers.SerializerMethodField()
    releases = serializers.SerializerMethodField()

    class Meta:
        model = RepositoryTag
        fields = ['uuid', 'tag', 'created_at', 'updated_at', 'processing_status', 'findings', 'components', 'releases']
        read_only_fields = ['created_at', 'updated_at', 'uuid']

    @extend_schema_field(serializers.IntegerField())
    def get_findings(self, obj):
        # Count all vulnerabilities across all images in this tag
        # Each image's vulnerabilities should be counted separately
        from .models import ComponentVersionVulnerability
        
        total_findings = 0
        for image in obj.images.all():
            total_findings += ComponentVersionVulnerability.objects.filter(
                component_version__images=image
            ).count()
        
        return total_findings

    @extend_schema_field(serializers.IntegerField())
    def get_components(self, obj):
        # Count all component versions across all images in this tag
        # Each image's components should be counted separately
        total_components = 0
        for image in obj.images.all():
            total_components += image.component_versions.count()
        
        return total_components

    def get_releases(self, obj):
        releases = []
        for rtr in obj.releases.select_related('release').all():
            releases.append({
                'uuid': rtr.release.uuid,
                'name': rtr.release.name,
                'description': rtr.release.description,
                'added_at': rtr.added_at
            })
        return releases


class RepositorySerializer(serializers.ModelSerializer):
    tags = RepositoryTagSerializer(many=True, read_only=True)
    tag_count = serializers.SerializerMethodField()

    class Meta:
        model = Repository
        fields = ['uuid', 'name', 'url', 'repository_type', 'tags', 'tag_count', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at', 'uuid']

    @extend_schema_field(serializers.IntegerField())
    def get_tag_count(self, obj):
        return obj.tags.count()


class RepositoryDetailSerializer(serializers.ModelSerializer):
    """Optimized serializer for repository detail view - excludes heavy fields"""
    tag_count = serializers.SerializerMethodField()
    scan_status = serializers.CharField(read_only=True)
    last_scanned = serializers.DateTimeField(read_only=True)

    class Meta:
        model = Repository
        fields = [
            'uuid', 'name', 'url', 'repository_type', 'tag_count', 
            'scan_status', 'last_scanned', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'uuid']

    @extend_schema_field(serializers.IntegerField())
    def get_tag_count(self, obj):
        return obj.tags.count()


class RepositoryListSerializer(serializers.ModelSerializer):
    tag_count = serializers.SerializerMethodField()

    class Meta:
        model = Repository
        fields = ['uuid', 'name', 'url', 'repository_type', 'tag_count', 'created_at', 'updated_at']
        read_only_fields = ['uuid', 'created_at', 'updated_at']

    @extend_schema_field(serializers.IntegerField())
    def get_tag_count(self, obj):
        return obj.tags.count()


class ComponentShortSerializer(serializers.ModelSerializer):
    class Meta:
        model = Component
        fields = ['uuid', 'name', 'type']
        read_only_fields = ['uuid']


class ComponentVersionDetailOptimizedSerializer(serializers.ModelSerializer):
    """Optimized serializer for component version detail view"""
    component = ComponentShortSerializer(read_only=True)
    vulnerabilities_count = serializers.SerializerMethodField()
    used_count = serializers.SerializerMethodField()
    locations_count = serializers.SerializerMethodField()
    images = ImageShortSerializer(many=True, read_only=True)

    class Meta:
        model = ComponentVersion
        fields = [
            'uuid', 'version', 'component', 'images', 
            'vulnerabilities_count', 'used_count', 'locations_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'uuid']

    @extend_schema_field(serializers.IntegerField())
    def get_vulnerabilities_count(self, obj):
        # Use annotated field if available, otherwise count
        if hasattr(obj, 'vulnerabilities_count'):
            return obj.vulnerabilities_count
        return obj.vulnerabilities.count()

    @extend_schema_field(serializers.IntegerField())
    def get_used_count(self, obj):
        # Use annotated field if available, otherwise count
        if hasattr(obj, 'images_count'):
            return obj.images_count
        return obj.images.count()

    @extend_schema_field(serializers.IntegerField())
    def get_locations_count(self, obj):
        # Use annotated field if available, otherwise count
        if hasattr(obj, 'locations_count'):
            return obj.locations_count
        return obj.locations.count()


class ComponentVersionUltraOptimizedSerializer(serializers.ModelSerializer):
    """Ultra-optimized serializer for component version detail view - minimal data only"""
    component = ComponentShortSerializer(read_only=True)
    vulnerabilities_count = serializers.SerializerMethodField()
    used_count = serializers.SerializerMethodField()
    locations_count = serializers.SerializerMethodField()

    class Meta:
        model = ComponentVersion
        fields = [
            'uuid', 'version', 'component', 
            'vulnerabilities_count', 'used_count', 'locations_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'uuid']

    @extend_schema_field(serializers.IntegerField())
    def get_vulnerabilities_count(self, obj):
        if hasattr(obj, 'vulnerabilities_count'):
            return obj.vulnerabilities_count
        return obj.vulnerabilities.count()

    @extend_schema_field(serializers.IntegerField())
    def get_used_count(self, obj):
        if hasattr(obj, 'images_count'):
            return obj.images_count
        return obj.images.count()

    @extend_schema_field(serializers.IntegerField())
    def get_locations_count(self, obj):
        if hasattr(obj, 'locations_count'):
            return obj.locations_count
        return obj.locations.count()


class ComponentVersionListSerializer(serializers.ModelSerializer):
    component = ComponentShortSerializer(read_only=True)
    vulnerabilities_count = serializers.IntegerField(read_only=True)
    used_count = serializers.SerializerMethodField()

    class Meta:
        model = ComponentVersion
        fields = ['uuid', 'version', 'component', 'created_at', 'updated_at', 'vulnerabilities_count', 'used_count']
        read_only_fields = ['uuid', 'created_at', 'updated_at']

    def get_used_count(self, obj):
        return obj.images.count()


class HasACRRegistryResponseSerializer(serializers.Serializer):
    has_acr = serializers.BooleanField()


class ACRRegistrySerializer(serializers.Serializer):
    uuid = serializers.UUIDField()
    name = serializers.CharField()
    api_url = serializers.URLField()


class ListACRRegistriesResponseSerializer(serializers.Serializer):
    registries = ACRRegistrySerializer(many=True)


class StatsResponseSerializer(serializers.Serializer):
    repositories = serializers.IntegerField()
    images = serializers.IntegerField()
    vulnerabilities = serializers.IntegerField()
    components = serializers.IntegerField()


class JobAddRepositoriesRequestSerializer(serializers.Serializer):
    repositories = serializers.ListField(
        child=serializers.DictField(
            child=serializers.CharField()
        )
    )
    registry_uuid = serializers.UUIDField(required=False)


class JobAddRepositoriesResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    message = serializers.CharField()
    results = serializers.ListField(
        child=serializers.DictField(
            child=serializers.CharField()
        )
    )


class ImageDropdownSerializer(serializers.ModelSerializer):
    has_sbom = serializers.SerializerMethodField()

    class Meta:
        model = Image
        fields = ['uuid', 'name', 'has_sbom']

    def get_has_sbom(self, obj):
        return bool(obj.sbom_data)


class ReleaseSerializer(serializers.ModelSerializer):
    repository_tags_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Release
        fields = ['uuid', 'name', 'description', 'repository_tags_count', 'created_at']
        read_only_fields = ['created_at', 'uuid']
        extra_kwargs = {
            'name': {
                'validators': [
                    UniqueValidator(
                        queryset=Release.objects.all(),
                        message='Release with this name already exists.'
                    )
                ]
            }
        }
    
    def get_repository_tags_count(self, obj):
        return obj.repository_tags.count()
    
    def validate_name(self, value):
        # Case-insensitive unique validation
        if Release.objects.filter(name__iexact=value).exists():
            raise serializers.ValidationError('Release with this name already exists.')
        return value


class RepositoryTagReleaseSerializer(serializers.ModelSerializer):
    repository_tag = RepositoryTagSerializer(read_only=True)
    release = ReleaseSerializer(read_only=True)
    
    class Meta:
        model = RepositoryTagRelease
        fields = ['uuid', 'repository_tag', 'release', 'added_at']
        read_only_fields = ['added_at', 'uuid']


class ReleaseAssignmentSerializer(serializers.Serializer):
    release_id = serializers.UUIDField() 


class TaskResultSerializer(serializers.ModelSerializer):
    """Serializer for Celery task results"""
    task_name = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    result_summary = serializers.SerializerMethodField()
    duration = serializers.SerializerMethodField()
    created = serializers.DateTimeField(source='date_created')
    updated = serializers.DateTimeField(source='date_done')
    
    class Meta:
        model = TaskResult
        fields = [
            'task_id', 'task_name', 'status', 'result_summary', 
            'duration', 'created', 'updated', 'traceback'
        ]
    
    def get_task_name(self, obj):
        """Extract task name from task_id or result"""
        # First check if task_name is set and not None/empty
        if obj.task_name and obj.task_name != 'None' and obj.task_name.strip():
            return obj.task_name
        
        # Try to extract from result if available
        if obj.result:
            try:
                result_data = json.loads(obj.result)
                if isinstance(result_data, dict) and 'task_name' in result_data:
                    return result_data['task_name']
            except (json.JSONDecodeError, TypeError):
                pass
        
        # Try to extract from task_id or other fields
        if hasattr(obj, 'task_id') and obj.task_id:
            # Try to get task name from Celery registry
            try:
                from celery import current_app
                task_func = current_app.tasks.get(obj.task_id)
                if task_func:
                    return task_func.name
            except:
                pass
        
        # Try to extract from task_id by looking for known patterns
        if obj.task_id:
            # Check if it's a known task pattern
            if 'generate_sbom' in obj.task_id or 'sbom' in obj.task_id:
                return "Generate SBOM and Create Components"
            elif 'scan' in obj.task_id and 'grype' in obj.task_id:
                return "Scan Image with Grype"
            elif 'vulnerability' in obj.task_id and 'update' in obj.task_id:
                return "Update Vulnerability Details"
            elif 'process' in obj.task_id and 'tag' in obj.task_id:
                return "Process Single Tag"
            elif 'repository' in obj.task_id and 'scan' in obj.task_id:
                return "Scan Repository"
            elif 'parse' in obj.task_id and 'sbom' in obj.task_id:
                return "Parse SBOM and Create Components"
            elif 'update' in obj.task_id and 'component' in obj.task_id:
                return "Update Components Latest Versions"
            elif 'process' in obj.task_id and 'grype' in obj.task_id:
                return "Process Grype Scan Results"
            elif 'cleanup' in obj.task_id:
                return "Cleanup Old Vulnerability Data"
            elif 'cisa' in obj.task_id or 'kev' in obj.task_id:
                return "Update CISA KEV Vulnerabilities"
            elif 'test' in obj.task_id:
                return "Test Task"
            else:
                return f"Task-{obj.task_id[:8]}"
        
        return 'Unknown Task'
    
    def get_status(self, obj):
        """Get task status"""
        if obj.status == 'SUCCESS':
            return 'success'
        elif obj.status == 'FAILURE':
            return 'error'
        elif obj.status == 'PENDING':
            return 'pending'
        elif obj.status == 'STARTED':
            return 'in_process'
        else:
            return obj.status.lower()
    
    def get_result_summary(self, obj):
        """Get a summary of the result"""
        if not obj.result:
            return None
        
        try:
            result_data = json.loads(obj.result)
            if isinstance(result_data, dict):
                # Extract key information
                summary = {}
                if 'status' in result_data:
                    summary['status'] = result_data['status']
                if 'message' in result_data:
                    summary['message'] = result_data['message']
                if 'processed_items' in result_data:
                    summary['processed_items'] = result_data['processed_items']
                if 'errors' in result_data:
                    summary['errors'] = result_data['errors']
                return summary
            else:
                return str(result_data)[:200] + '...' if len(str(result_data)) > 200 else str(result_data)
        except (json.JSONDecodeError, TypeError):
            return str(obj.result)[:200] + '...' if len(str(obj.result)) > 200 else str(obj.result)
    
    def get_duration(self, obj):
        """Calculate task duration"""
        if obj.date_created and obj.date_done:
            duration = obj.date_done - obj.date_created
            return duration.total_seconds()
        return None

class TaskResultListSerializer(serializers.ModelSerializer):
    """Simplified serializer for task list"""
    task_name = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    result_summary = serializers.SerializerMethodField()
    duration = serializers.SerializerMethodField()
    created = serializers.DateTimeField(source='date_created')
    
    class Meta:
        model = TaskResult
        fields = ['task_id', 'task_name', 'status', 'result_summary', 'duration', 'created']
    
    def get_task_name(self, obj):
        # First check if task_name is set and not None/empty
        if obj.task_name and obj.task_name != 'None' and obj.task_name.strip():
            return obj.task_name
        
        # Try to extract from result if available
        if obj.result:
            try:
                result_data = json.loads(obj.result)
                if isinstance(result_data, dict) and 'task_name' in result_data:
                    return result_data['task_name']
            except (json.JSONDecodeError, TypeError):
                pass
        
        # Try to extract from task_id or other fields
        if hasattr(obj, 'task_id') and obj.task_id:
            # Try to get task name from Celery registry
            try:
                from celery import current_app
                task_func = current_app.tasks.get(obj.task_id)
                if task_func:
                    return task_func.name
            except:
                pass
        
        # Try to extract from task_id by looking for known patterns
        if obj.task_id:
            # Check if it's a known task pattern
            if 'generate_sbom' in obj.task_id or 'sbom' in obj.task_id:
                return "Generate SBOM and Create Components"
            elif 'scan' in obj.task_id and 'grype' in obj.task_id:
                return "Scan Image with Grype"
            elif 'vulnerability' in obj.task_id and 'update' in obj.task_id:
                return "Update Vulnerability Details"
            elif 'process' in obj.task_id and 'tag' in obj.task_id:
                return "Process Single Tag"
            elif 'repository' in obj.task_id and 'scan' in obj.task_id:
                return "Scan Repository"
            elif 'parse' in obj.task_id and 'sbom' in obj.task_id:
                return "Parse SBOM and Create Components"
            elif 'update' in obj.task_id and 'component' in obj.task_id:
                return "Update Components Latest Versions"
            elif 'process' in obj.task_id and 'grype' in obj.task_id:
                return "Process Grype Scan Results"
            elif 'cleanup' in obj.task_id:
                return "Cleanup Old Vulnerability Data"
            elif 'cisa' in obj.task_id or 'kev' in obj.task_id:
                return "Update CISA KEV Vulnerabilities"
            elif 'test' in obj.task_id:
                return "Test Task"
            else:
                return f"Task-{obj.task_id[:8]}"
        
        return 'Unknown Task'
    
    def get_status(self, obj):
        if obj.status == 'SUCCESS':
            return 'success'
        elif obj.status == 'FAILURE':
            return 'error'
        elif obj.status == 'PENDING':
            return 'pending'
        elif obj.status == 'STARTED':
            return 'in_process'
        else:
            return obj.status.lower()
    
    def get_result_summary(self, obj):
        """Get a summary of the result"""
        if not obj.result:
            return None
        
        try:
            result_data = json.loads(obj.result)
            if isinstance(result_data, dict):
                # Extract key information
                summary = {}
                if 'status' in result_data:
                    summary['status'] = result_data['status']
                if 'message' in result_data:
                    summary['message'] = result_data['message']
                if 'processed_items' in result_data:
                    summary['processed_items'] = result_data['processed_items']
                if 'errors' in result_data:
                    summary['errors'] = result_data['errors']
                return summary
            else:
                return str(result_data)[:100] + '...' if len(str(result_data)) > 100 else str(result_data)
        except (json.JSONDecodeError, TypeError):
            return str(obj.result)[:100] + '...' if len(str(obj.result)) > 100 else str(obj.result)
    
    def get_duration(self, obj):
        if obj.date_created and obj.date_done:
            duration = obj.date_done - obj.date_created
            return duration.total_seconds()
        return None

class PeriodicTaskSerializer(serializers.ModelSerializer):
    """Serializer for periodic tasks"""
    schedule_info = serializers.SerializerMethodField()
    next_run = serializers.SerializerMethodField()
    
    class Meta:
        model = PeriodicTask
        fields = [
            'id', 'name', 'task', 'enabled', 'schedule_info', 
            'next_run', 'last_run_at', 'total_run_count'
        ]
    
    def get_schedule_info(self, obj):
        """Get schedule information"""
        if obj.interval:
            return {
                'type': 'interval',
                'every': obj.interval.every,
                'period': obj.interval.period
            }
        elif obj.crontab:
            return {
                'type': 'crontab',
                'minute': obj.crontab.minute,
                'hour': obj.crontab.hour,
                'day_of_week': obj.crontab.day_of_week,
                'day_of_month': obj.crontab.day_of_month,
                'month_of_year': obj.crontab.month_of_year
            }
        return None
    
    def get_next_run(self, obj):
        """Get next run time"""
        try:
            return obj.schedule.next_run_at
        except:
            return None

class TaskStatisticsSerializer(serializers.Serializer):
    """Serializer for task statistics"""
    total_tasks = serializers.IntegerField()
    successful_tasks = serializers.IntegerField()
    failed_tasks = serializers.IntegerField()
    pending_tasks = serializers.IntegerField()
    running_tasks = serializers.IntegerField()
    average_duration = serializers.FloatField()
    recent_tasks = serializers.ListField(child=TaskResultListSerializer()) 