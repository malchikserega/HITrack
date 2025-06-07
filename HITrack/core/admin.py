from django.contrib import admin
from .models import Repository, RepositoryTag, Image, Component, ComponentVersion, Vulnerability, ContainerRegistry, ComponentVersionVulnerability

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
    list_display = ('name', 'url', 'created_at', 'updated_at', 'last_scanned', 'status')
    search_fields = ('name', 'url')
    list_filter = ('created_at', 'updated_at')

@admin.register(RepositoryTag)
class RepositoryTagAdmin(admin.ModelAdmin):
    list_display = ('tag', 'repository', 'created_at', 'updated_at')
    search_fields = ('tag', 'repository__name')
    list_filter = ('repository', 'created_at', 'updated_at')

@admin.register(Image)
class ImageAdmin(admin.ModelAdmin):
    list_display = ('name', 'digest', 'created_at', 'updated_at')
    search_fields = ('name', 'digest')
    list_filter = ('created_at', 'updated_at')
    filter_horizontal = ('repository_tags',)

@admin.register(Component)
class ComponentAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at', 'updated_at')
    search_fields = ('name',)
    list_filter = ('created_at', 'updated_at')

class ComponentVersionVulnerabilityInline(admin.TabularInline):
    model = ComponentVersionVulnerability
    extra = 0
    fields = ('vulnerability', 'fixable', 'fix', 'created_at', 'updated_at')
    readonly_fields = ('created_at', 'updated_at')
    autocomplete_fields = ('vulnerability',)

@admin.register(ComponentVersion)
class ComponentVersionAdmin(admin.ModelAdmin):
    list_display = ('version', 'component', 'created_at', 'updated_at')
    search_fields = ('version', 'component__name')
    list_filter = ('created_at', 'updated_at')
    filter_horizontal = ('images',)
    inlines = [ComponentVersionVulnerabilityInline]

@admin.register(Vulnerability)
class VulnerabilityAdmin(admin.ModelAdmin):
    list_display = ['vulnerability_id', 'vulnerability_type', 'severity', 'epss', 'created_at']
    list_filter = ['severity', 'vulnerability_type']
    search_fields = ['vulnerability_id', 'description']
    readonly_fields = ['uuid', 'created_at', 'updated_at']
