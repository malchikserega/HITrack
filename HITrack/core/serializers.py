from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from drf_spectacular.utils import extend_schema_field
from .models import Repository, RepositoryTag, Image, Component, ComponentVersion, Vulnerability, ComponentVersionVulnerability, Release, RepositoryTagRelease


class ComponentListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Component
        fields = [
            'uuid', 'name', 'type', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'uuid']


class ComponentVersionVulnerabilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = ComponentVersionVulnerability
        fields = ['fixable', 'fix']


class VulnerabilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Vulnerability
        fields = ['uuid', 'vulnerability_id', 'vulnerability_type', 'severity', 'description', 'epss', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at', 'uuid']


class ComponentVersionSerializer(serializers.ModelSerializer):
    component = ComponentListSerializer(read_only=True)
    vulnerabilities = serializers.SerializerMethodField()
    used_count = serializers.SerializerMethodField()

    class Meta:
        model = ComponentVersion
        fields = ['uuid', 'version', 'component', 'images', 'vulnerabilities', 'used_count', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at', 'uuid']

    @extend_schema_field(serializers.ListField(child=VulnerabilitySerializer()))
    def get_vulnerabilities(self, obj):
        # Get vulnerabilities with their fix information through the through model
        vulns = []
        for cvv in obj.componentversionvulnerability_set.select_related('vulnerability').all():
            vuln_data = VulnerabilitySerializer(cvv.vulnerability).data
            vuln_data['fixable'] = cvv.fixable
            vuln_data['fix'] = cvv.fix
            vulns.append(vuln_data)
        return vulns

    @extend_schema_field(serializers.IntegerField())
    def get_used_count(self, obj):
        return obj.images.count()


class ComponentSerializer(serializers.ModelSerializer):
    versions = ComponentVersionSerializer(many=True, read_only=True)

    class Meta:
        model = Component
        fields = [
            'uuid', 'name', 'type', 'purl', 'cpes',
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

    class Meta:
        model = Image
        fields = [
            'uuid', 'name', 'digest', 'scan_status',
            'findings', 'unique_findings', 'severity_counts', 'components_count',
            'fully_fixable_components_count',
            'fixable_findings', 'fixable_unique_findings', 'fixable_severity_counts',
            'unique_severity_counts', 'fixable_unique_severity_counts',
            'created_at', 'updated_at'
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
        from core.models import ComponentVersionVulnerability
        return ComponentVersionVulnerability.objects.filter(
            component_version__images=obj
        ).count()

    @extend_schema_field(serializers.IntegerField())
    def get_unique_findings(self, obj):
        # Count unique vulnerabilities through ComponentVersionVulnerability
        from core.models import ComponentVersionVulnerability
        return ComponentVersionVulnerability.objects.filter(
            component_version__images=obj
        ).values('vulnerability').distinct().count()

    @extend_schema_field(serializers.DictField(child=serializers.IntegerField()))
    def get_severity_counts(self, obj):
        from collections import Counter
        from core.models import ComponentVersionVulnerability
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
        from core.models import ComponentVersionVulnerability
        qs = ComponentVersionVulnerability.objects.filter(
            component_version__images=obj,
            fixable=True
        ).values_list('vulnerability__severity', flat=True)
        severities = [s.upper() if s else 'UNKNOWN' for s in qs]
        counter = Counter(severities)
        all_sevs = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'UNKNOWN']
        return {sev: counter.get(sev, 0) for sev in all_sevs}

    @extend_schema_field(serializers.DictField(child=serializers.IntegerField()))
    def get_unique_severity_counts(self, obj):
        from collections import Counter
        from core.models import ComponentVersionVulnerability
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
        from core.models import ComponentVersionVulnerability
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


class ImageListSerializer(serializers.ModelSerializer):
    has_sbom = serializers.SerializerMethodField()
    findings = serializers.SerializerMethodField()
    unique_findings = serializers.SerializerMethodField()
    components_count = serializers.SerializerMethodField()

    class Meta:
        model = Image
        fields = ['uuid', 'name', 'digest', 'scan_status', 'has_sbom', 'findings', 'unique_findings', 'components_count', 'updated_at']
        read_only_fields = ['uuid', 'updated_at']

    @extend_schema_field(serializers.BooleanField())
    def get_has_sbom(self, obj):
        return bool(obj.sbom_data)

    @extend_schema_field(serializers.IntegerField())
    def get_findings(self, obj):
        # Count only vulnerabilities that are linked through ComponentVersionVulnerability
        from core.models import ComponentVersionVulnerability
        return ComponentVersionVulnerability.objects.filter(
            component_version__images=obj
        ).count()

    @extend_schema_field(serializers.IntegerField())
    def get_unique_findings(self, obj):
        # Count unique vulnerabilities through ComponentVersionVulnerability
        from core.models import ComponentVersionVulnerability
        return ComponentVersionVulnerability.objects.filter(
            component_version__images=obj
        ).values('vulnerability').distinct().count()

    @extend_schema_field(serializers.IntegerField())
    def get_components_count(self, obj):
        return obj.component_versions.count()


class TagImageShortSerializer(serializers.ModelSerializer):
    findings = serializers.SerializerMethodField()
    components_count = serializers.SerializerMethodField()

    class Meta:
        model = Image
        fields = ['uuid', 'findings', 'components_count', 'name']

    @extend_schema_field(serializers.IntegerField())
    def get_findings(self, obj):
        # Count only vulnerabilities that are linked through ComponentVersionVulnerability
        from core.models import ComponentVersionVulnerability
        return ComponentVersionVulnerability.objects.filter(
            component_version__images=obj
        ).count()

    @extend_schema_field(serializers.IntegerField())
    def get_components_count(self, obj):
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
        """Get releases for this repository tag"""
        releases = obj.releases.all()
        return [
            {
                'uuid': str(release.release.uuid),
                'name': release.release.name,
                'description': release.release.description
            }
            for release in releases
        ]

    class Meta:
        model = RepositoryTag
        fields = ['uuid', 'tag', 'repository', 'images', 'created_at', 'updated_at', 'vulnerabilities_count', 'processing_status', 'findings', 'components', 'releases']
        read_only_fields = ['created_at', 'updated_at', 'uuid']

    @extend_schema_field(serializers.IntegerField())
    def get_vulnerabilities_count(self, obj):
        from core.models import Vulnerability
        return Vulnerability.objects.filter(
            component_versions__images__repository_tags=obj
        ).distinct().count()

    @extend_schema_field(serializers.IntegerField())
    def get_findings(self, obj):
        # Count only vulnerabilities that are linked through ComponentVersionVulnerability
        from core.models import ComponentVersionVulnerability
        return ComponentVersionVulnerability.objects.filter(
            component_version__images__repository_tags=obj
        ).count()

    @extend_schema_field(serializers.IntegerField())
    def get_components(self, obj):
        # Sum of all components_count across images
        return sum(img.component_versions.count() for img in obj.images.all())


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


class RepositoryListSerializer(serializers.ModelSerializer):
    tag_count = serializers.SerializerMethodField()

    class Meta:
        model = Repository
        fields = ['uuid', 'name', 'url', 'repository_type', 'tag_count', 'created_at', 'updated_at']
        read_only_fields = ['uuid', 'created_at', 'updated_at']

    @extend_schema_field(serializers.IntegerField())
    def get_tag_count(self, obj):
        return obj.tags.count()


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
        # Count only vulnerabilities that are linked through ComponentVersionVulnerability
        from core.models import ComponentVersionVulnerability
        return ComponentVersionVulnerability.objects.filter(
            component_version__images__repository_tags=obj
        ).count()

    @extend_schema_field(serializers.IntegerField())
    def get_components(self, obj):
        return sum(img.component_versions.count() for img in obj.images.all())

    def get_releases(self, obj):
        """Get releases for this repository tag"""
        releases = obj.releases.all()
        return [
            {
                'uuid': str(release.release.uuid),
                'name': release.release.name,
                'description': release.release.description
            }
            for release in releases
        ]


class ComponentShortSerializer(serializers.ModelSerializer):
    class Meta:
        model = Component
        fields = ['uuid', 'name', 'type']
        read_only_fields = ['uuid']


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
