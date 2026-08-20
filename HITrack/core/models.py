from django.db import models
from django.conf import settings
import uuid

class ContainerRegistry(models.Model):
    PROVIDER_CHOICES = [
        ('acr', 'Azure Container Registry'),
        ('gcr', 'Google Container Registry'),
        ('jfrog', 'JFrog Artifactory'),
        ('dockerhub', 'Docker Hub'),
        ('harbor', 'Harbor'),
    ]
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=128, unique=True)
    provider = models.CharField(max_length=32, choices=PROVIDER_CHOICES)
    api_url = models.URLField(blank=True, null=True)
    login = models.CharField(max_length=128, blank=True)
    password = models.CharField(max_length=256, blank=True)
    token = models.TextField(blank=True, null=True)
    last_sync = models.DateTimeField(null=True, blank=True)
    image_fallback_repositories = models.JSONField(
        default=list,
        blank=True,
        help_text='Fallback Docker repos for Helm image resolution. '
                  'Each entry: {"url": "...", "name": "...", "registry_uuid": "..."}',
    )

    class Meta:
        verbose_name_plural = "Registry"
        verbose_name = "Registry"

    def __str__(self):
        return self.name

class Repository(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    url = models.CharField(max_length=255, blank=True, null=True, unique=True)
    status = models.BooleanField(default=False, blank=True, verbose_name="Status")
    last_scanned = models.DateTimeField(blank=True, null=True)
    scan_status = models.CharField(
        max_length=32,
        choices=[
            ('pending', 'Pending'),
            ('in_process', 'In Process'),
            ('success', 'Success'),
            ('error', 'Error'),
            ('none', 'None'),
        ],
        default='none'
    )
    repository_type = models.CharField(
        max_length=10,
        choices=[('helm', 'Helm Chart'), ('docker', 'Docker Image'), ('none', 'Unknown')],
        default='none'
    )
    container_registry = models.ForeignKey('ContainerRegistry', on_delete=models.CASCADE, related_name='repositories', blank=True, null=True, to_field='uuid')
    # For JFrog: the Artifactory repo key (e.g. a8n-docker-local). Empty for ACR.
    repo_key = models.CharField(max_length=255, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Repositories"
        unique_together = ('name', 'url')
        indexes = [
            models.Index(fields=['scan_status']),
            models.Index(fields=['repository_type']),
        ]

    def __str__(self):
        return self.name


class RepositoryTag(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tag = models.CharField(max_length=255)
    digest = models.CharField(max_length=255, blank=True, null=True)
    repository = models.ForeignKey(Repository, on_delete=models.CASCADE, related_name='tags', to_field='uuid')
    # For Artifactory repo keys: image path within the repo (e.g. com.ingrammicro.foo). Blank for ACR/single-image repos.
    image_path = models.CharField(max_length=512, blank=True, default='')
    processing_status = models.CharField(
        max_length=32,
        choices=[
            ('pending', 'Pending'),
            ('in_process', 'In Process'),
            ('success', 'Success'),
            ('error', 'Error'),
            ('none', 'None'),
        ],
        default='none'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [['repository', 'tag', 'image_path']]
        indexes = [
            models.Index(fields=['processing_status']),
        ]

    def __str__(self):
        return f"{self.repository.name}:{self.tag}"


class RepositoryTagScanSnapshot(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    repository_tag = models.ForeignKey(
        RepositoryTag,
        on_delete=models.CASCADE,
        related_name='scan_snapshots',
    )
    processing_status = models.CharField(max_length=32, default='success')
    total_images = models.IntegerField(default=0)
    successful_images = models.IntegerField(default=0)
    unique_vulnerabilities_count = models.IntegerField(default=0)
    weighted_risk_score = models.FloatField(default=0.0)
    previous_unique_vulnerabilities_count = models.IntegerField(default=0)
    new_vulnerabilities_count = models.IntegerField(default=0)
    fixed_vulnerabilities_count = models.IntegerField(default=0)
    severity_increased_count = models.IntegerField(default=0)
    new_kev_relevant_count = models.IntegerField(default=0)
    risk_score_delta = models.FloatField(default=0.0)
    has_changes = models.BooleanField(default=False)
    fixability_breakdown = models.JSONField(default=dict, blank=True)
    vulnerability_state = models.JSONField(default=dict, blank=True)
    delta_summary = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Repository Tag Scan Snapshot'
        verbose_name_plural = 'Repository Tag Scan Snapshots'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['repository_tag', '-created_at']),
            models.Index(fields=['has_changes', '-created_at']),
        ]

    def __str__(self):
        return f"Snapshot for {self.repository_tag} at {self.created_at.isoformat()}"


class Image(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    digest = models.CharField(max_length=255, blank=True, null=True)
    artifact_reference = models.CharField(max_length=255, blank=True, null=True)
    repository_tags = models.ManyToManyField(RepositoryTag, related_name='images', blank=True)
    sbom_data = models.JSONField(null=True, blank=True)
    grype_data = models.JSONField(null=True, blank=True)
    vulnerability_summary = models.JSONField(null=True, blank=True)
    scan_status = models.CharField(
        max_length=32,
        choices=[
            ('pending', 'Pending'),
            ('in_process', 'In Process'),
            ('success', 'Success'),
            ('error', 'Error'),
            ('none', 'None'),
        ],
        default='none'
    )
    lineage_label = models.CharField(max_length=255, default='unknown')
    lineage_source = models.CharField(max_length=64, default='unknown')
    os_distro_name = models.CharField(max_length=255, null=True, blank=True)
    os_distro_version = models.CharField(max_length=255, null=True, blank=True)
    lineage_updated_at = models.DateTimeField(null=True, blank=True)
    os_eol_status = models.CharField(max_length=32, default='unknown')
    os_eol_source = models.CharField(max_length=32, default='unknown')
    os_eol_message = models.CharField(max_length=255, null=True, blank=True)
    os_eol_checked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['scan_status']),
            models.Index(fields=['os_eol_status']),
            models.Index(
                fields=['scan_status', 'lineage_label', 'lineage_source'],
                name='core_image_scan_lineage_idx',
            ),
            models.Index(
                fields=['lineage_label', 'lineage_source'],
                name='core_image_lineage_idx',
            ),
        ]

    def __str__(self):
        return f"{self.name}"


class ScanRun(models.Model):
    """Durable, idempotent record of one image scan pipeline execution."""
    STATUS_CHOICES = [
        ('queued', 'Queued'), ('running', 'Running'), ('success', 'Success'),
        ('failed', 'Failed'), ('cancelled', 'Cancelled'),
    ]
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    image = models.ForeignKey(Image, on_delete=models.CASCADE, related_name='scan_runs')
    idempotency_key = models.CharField(max_length=255, unique=True)
    scanner_version = models.CharField(max_length=128, blank=True, default='')
    policy_version = models.CharField(max_length=128, blank=True, default='')
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default='queued')
    celery_task_id = models.CharField(max_length=255, blank=True, default='')
    attempt_count = models.PositiveIntegerField(default=0)
    lease_expires_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['image', 'status', '-created_at'], name='core_scanrun_image_status_idx'),
            models.Index(fields=['status', 'lease_expires_at'], name='core_scanrun_status_lease_idx'),
        ]


class ScanArtifact(models.Model):
    """Metadata for raw scanner payloads stored outside the operational tables."""
    KIND_CHOICES = [('sbom', 'SBOM'), ('grype', 'Grype')]
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    image = models.ForeignKey(Image, on_delete=models.CASCADE, related_name='scan_artifacts')
    scan_run = models.ForeignKey(ScanRun, on_delete=models.SET_NULL, null=True, blank=True, related_name='artifacts')
    kind = models.CharField(max_length=16, choices=KIND_CHOICES)
    storage_key = models.CharField(max_length=1024)
    checksum = models.CharField(max_length=128, blank=True, default='')
    size_bytes = models.BigIntegerField(default=0)
    scanner_version = models.CharField(max_length=128, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['image', 'kind', 'checksum'], name='unique_image_artifact_checksum')]
        indexes = [models.Index(fields=['image', 'kind', '-created_at'], name='core_artifact_image_kind_idx')]


class Component(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    type = models.CharField(max_length=50, default='unknown')
    # A normalized PURL without its version.  Legacy rows use an empty value.
    identity = models.CharField(max_length=512, blank=True, default='', db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.type})"


class ComponentVersion(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    version = models.CharField(max_length=255)
    latest_version = models.CharField(max_length=255, blank=True, null=True)
    latest_version_updated_at = models.DateTimeField(null=True, blank=True)
    component = models.ForeignKey(Component, on_delete=models.CASCADE, related_name='versions', to_field='uuid')
    images = models.ManyToManyField(Image, related_name='component_versions', blank=True)
    # Use through model to store fixable/fix for each ComponentVersion+Vulnerability pair
    vulnerabilities = models.ManyToManyField(
        'Vulnerability',
        through='ComponentVersionVulnerability',
        related_name='component_versions',
        blank=True
    )
    purl = models.CharField(max_length=512, null=True, blank=True)
    cpes = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['version', 'component']


    def __str__(self):
        return f"{self.component.name} {self.version}"


class ImageComponentVersionContext(models.Model):
    DEPENDENCY_SCOPE_CHOICES = [
        ('direct', 'Direct'),
        ('transitive', 'Transitive'),
        ('unknown', 'Unknown'),
    ]
    PACKAGE_SCOPE_CHOICES = [
        ('runtime', 'Runtime'),
        ('development', 'Development'),
        ('build', 'Build'),
        ('test', 'Test'),
        ('optional', 'Optional'),
        ('unknown', 'Unknown'),
    ]

    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    image = models.ForeignKey(Image, on_delete=models.CASCADE, related_name='component_contexts')
    component_version = models.ForeignKey(
        ComponentVersion,
        on_delete=models.CASCADE,
        related_name='image_contexts',
    )
    cataloger = models.CharField(max_length=128, blank=True, default='')
    metadata_type = models.CharField(max_length=128, blank=True, default='')
    dependency_scope = models.CharField(
        max_length=16,
        choices=DEPENDENCY_SCOPE_CHOICES,
        default='unknown',
    )
    dependency_depth = models.PositiveIntegerField(null=True, blank=True)
    immediate_parent_name = models.CharField(max_length=255, null=True, blank=True)
    immediate_parent_version = models.CharField(max_length=255, null=True, blank=True)
    direct_introducer_name = models.CharField(max_length=255, null=True, blank=True)
    direct_introducer_version = models.CharField(max_length=255, null=True, blank=True)
    package_scope = models.CharField(
        max_length=16,
        choices=PACKAGE_SCOPE_CHOICES,
        default='unknown',
    )
    package_arch = models.CharField(max_length=64, null=True, blank=True)
    package_distro = models.CharField(max_length=255, null=True, blank=True)
    package_repo = models.CharField(max_length=255, null=True, blank=True)
    package_channel = models.CharField(max_length=255, null=True, blank=True)
    source_package = models.CharField(max_length=255, null=True, blank=True)
    source_package_version = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('image', 'component_version')]
        indexes = [
            models.Index(fields=['image', 'dependency_scope']),
            models.Index(fields=['component_version']),
            models.Index(fields=['package_arch']),
            models.Index(fields=['source_package']),
            models.Index(fields=['package_scope']),
        ]

    def __str__(self):
        return f"{self.component_version} in {self.image.name}"


class Vulnerability(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vulnerability_id = models.CharField(max_length=255, unique=True)
    vulnerability_type = models.CharField(max_length=50, default='CVE')
    severity = models.CharField(
        max_length=20,
        choices=[
            ('CRITICAL', 'Critical'),
            ('HIGH', 'High'),
            ('MEDIUM', 'Medium'),
            ('LOW', 'Low'),
            ('NEGLIGIBLE', 'Negligible'),
            ('UNKNOWN', 'Unknown')
        ]
    )
    description = models.TextField(blank=True, null=True)
    epss = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['vulnerability_id']
        verbose_name = 'Vulnerability'
        verbose_name_plural = 'Vulnerabilities'
        indexes = [
            models.Index(fields=['severity']),
            models.Index(fields=['epss']),
        ]

    def __str__(self):
        return f"{self.vulnerability_id} ({self.severity})"


class ThreatIntelSnapshot(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    snapshot_date = models.DateField(unique=True)
    period_start = models.DateField()
    period_end = models.DateField()
    observed_this_week = models.JSONField(default=dict, blank=True)
    kev_added_this_week = models.JSONField(default=dict, blank=True)
    supply_chain_this_week = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Threat Intel Snapshot'
        verbose_name_plural = 'Threat Intel Snapshots'
        ordering = ['-snapshot_date', '-updated_at']
        indexes = [
            models.Index(fields=['period_start', 'period_end']),
        ]

    def __str__(self):
        return f"Threat intel snapshot for {self.snapshot_date.isoformat()}"


class SharedRootCauseAnalyticsSnapshot(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    snapshot_date = models.DateField(unique=True)
    total_items = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Shared Root Cause Analytics Snapshot'
        verbose_name_plural = 'Shared Root Cause Analytics Snapshots'
        ordering = ['-snapshot_date', '-updated_at']

    def __str__(self):
        return f"Shared root-cause snapshot for {self.snapshot_date.isoformat()}"


class SharedRootCauseAnalyticsSnapshotRow(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    snapshot = models.ForeignKey(
        SharedRootCauseAnalyticsSnapshot,
        on_delete=models.CASCADE,
        related_name='rows',
    )
    component_version_uuid = models.UUIDField()
    component_uuid = models.UUIDField()
    component_name = models.CharField(max_length=255)
    version = models.CharField(max_length=255)
    component_type = models.CharField(max_length=50, default='unknown')
    purl = models.CharField(max_length=512, null=True, blank=True)
    latest_version = models.CharField(max_length=255, null=True, blank=True)
    affected_repositories_count = models.IntegerField(default=0)
    affected_tags_count = models.IntegerField(default=0)
    affected_releases_count = models.IntegerField(default=0)
    affected_images_count = models.IntegerField(default=0)
    vulnerabilities_count = models.IntegerField(default=0)
    critical_vulnerabilities_count = models.IntegerField(default=0)
    high_vulnerabilities_count = models.IntegerField(default=0)
    kev_vulnerabilities_count = models.IntegerField(default=0)
    exploit_vulnerabilities_count = models.IntegerField(default=0)
    weighted_risk_score = models.FloatField(default=0.0)
    max_fix_priority = models.IntegerField(default=0)
    fixability_category = models.CharField(max_length=64, default='fix_unknown')
    fixable_now_count = models.IntegerField(default=0)
    fix_exists_but_not_in_repo_count = models.IntegerField(default=0)
    no_fix_count = models.IntegerField(default=0)
    fix_unknown_count = models.IntegerField(default=0)
    latest_seen_at = models.DateTimeField(null=True, blank=True)
    repositories_preview = models.JSONField(default=list, blank=True)
    vulnerabilities_preview = models.JSONField(default=list, blank=True)

    class Meta:
        verbose_name = 'Shared Root Cause Analytics Snapshot Row'
        verbose_name_plural = 'Shared Root Cause Analytics Snapshot Rows'
        ordering = ['-weighted_risk_score', 'component_name', 'version']
        unique_together = [('snapshot', 'component_version_uuid')]
        indexes = [
            models.Index(fields=['snapshot', '-weighted_risk_score']),
            models.Index(fields=['snapshot', 'component_type']),
            models.Index(fields=['snapshot', 'max_fix_priority']),
            models.Index(fields=['snapshot', 'component_name']),
            models.Index(fields=['snapshot', '-affected_repositories_count']),
        ]

    def __str__(self):
        return f"{self.component_name}@{self.version} ({self.snapshot.snapshot_date.isoformat()})"

    @property
    def fixability_breakdown(self):
        return {
            'fixable_now': self.fixable_now_count,
            'fix_exists_but_not_in_repo': self.fix_exists_but_not_in_repo_count,
            'no_fix': self.no_fix_count,
            'fix_unknown': self.fix_unknown_count,
        }


class BaseLineageRootCauseAnalyticsSnapshot(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    snapshot_date = models.DateField(unique=True)
    total_items = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Base Lineage Root Cause Analytics Snapshot'
        verbose_name_plural = 'Base Lineage Root Cause Analytics Snapshots'
        ordering = ['-snapshot_date', '-updated_at']

    def __str__(self):
        return f"Base-lineage root-cause snapshot for {self.snapshot_date.isoformat()}"


class BaseLineageRootCauseAnalyticsSnapshotRow(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    snapshot = models.ForeignKey(
        BaseLineageRootCauseAnalyticsSnapshot,
        on_delete=models.CASCADE,
        related_name='rows',
    )
    key = models.CharField(max_length=255)
    lineage_label = models.CharField(max_length=255)
    lineage_source = models.CharField(max_length=64, default='unknown')
    affected_repositories_count = models.IntegerField(default=0)
    affected_tags_count = models.IntegerField(default=0)
    affected_releases_count = models.IntegerField(default=0)
    affected_images_count = models.IntegerField(default=0)
    vulnerabilities_count = models.IntegerField(default=0)
    critical_vulnerabilities_count = models.IntegerField(default=0)
    high_vulnerabilities_count = models.IntegerField(default=0)
    kev_vulnerabilities_count = models.IntegerField(default=0)
    exploit_vulnerabilities_count = models.IntegerField(default=0)
    weighted_risk_score = models.FloatField(default=0.0)
    max_fix_priority = models.IntegerField(default=0)
    fixability_category = models.CharField(max_length=64, default='fix_unknown')
    fixable_now_count = models.IntegerField(default=0)
    fix_exists_but_not_in_repo_count = models.IntegerField(default=0)
    no_fix_count = models.IntegerField(default=0)
    fix_unknown_count = models.IntegerField(default=0)
    latest_seen_at = models.DateTimeField(null=True, blank=True)
    repositories_preview = models.JSONField(default=list, blank=True)
    components_preview = models.JSONField(default=list, blank=True)
    vulnerabilities_preview = models.JSONField(default=list, blank=True)

    class Meta:
        verbose_name = 'Base Lineage Root Cause Analytics Snapshot Row'
        verbose_name_plural = 'Base Lineage Root Cause Analytics Snapshot Rows'
        ordering = ['-weighted_risk_score', 'lineage_label']
        unique_together = [('snapshot', 'key')]
        indexes = [
            models.Index(fields=['snapshot', '-weighted_risk_score']),
            models.Index(fields=['snapshot', 'lineage_label']),
            models.Index(fields=['snapshot', 'lineage_source']),
            models.Index(fields=['snapshot', 'max_fix_priority']),
            models.Index(fields=['snapshot', '-affected_repositories_count']),
        ]

    def __str__(self):
        return f"{self.lineage_label} ({self.snapshot.snapshot_date.isoformat()})"

    @property
    def fixability_breakdown(self):
        return {
            'fixable_now': self.fixable_now_count,
            'fix_exists_but_not_in_repo': self.fix_exists_but_not_in_repo_count,
            'no_fix': self.no_fix_count,
            'fix_unknown': self.fix_unknown_count,
        }


class VulnerabilityDetails(models.Model):
    """
    Additional vulnerability information from external sources like CVE Details,
    exploit databases, and other security sources.
    """
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vulnerability = models.OneToOneField(Vulnerability, on_delete=models.CASCADE, related_name='details')
    
    # CVE Details information
    cve_details_score = models.FloatField(null=True, blank=True, help_text='CVSS Score from CVE Details')
    cve_details_severity = models.CharField(max_length=20, blank=True, null=True, help_text='Severity from CVE Details')
    cve_details_published_date = models.DateField(null=True, blank=True, help_text='Published date from CVE Details')
    cve_details_updated_date = models.DateField(null=True, blank=True, help_text='Last updated date from CVE Details')
    cve_details_summary = models.TextField(blank=True, null=True, help_text='Detailed summary from CVE Details')
    cve_details_references = models.JSONField(default=list, blank=True, help_text='References from CVE Details')
    
    # Exploit information
    exploit_available = models.BooleanField(default=False, help_text='Whether exploit is publicly available')
    exploit_public = models.BooleanField(default=False, help_text='Whether exploit is in public databases')
    exploit_verified = models.BooleanField(default=False, help_text='Whether exploit has been verified')
    exploit_links = models.JSONField(default=list, blank=True, help_text='Links to exploit information')
    
    # CISA KEV information
    cisa_kev_known_exploited = models.BooleanField(default=False, help_text='Whether vulnerability is in CISA KEV catalog')
    cisa_kev_date_added = models.DateField(null=True, blank=True, help_text='Date added to CISA KEV catalog')
    cisa_kev_vendor_project = models.CharField(max_length=255, blank=True, null=True, help_text='Vendor/Project from CISA KEV')
    cisa_kev_product = models.CharField(max_length=255, blank=True, null=True, help_text='Product from CISA KEV')
    cisa_kev_vulnerability_name = models.CharField(max_length=255, blank=True, null=True, help_text='Vulnerability name from CISA KEV')
    cisa_kev_short_description = models.TextField(blank=True, null=True, help_text='Short description from CISA KEV')
    cisa_kev_required_action = models.TextField(blank=True, null=True, help_text='Required action from CISA KEV')
    cisa_kev_due_date = models.DateField(null=True, blank=True, help_text='Due date from CISA KEV')
    cisa_kev_ransomware_use = models.CharField(max_length=20, blank=True, null=True, help_text='Known ransomware campaign use')
    cisa_kev_notes = models.TextField(blank=True, null=True, help_text='Notes from CISA KEV')
    cisa_kev_cwes = models.JSONField(default=list, blank=True, help_text='CWE codes from CISA KEV')
    
    # Exploit-DB information
    exploit_db_available = models.BooleanField(default=False, help_text='Whether exploit is available in Exploit-DB')
    exploit_db_verified = models.BooleanField(default=False, help_text='Whether exploit is verified in Exploit-DB')
    exploit_db_count = models.IntegerField(default=0, help_text='Number of exploits found in Exploit-DB')
    exploit_db_verified_count = models.IntegerField(default=0, help_text='Number of verified exploits in Exploit-DB')
    exploit_db_working_count = models.IntegerField(default=0, help_text='Number of working exploits in Exploit-DB')
    exploit_db_links = models.JSONField(default=list, blank=True, help_text='Links to Exploit-DB entries')
    
    # Additional metadata
    last_updated = models.DateTimeField(auto_now=True, help_text='When this record was last updated')
    last_attempted_at = models.DateTimeField(null=True, blank=True, help_text='Most recent external enrichment attempt')
    last_successful_at = models.DateTimeField(null=True, blank=True, help_text='Most recent enrichment that returned usable data')
    enrichment_status = models.CharField(max_length=32, default='never', help_text='never, success, partial, or failed')
    enrichment_error = models.TextField(blank=True, default='', help_text='Most recent enrichment error; cleared after success')
    data_source = models.CharField(max_length=100, default='manual', help_text='Source of this information')
    
    # EPSS information from FIRST API
    epss_score = models.FloatField(null=True, blank=True, help_text='EPSS score from FIRST API')
    epss_percentile = models.FloatField(null=True, blank=True, help_text='EPSS percentile from FIRST API')
    epss_date = models.DateField(null=True, blank=True, help_text='EPSS assessment date from FIRST API')
    epss_data_source = models.CharField(max_length=50, blank=True, null=True, help_text='Source of EPSS data (FIRST-EPSS, Grype, etc.)')
    epss_last_updated = models.DateTimeField(null=True, blank=True, help_text='When EPSS data was last updated')
    
    class Meta:
        verbose_name = 'Vulnerability Details'
        verbose_name_plural = 'Vulnerability Details'
        indexes = [
            models.Index(fields=['last_updated']),
            models.Index(fields=['exploit_available']),
            models.Index(fields=['cisa_kev_known_exploited']),
            models.Index(fields=['cisa_kev_ransomware_use']),
            models.Index(fields=['enrichment_status', 'last_successful_at'], name='core_vulnd_enrich_status_idx'),
        ]
    
    def __str__(self):
        return f"Details for {self.vulnerability.vulnerability_id}"

# Through model for ComponentVersion <-> Vulnerability with fix info
class ComponentVersionVulnerability(models.Model):
    component_version = models.ForeignKey(ComponentVersion, on_delete=models.CASCADE)
    vulnerability = models.ForeignKey('Vulnerability', on_delete=models.CASCADE)
    fixable = models.BooleanField(default=False, help_text='True if a fix is available for this vulnerability in this component version')
    fix = models.CharField(max_length=255, blank=True, null=True, help_text='Fix version(s) or state from Grype report')
    fix_state = models.CharField(max_length=64, blank=True, null=True, help_text='Raw fix state reported by Grype')
    fix_status = models.CharField(max_length=32, default='unknown', help_text='Normalized fix availability status')
    fix_versions = models.JSONField(default=list, blank=True, help_text='Structured fixed-in versions reported by Grype')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['component_version', 'vulnerability']
        verbose_name = 'Component Version Vulnerability Link'
        verbose_name_plural = 'Component Version Vulnerability Links'
        indexes = [
            models.Index(fields=['vulnerability', 'component_version']),
        ]

    def __str__(self):
        return f"{self.component_version} <-> {self.vulnerability}"


class AuditEvent(models.Model):
    """Append-only audit trail for security-sensitive operations."""
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='hitrack_audit_events')
    action = models.CharField(max_length=128)
    target_type = models.CharField(max_length=128, blank=True, default='')
    target_id = models.CharField(max_length=128, blank=True, default='')
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['actor', '-created_at'], name='core_audit_actor_date_idx'),
            models.Index(fields=['action', '-created_at'], name='core_audit_action_date_idx'),
        ]


class Release(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=128, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = 'Release'
        verbose_name_plural = 'Releases'

    def __str__(self):
        return self.name


class RepositoryTagRelease(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    repository_tag = models.ForeignKey(RepositoryTag, on_delete=models.CASCADE, related_name='releases')
    release = models.ForeignKey(Release, on_delete=models.CASCADE, related_name='repository_tags')
    added_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['repository_tag', 'release']
        verbose_name = 'Repository Tag Release Assignment'
        verbose_name_plural = 'Repository Tag Release Assignments'

    def __str__(self):
        return f"{self.repository_tag} -> {self.release}"


class ComponentLocation(models.Model):
    """
    Model to store location information for components found in images.
    This includes file paths, layer information, and access paths from Grype scan results.
    """
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    component_version = models.ForeignKey(ComponentVersion, on_delete=models.CASCADE, related_name='locations')
    image = models.ForeignKey(Image, on_delete=models.CASCADE, related_name='component_locations')
    
    # Location information from Grype
    path = models.CharField(max_length=512, help_text='File path where component was found')
    layer_id = models.CharField(max_length=255, blank=True, null=True, help_text='Docker layer ID')
    access_path = models.CharField(max_length=512, blank=True, null=True, help_text='Access path to the component')
    
    # Evidence information
    evidence_type = models.CharField(
        max_length=32,
        choices=[
            ('primary', 'Primary Evidence'),
            ('supporting', 'Supporting Evidence'),
            ('unknown', 'Unknown')
        ],
        default='unknown',
        help_text='Type of evidence for this location'
    )
    
    # Additional metadata
    annotations = models.JSONField(default=dict, blank=True, help_text='Additional annotations from Grype')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['component_version', 'image', 'path']
        verbose_name = 'Component Location'
        verbose_name_plural = 'Component Locations'
        indexes = [
            models.Index(fields=['path']),
            models.Index(fields=['layer_id']),
            models.Index(fields=['evidence_type']),
        ]

    def __str__(self):
        return f"{self.component_version} in {self.image.name} at {self.path}"
