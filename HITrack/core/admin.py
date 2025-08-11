from django.contrib import admin
from django.contrib import messages
from django.utils import timezone
from django.db import models
from .models import Repository, RepositoryTag, Image, Component, ComponentVersion, Vulnerability, VulnerabilityDetails, ContainerRegistry, ComponentVersionVulnerability, Release, RepositoryTagRelease
from .tasks import update_vulnerability_details


class EPSSScoreRangeFilter(admin.SimpleListFilter):
    title = 'EPSS Score Range'
    parameter_name = 'epss_score_range'
    
    def lookups(self, request, model_admin):
        return (
            ('critical', 'Critical (≥0.7)'),
            ('high', 'High (0.4-0.7)'),
            ('medium', 'Medium (0.1-0.4)'),
            ('low', 'Low (<0.1)'),
            ('none', 'No EPSS Data'),
        )
    
    def queryset(self, request, queryset):
        if self.value() == 'critical':
            return queryset.filter(epss_score__gte=0.7)
        elif self.value() == 'high':
            return queryset.filter(epss_score__gte=0.4, epss_score__lt=0.7)
        elif self.value() == 'medium':
            return queryset.filter(epss_score__gte=0.1, epss_score__lt=0.4)
        elif self.value() == 'low':
            return queryset.filter(epss_score__lt=0.1)
        elif self.value() == 'none':
            return queryset.filter(epss_score__isnull=True)
        return queryset

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

class VulnerabilityDetailsInline(admin.TabularInline):
    model = VulnerabilityDetails
    extra = 0
    fields = ('cve_details_score', 'cve_details_severity', 'epss_score', 'epss_percentile', 'epss_data_source', 'exploit_available', 'exploit_public', 'data_source', 'last_updated')
    readonly_fields = ('last_updated',)
    can_delete = False
    max_num = 1
    
    def get_data_source_display(self, obj):
        """Custom display for data source field."""
        if not obj.data_source or obj.data_source == 'manual':
            return 'Manual Entry'
        elif obj.data_source == 'api':
            return 'API (Legacy)'
        else:
            return obj.data_source
    get_data_source_display.short_description = 'Data Sources'

@admin.register(Vulnerability)
class VulnerabilityAdmin(admin.ModelAdmin):
    list_display = ('vulnerability_id', 'vulnerability_type', 'severity', 'epss', 'epss_percentile', 'description', 'has_details', 'exploit_available', 'created_at')
    search_fields = ('vulnerability_id', 'description', 'details__epss_data_source')
    list_filter = ('vulnerability_type', 'severity', 'details__exploit_available', 'details__data_source', 'details__epss_data_source')
    readonly_fields = ['uuid', 'created_at', 'updated_at', 'epss_percentile', 'epss_from_details']
    
    def epss_percentile(self, obj):
        """Display EPSS percentile from VulnerabilityDetails if available."""
        try:
            if obj.details and obj.details.epss_percentile is not None:
                return f"{obj.details.epss_percentile * 100:.1f}%"
            return "N/A"
        except VulnerabilityDetails.DoesNotExist:
            return "N/A"
    epss_percentile.short_description = 'EPSS %'
    inlines = [VulnerabilityDetailsInline]
    
    def has_details(self, obj):
        try:
            return bool(obj.details)
        except VulnerabilityDetails.DoesNotExist:
            return False
    has_details.boolean = True
    has_details.short_description = 'Has Details'
    
    def exploit_available(self, obj):
        try:
            return obj.details.exploit_available
        except VulnerabilityDetails.DoesNotExist:
            return False
    exploit_available.boolean = True
    exploit_available.short_description = 'Exploit Available'
    
    def epss_from_details(self, obj):
        """Display EPSS score from VulnerabilityDetails if available."""
        try:
            if obj.details and obj.details.epss_score is not None:
                score = obj.details.epss_score
                if score >= 0.7:
                    color = 'red'
                elif score >= 0.4:
                    color = 'orange'
                elif score >= 0.1:
                    color = 'yellow'
                else:
                    color = 'green'
                return f'<span style="color: {color}; font-weight: bold;">{score:.3f}</span>'
            return "N/A"
        except VulnerabilityDetails.DoesNotExist:
            return "N/A"
    epss_from_details.short_description = 'EPSS Score (Details)'
    epss_from_details.allow_tags = True
    

    

    
    fieldsets = (
        ('Basic Information', {
            'fields': ('vulnerability_id', 'vulnerability_type', 'severity', 'description')
        }),
        ('EPSS Information', {
            'fields': ('epss', 'epss_percentile', 'epss_from_details'),
            'classes': ('collapse',)
        }),
        ('System Fields', {
            'fields': ('uuid', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['update_vulnerability_details_action']
    
    def update_vulnerability_details_action(self, request, queryset):
        """Update details for selected vulnerabilities."""
        updated_count = 0
        error_count = 0
        
        for vulnerability in queryset:
            try:
                result = update_vulnerability_details(str(vulnerability.uuid))
                if result.get('status') == 'success':
                    updated_count += 1
                else:
                    error_count += 1
            except Exception as e:
                error_count += 1
        
        if updated_count > 0:
            self.message_user(
                request,
                f'Successfully updated {updated_count} vulnerabilities.',
                messages.SUCCESS
            )
        
        if error_count > 0:
            self.message_user(
                request,
                f'Error updating {error_count} vulnerabilities.',
                messages.ERROR
            )
    
    update_vulnerability_details_action.short_description = "Update details for selected vulnerabilities"

@admin.register(VulnerabilityDetails)
class VulnerabilityDetailsAdmin(admin.ModelAdmin):
    list_display = ('vulnerability', 'cve_details_score', 'cve_details_severity', 'epss_score_display', 'epss_percentile_display', 'epss_data_source', 'exploit_available', 'exploit_public', 'exploit_db_available', 'cisa_kev_known_exploited', 'get_data_source_display', 'last_updated')
    search_fields = ('vulnerability__vulnerability_id', 'cve_details_summary', 'epss_data_source')
    list_filter = ('cve_details_severity', 'exploit_available', 'exploit_public', 'exploit_verified', 'exploit_db_available', 'exploit_db_verified', 'data_source', 'epss_data_source', EPSSScoreRangeFilter)
    readonly_fields = ('uuid', 'last_updated', 'get_data_source_links', 'epss_score_display', 'epss_percentile_display')
    raw_id_fields = ('vulnerability',)
    
    def get_data_source_display(self, obj):
        """Custom display for data source field."""
        if not obj.data_source or obj.data_source == 'manual':
            return 'Manual Entry'
        elif obj.data_source == 'api':
            return 'API (Legacy)'
        else:
            return obj.data_source
    get_data_source_display.short_description = 'Data Sources'
    
    def get_data_source_links(self, obj):
        """Get links for data sources."""
        from django.utils.safestring import mark_safe
        
        if not obj.data_source or obj.data_source in ['manual', 'api']:
            return "No links"
        
        links = []
        sources = obj.data_source.split(' + ')
        
        for source in sources:
            if source == 'CVE-CIRCL':
                links.append(f'<a href="https://cve.circl.lu/api/cve/{obj.vulnerability.vulnerability_id}" target="_blank">CVE-CIRCL</a>')
            elif source == 'Exploit-DB':
                links.append(f'<a href="https://www.exploit-db.com/search?cve={obj.vulnerability.vulnerability_id}" target="_blank">Exploit-DB</a>')
            elif source == 'GitHub-Advisories':
                links.append(f'<a href="https://github.com/advisories?query={obj.vulnerability.vulnerability_id}" target="_blank">GitHub-Advisories</a>')
            elif source == 'NVD':
                links.append(f'<a href="https://nvd.nist.gov/vuln/detail/{obj.vulnerability.vulnerability_id}" target="_blank">NVD</a>')
            elif source == 'CISA-KEV':
                links.append(f'<a href="https://www.cisa.gov/known-exploited-vulnerabilities-catalog?field_cve={obj.vulnerability.vulnerability_id}" target="_blank">CISA-KEV</a>')
            else:
                links.append(source)
        
        return mark_safe(' + '.join(links))
    get_data_source_links.short_description = 'Data Source Links'
    
    def epss_score_display(self, obj):
        """Display EPSS score with color coding."""
        if obj.epss_score is not None:
            score = obj.epss_score
            if score >= 0.7:
                color = 'red'
            elif score >= 0.4:
                color = 'orange'
            elif score >= 0.1:
                color = 'yellow'
            else:
                color = 'green'
            return f'<span style="color: {color}; font-weight: bold;">{score:.3f}</span>'
        return "N/A"
    epss_score_display.short_description = 'EPSS Score'
    epss_score_display.allow_tags = True
    
    def epss_percentile_display(self, obj):
        """Display EPSS percentile with color coding."""
        if obj.epss_percentile is not None:
            percentile = obj.epss_percentile * 100
            if percentile >= 70:
                color = 'red'
            elif percentile >= 40:
                color = 'orange'
            elif percentile >= 10:
                color = 'yellow'
            else:
                color = 'green'
            return f'<span style="color: {color}; font-weight: bold;">{percentile:.1f}%</span>'
        return "N/A"
    epss_percentile_display.short_description = 'EPSS %'
    epss_percentile_display.allow_tags = True
    
    fieldsets = (
        ('Vulnerability', {
            'fields': ('vulnerability',)
        }),
        ('EPSS Information', {
            'fields': ('epss_score_display', 'epss_percentile_display', 'epss_score', 'epss_percentile', 'epss_date', 'epss_data_source', 'epss_last_updated'),
            'classes': ('collapse',)
        }),
        ('CVE Details', {
            'fields': ('cve_details_score', 'cve_details_severity', 'cve_details_published_date', 'cve_details_updated_date', 'cve_details_summary', 'cve_details_references'),
            'classes': ('collapse',)
        }),
        ('Exploit Information', {
            'fields': ('exploit_available', 'exploit_public', 'exploit_verified', 'exploit_links'),
            'classes': ('collapse',)
        }),
        ('Exploit-DB Information', {
            'fields': ('exploit_db_available', 'exploit_db_verified', 'exploit_db_count', 'exploit_db_verified_count', 'exploit_db_working_count', 'exploit_db_links'),
            'classes': ('collapse',)
        }),
        ('CISA KEV Information', {
            'fields': ('cisa_kev_known_exploited', 'cisa_kev_date_added', 'cisa_kev_vendor_project', 'cisa_kev_product', 'cisa_kev_vulnerability_name', 'cisa_kev_short_description', 'cisa_kev_required_action', 'cisa_kev_due_date', 'cisa_kev_ransomware_use', 'cisa_kev_notes', 'cisa_kev_cwes'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('data_source', 'get_data_source_links', 'last_updated'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('vulnerability')
    
    actions = ['update_details_action']
    
    def update_details_action(self, request, queryset):
        """Update details for selected records."""
        updated_count = 0
        error_count = 0
        
        for details in queryset:
            try:
                result = update_vulnerability_details(str(details.vulnerability.uuid))
                if result.get('status') == 'success':
                    updated_count += 1
                else:
                    error_count += 1
            except Exception as e:
                error_count += 1
        
        if updated_count > 0:
            self.message_user(
                request,
                f'Successfully updated {updated_count} records.',
                messages.SUCCESS
            )
        
        if error_count > 0:
            self.message_user(
                request,
                f'Error updating {error_count} records.',
                messages.ERROR
            )
    
    update_details_action.short_description = "Update details for selected records"

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
