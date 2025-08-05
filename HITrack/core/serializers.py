from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from drf_spectacular.utils import extend_schema_field
from .models import Repository, RepositoryTag, Image, Component, ComponentVersion, Vulnerability, ComponentVersionVulnerability, Release, RepositoryTagRelease, VulnerabilityDetails


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
            'cisa_kev_notes', 'cisa_kev_cwes', 'last_updated', 'data_source'
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

    class Meta:
        model = Vulnerability
        fields = [
            'uuid', 'vulnerability_id', 'vulnerability_type', 'severity', 'description',
            'epss', 'has_details', 'exploit_available', 'cisa_kev', 'created_at', 'updated_at'
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


class ComponentVersionVulnerabilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = ComponentVersionVulnerability
        fields = ['fixable', 'fix']


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
        # Get vulnerabilities through ComponentVersionVulnerability
        vulnerabilities = []
        for cvv in obj.component_versions.through.objects.filter(
            componentversion__images=obj
        ).select_related('vulnerability').all():
            vuln_data = VulnerabilitySerializer(cvv.vulnerability).data
            vuln_data['fixable'] = cvv.fixable
            vuln_data['fix'] = cvv.fix
            vulnerabilities.append(vuln_data)
        return vulnerabilities

    @extend_schema_field(serializers.IntegerField())
    def get_findings(self, obj):
        # Count only vulnerabilities that are linked through ComponentVersionVulnerability
        return obj.component_versions.through.objects.filter(
            componentversion__images=obj
        ).count()

    @extend_schema_field(serializers.IntegerField())
    def get_unique_findings(self, obj):
        # Count unique vulnerabilities through ComponentVersionVulnerability
        return obj.component_versions.through.objects.filter(
            componentversion__images=obj
        ).values('vulnerability').distinct().count()

    @extend_schema_field(serializers.DictField(child=serializers.IntegerField()))
    def get_severity_counts(self, obj):
        # Count vulnerabilities by severity through ComponentVersionVulnerability
        severity_counts = {}
        for cvv in obj.component_versions.through.objects.filter(
            componentversion__images=obj
        ).select_related('vulnerability').all():
            severity = cvv.vulnerability.severity
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
        return severity_counts

    @extend_schema_field(serializers.IntegerField())
    def get_components_count(self, obj):
        # Return the number of unique component versions linked to this image
        return obj.component_versions.count()

    @extend_schema_field(serializers.IntegerField())
    def get_fully_fixable_components_count(self, obj):
        # Count components that have all vulnerabilities fixable
        fixable_components = 0
        for component_version in obj.component_versions.all():
            if component_version.componentversionvulnerability_set.filter(fixable=False).count() == 0:
                fixable_components += 1
        return fixable_components

    @extend_schema_field(serializers.IntegerField())
    def get_fixable_findings(self, obj):
        # All fixable vulnerabilities (including duplicates by components)
        return obj.component_versions.through.objects.filter(
            componentversion__images=obj,
            fixable=True
        ).count()

    @extend_schema_field(serializers.IntegerField())
    def get_fixable_unique_findings(self, obj):
        # Unique fixable vulnerabilities
        return obj.component_versions.through.objects.filter(
            componentversion__images=obj,
            fixable=True
        ).values('vulnerability').distinct().count()

    @extend_schema_field(serializers.DictField(child=serializers.IntegerField()))
    def get_fixable_severity_counts(self, obj):
        # Count fixable vulnerabilities by severity
        severity_counts = {}
        for cvv in obj.component_versions.through.objects.filter(
            componentversion__images=obj,
            fixable=True
        ).select_related('vulnerability').all():
            severity = cvv.vulnerability.severity
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
        return severity_counts

    @extend_schema_field(serializers.DictField(child=serializers.IntegerField()))
    def get_unique_severity_counts(self, obj):
        # Count unique vulnerabilities by severity
        severity_counts = {}
        for cvv in obj.component_versions.through.objects.filter(
            componentversion__images=obj
        ).select_related('vulnerability').values('vulnerability__severity').distinct():
            severity = cvv['vulnerability__severity']
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
        return severity_counts

    @extend_schema_field(serializers.DictField(child=serializers.IntegerField()))
    def get_fixable_unique_severity_counts(self, obj):
        # Count unique fixable vulnerabilities by severity
        severity_counts = {}
        for cvv in obj.component_versions.through.objects.filter(
            componentversion__images=obj,
            fixable=True
        ).select_related('vulnerability').values('vulnerability__severity').distinct():
            severity = cvv['vulnerability__severity']
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
        return severity_counts


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
        return obj.has_sbom

    @extend_schema_field(serializers.IntegerField())
    def get_findings(self, obj):
        # Count only vulnerabilities that are linked through ComponentVersionVulnerability
        return obj.component_versions.through.objects.filter(
            componentversion__images=obj
        ).count()

    @extend_schema_field(serializers.IntegerField())
    def get_unique_findings(self, obj):
        # Count unique vulnerabilities through ComponentVersionVulnerability
        return obj.component_versions.through.objects.filter(
            componentversion__images=obj
        ).values('vulnerability').distinct().count()

    @extend_schema_field(serializers.IntegerField())
    def get_components_count(self, obj):
        # Return the number of unique component versions linked to this image
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
        return obj.component_versions.through.objects.filter(
            componentversion__images=obj
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
        for rtr in obj.repositorytagrelease_set.select_related('release').all():
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
            for cvv in image.component_versions.through.objects.filter(
                componentversion__images=image
            ).values_list('vulnerability_id', flat=True):
                vulnerability_ids.add(cvv)
        return len(vulnerability_ids)

    @extend_schema_field(serializers.IntegerField())
    def get_findings(self, obj):
        # Count only vulnerabilities that are linked through ComponentVersionVulnerability
        total_findings = 0
        for image in obj.images.all():
            total_findings += image.component_versions.through.objects.filter(
                componentversion__images=image
            ).count()
        return total_findings

    @extend_schema_field(serializers.IntegerField())
    def get_components(self, obj):
        # Sum of all components_count across images
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
        # Count only vulnerabilities that are linked through ComponentVersionVulnerability
        total_findings = 0
        for image in obj.images.all():
            total_findings += image.component_versions.through.objects.filter(
                componentversion__images=image
            ).count()
        return total_findings

    @extend_schema_field(serializers.IntegerField())
    def get_components(self, obj):
        # Sum of all components_count across images
        total_components = 0
        for image in obj.images.all():
            total_components += image.component_versions.count()
        return total_components

    def get_releases(self, obj):
        releases = []
        for rtr in obj.repositorytagrelease_set.select_related('release').all():
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
        return obj.has_sbom


class ReleaseSerializer(serializers.ModelSerializer):
    repository_tags_count = serializers.SerializerMethodField()

    class Meta:
        model = Release
        fields = ['uuid', 'name', 'description', 'repository_tags_count', 'created_at']
        read_only_fields = ['created_at', 'uuid']
        extra_kwargs = {
            'name': {
                'validators': [UniqueValidator(queryset=Release.objects.all(), lookup='iexact')]
            }
        }

    @extend_schema_field(serializers.IntegerField())
    def get_repository_tags_count(self, obj):
        return obj.repository_tags.count()

    def validate_name(self, value):
        # Case-insensitive unique validation
        if Release.objects.filter(name__iexact=value).exists():
            raise serializers.ValidationError("A release with this name already exists.")
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