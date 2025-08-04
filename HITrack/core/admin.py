from django.contrib import admin
from .models import Repository, RepositoryTag, Image, Component, ComponentVersion, Vulnerability, ContainerRegistry, ComponentVersionVulnerability, Release, RepositoryTagRelease

@admin.register(ContainerRegistry)
class ContainerRegistryAdmin(admin.ModelAdmin):
    list_display = ('name', 'provider', 'api_url', 'last_sync')
    list_filter = ('provider',)
    search_fields = ('name', 'api_url')
    readonly_fields = ('last_sync',)
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'provider')
        }),
        ('Connection Details', {
            'fields': ('api_url', 'login', 'password', 'token')
        }),
        ('Status', {
            'fields': ('last_sync',)
        }),
    )

@admin.register(Repository)
class RepositoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'url', 'status', 'repository_type', 'scan_status', 'last_scanned')
    search_fields = ('name', 'url')
    list_filter = ('status', 'repository_type', 'scan_status')
    raw_id_fields = ('container_registry',)

@admin.register(RepositoryTag)
class RepositoryTagAdmin(admin.ModelAdmin):
    list_display = ('tag', 'repository', 'processing_status', 'created_at')
    search_fields = ('tag', 'repository__name')
    list_filter = ('processing_status',)
    raw_id_fields = ('repository',)

@admin.register(Image)
class ImageAdmin(admin.ModelAdmin):
    list_display = ('name', 'digest', 'scan_status', 'created_at')
    search_fields = ('name', 'digest')
    list_filter = ('scan_status',)
    filter_horizontal = ('repository_tags',)

@admin.register(Component)
class ComponentAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'created_at')
    search_fields = ('name', 'type')
    list_filter = ('type',)

class ComponentVersionVulnerabilityInline(admin.TabularInline):
    model = ComponentVersionVulnerability
    extra = 0
    fields = ('vulnerability', 'fixable', 'fix', 'created_at', 'updated_at')
    readonly_fields = ('created_at', 'updated_at')
    autocomplete_fields = ('vulnerability',)

@admin.register(ComponentVersion)
class ComponentVersionAdmin(admin.ModelAdmin):
    list_display = ('component', 'version', 'created_at', 'latest_version')
    search_fields = ('component__name', 'version', 'purl')
    list_filter = ('component__type',)
    raw_id_fields = ('component',)
    filter_horizontal = ('images',)
    inlines = [ComponentVersionVulnerabilityInline]
    fieldsets = (
        ('Basic Information', {
            'fields': ('component', 'version', 'purl', 'latest_version')
        }),
        ('CPE Information', {
            'fields': ('cpes',)
        })
    )
    readonly_fields = ('created_at', 'updated_at')

@admin.register(Vulnerability)
class VulnerabilityAdmin(admin.ModelAdmin):
    list_display = ('vulnerability_id', 'vulnerability_type', 'severity', 'epss', 'created_at')
    search_fields = ('vulnerability_id', 'description')
    list_filter = ('vulnerability_type', 'severity')
    readonly_fields = ['uuid', 'created_at', 'updated_at']

@admin.register(ComponentVersionVulnerability)
class ComponentVersionVulnerabilityAdmin(admin.ModelAdmin):
    list_display = ('component_version', 'vulnerability', 'fixable', 'fix', 'created_at')
    search_fields = ('component_version__component__name', 'vulnerability__vulnerability_id')
    list_filter = ('fixable',)
    raw_id_fields = ('component_version', 'vulnerability')


@admin.register(Release)
class ReleaseAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'created_at')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at',)


@admin.register(RepositoryTagRelease)
class RepositoryTagReleaseAdmin(admin.ModelAdmin):
    list_display = ('repository_tag', 'release', 'added_at')
    search_fields = ('repository_tag__tag', 'repository_tag__repository__name', 'release__name')
    list_filter = ('release',)
    raw_id_fields = ('repository_tag', 'release')
    readonly_fields = ('added_at',)
