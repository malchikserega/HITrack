from rest_framework import serializers
from .models import Repository, RepositoryTag, Image, Component, ComponentVersion, Vulnerability, ComponentVersionVulnerability


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

    class Meta:
        model = ComponentVersion
        fields = ['uuid', 'version', 'component', 'images', 'vulnerabilities', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at', 'uuid']

    def get_vulnerabilities(self, obj):
        # Get vulnerabilities with their fix information through the through model
        vulns = []
        for cvv in obj.componentversionvulnerability_set.select_related('vulnerability').all():
            vuln_data = VulnerabilitySerializer(cvv.vulnerability).data
            vuln_data['fixable'] = cvv.fixable
            vuln_data['fix'] = cvv.fix
            vulns.append(vuln_data)
        return vulns


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

    def get_findings(self, obj):
        # Get all vulnerabilities through component versions
        return obj.component_versions.values('vulnerabilities').count()

    def get_unique_findings(self, obj):
        # Count unique vulnerabilities across all components
        return obj.component_versions.values('vulnerabilities').distinct().count()

    def get_severity_counts(self, obj):
        from collections import Counter
        # Get all vulnerabilities related to this image through component_versions
        qs = obj.component_versions.values_list('vulnerabilities__severity', flat=True)
        # qs may contain None, filter and convert to uppercase
        severities = [s.upper() if s else 'UNKNOWN' for s in qs]
        counter = Counter(severities)
        # Ensure all keys are present
        all_sevs = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'UNKNOWN']
        return {sev: counter.get(sev, 0) for sev in all_sevs}

    def get_components_count(self, obj):
        # Return the number of unique component versions linked to this image
        return obj.component_versions.count()

    def get_fully_fixable_components_count(self, obj):
        count = 0
        for cv in obj.component_versions.all():
            vulns = cv.componentversionvulnerability_set.all()
            if vulns.exists() and all(v.fixable for v in vulns):
                count += 1
        return count

    def get_fixable_findings(self, obj):
        # All fixable vulnerabilities (including duplicates by components)
        fixable_vulns = [v for v in self.get_vulnerabilities(obj) if v['fixable']]
        return len(fixable_vulns)

    def get_fixable_unique_findings(self, obj):
        # Unique fixable vulnerabilities
        fixable_vulns = [v for v in self.get_vulnerabilities(obj) if v['fixable']]
        unique_fixable_vulns = list({v['vulnerability_id']: v for v in fixable_vulns}.values())
        return len(unique_fixable_vulns)

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

    def get_unique_severity_counts(self, obj):
        from collections import Counter
        qs = obj.component_versions.values_list('vulnerabilities__uuid', 'vulnerabilities__severity')
        seen = set()
        severities = []
        for uuid, sev in qs:
            if uuid and uuid not in seen:
                seen.add(uuid)
                severities.append(sev.upper() if sev else 'UNKNOWN')
        counter = Counter(severities)
        all_sevs = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'UNKNOWN']
        return {sev: counter.get(sev, 0) for sev in all_sevs}

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

    def get_has_sbom(self, obj):
        return bool(obj.sbom_data)

    def get_findings(self, obj):
        # Count all vulnerabilities, including duplicates in different components
        return obj.component_versions.values('vulnerabilities').count()

    def get_unique_findings(self, obj):
        # Count unique vulnerabilities across all components
        return obj.component_versions.values('vulnerabilities').distinct().count()

    def get_components_count(self, obj):
        return obj.component_versions.count()


class TagImageShortSerializer(serializers.ModelSerializer):
    findings = serializers.SerializerMethodField()
    components_count = serializers.SerializerMethodField()

    class Meta:
        model = Image
        fields = ['uuid', 'findings', 'components_count', 'name']

    def get_findings(self, obj):
        return obj.component_versions.values('vulnerabilities').count()

    def get_components_count(self, obj):
        return obj.component_versions.count()


class RepositoryTagSerializer(serializers.ModelSerializer):
    images = TagImageShortSerializer(many=True, read_only=True)
    vulnerabilities_count = serializers.SerializerMethodField()

    class Meta:
        model = RepositoryTag
        fields = ['uuid', 'tag', 'repository', 'images', 'created_at', 'updated_at', 'vulnerabilities_count', 'processing_status']
        read_only_fields = ['created_at', 'updated_at', 'uuid']

    def get_vulnerabilities_count(self, obj):
        from core.models import Vulnerability
        return Vulnerability.objects.filter(
            component_versions__images__repository_tags=obj
        ).distinct().count()


class RepositorySerializer(serializers.ModelSerializer):
    tags = RepositoryTagSerializer(many=True, read_only=True)
    tag_count = serializers.SerializerMethodField()

    class Meta:
        model = Repository
        fields = ['uuid', 'name', 'url', 'repository_type', 'tags', 'tag_count', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at', 'uuid']

    def get_tag_count(self, obj):
        return obj.tags.count()


class RepositoryListSerializer(serializers.ModelSerializer):
    tag_count = serializers.SerializerMethodField()

    class Meta:
        model = Repository
        fields = ['uuid', 'name', 'url', 'repository_type', 'tag_count', 'created_at', 'updated_at']
        read_only_fields = ['uuid', 'created_at', 'updated_at']

    def get_tag_count(self, obj):
        return obj.tags.count()
