from django.db import models
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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Repositories"
        unique_together = ('name', 'url')

    def __str__(self):
        return self.name


class RepositoryTag(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tag = models.CharField(max_length=255)
    digest = models.CharField(max_length=255, blank=True, null=True)
    repository = models.ForeignKey(Repository, on_delete=models.CASCADE, related_name='tags', to_field='uuid')
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
        unique_together = ['tag', 'repository']

    def __str__(self):
        return f"{self.repository.name}:{self.tag}"


class Image(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    digest = models.CharField(max_length=255, blank=True, null=True)
    artifact_reference = models.CharField(max_length=255, blank=True, null=True)
    repository_tags = models.ManyToManyField(RepositoryTag, related_name='images', blank=True)
    sbom_data = models.JSONField(null=True, blank=True)
    grype_data = models.JSONField(null=True, blank=True)
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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name}"


class Component(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    type = models.CharField(max_length=50, default='unknown')
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

    def __str__(self):
        return f"{self.vulnerability_id} ({self.severity})"

# Through model for ComponentVersion <-> Vulnerability with fix info
class ComponentVersionVulnerability(models.Model):
    component_version = models.ForeignKey(ComponentVersion, on_delete=models.CASCADE)
    vulnerability = models.ForeignKey('Vulnerability', on_delete=models.CASCADE)
    fixable = models.BooleanField(default=False, help_text='True if a fix is available for this vulnerability in this component version')
    fix = models.CharField(max_length=255, blank=True, null=True, help_text='Fix version(s) or state from Grype report')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['component_version', 'vulnerability']
        verbose_name = 'Component Version Vulnerability Link'
        verbose_name_plural = 'Component Version Vulnerability Links'
    def __str__(self):
        return f"{self.component_version} <-> {self.vulnerability}"
