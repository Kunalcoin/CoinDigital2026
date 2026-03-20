from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import (
    UniqueCode, Label, Release, Track, Artist, RelatedArtists, 
    Metadata, Royalties
)


@admin.register(UniqueCode)
class UniqueCodeAdmin(admin.ModelAdmin):
    list_display = ('code', 'type', 'assigned', 'created_at')
    list_filter = ('type', 'assigned', 'created_at')
    search_fields = ('code',)
    readonly_fields = ('created_at', 'updated_at')
    list_per_page = 50
    
    fieldsets = (
        (None, {
            'fields': ('type', 'code', 'assigned')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Label)
class LabelAdmin(admin.ModelAdmin):
    list_display = ('label', 'user', 'created_at')
    list_filter = ('created_at', 'user')
    search_fields = ('label', 'user__username', 'user__email')
    readonly_fields = ('created_at', 'updated_at')
    list_per_page = 50
    
    fieldsets = (
        (None, {
            'fields': ('user', 'label')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


class RelatedArtistsInline(admin.TabularInline):
    model = RelatedArtists
    extra = 1
    fields = ('artist', 'role')
    autocomplete_fields = ('artist',)


class TrackInline(admin.TabularInline):
    model = Track
    extra = 0
    fields = ('title', 'primary_genre', 'isrc', 'explicit_lyrics', 'available_separately')
    readonly_fields = ('created_at',)
    show_change_link = True


@admin.register(Release)
class ReleaseAdmin(admin.ModelAdmin):
    list_display = (
        'title', 'album_format', 'primary_genre', 'created_by', 
        'published', 'digital_release_date', 'label'
    )
    list_filter = (
        'album_format', 'primary_genre', 'published', 'takedown_requested',
        'price_category', 'license_type', 'apple_music_commercial_model',
        'digital_release_date', 'created_at'
    )
    search_fields = ('title', 'upc', 'reference_number', 'created_by__username')
    readonly_fields = ('created_at', 'updated_at', 'published_at')
    autocomplete_fields = ('created_by', 'label')
    list_per_page = 25
    date_hierarchy = 'digital_release_date'
    
    inlines = [TrackInline, RelatedArtistsInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'title', 'cover_art_url', 'remix_version', 'album_format',
                'primary_genre', 'secondary_genre', 'language', 'description'
            )
        }),
        ('Identifiers', {
            'fields': ('upc', 'reference_number', 'grid'),
            'classes': ('collapse',)
        }),
        ('Publishing Information', {
            'fields': (
                'created_by', 'label', 'published', 'takedown_requested', 
                'published_at'
            )
        }),
        ('License & Pricing', {
            'fields': (
                'price_category', 'license_type', 'license_holder_name',
                'license_holder_year', 'copyright_recording_year',
                'copyright_recording_text', 'territories',
            ),
            'classes': ('collapse',)
        }),
        ('License — Apple Music (Merlin Bridge)', {
            'fields': ('apple_music_commercial_model', 'apple_music_preorder_start_date'),
            'description': (
                'Commercial model: cleared_for_sale / cleared_for_stream (checklist: streaming vs retail). '
                'Pre-order: set pre-order sales start date (maps to preorder_sales_start_date in XML; before Digital release date, future when you deliver). '
                'Clear the date to remove pre-order from metadata.'
            ),
        }),
        ('Release Dates', {
            'fields': ('digital_release_date', 'original_release_date')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'created_by', 'label'
        )


@admin.register(Track)
class TrackAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'title', 'release', 'primary_genre', 'explicit_lyrics',
        'apple_music_instant_grat', 'available_separately', 'created_by'
    )
    list_filter = (
        'explicit_lyrics', 'available_separately', 'apple_music_instant_grat',
        'primary_genre', 'language', 'created_at'
    )
    search_fields = (
        'id', 'title', 'isrc', 'iswc', 'release__title', 'created_by__username'
    )
    readonly_fields = ('created_at', 'updated_at')
    autocomplete_fields = ('release', 'created_by')
    list_per_page = 50
    
    inlines = [RelatedArtistsInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'release', 'title', 'remix_version', 'primary_genre',
                'secondary_genre', 'language', 'explicit_lyrics'
            )
        }),
        ('Audio & Media', {
            'fields': ('audio_track_url', 'start_point', 'available_separately')
        }),
        ('Apple Music (Merlin Bridge)', {
            'fields': (
                'apple_music_instant_grat',
                'apple_music_dolby_atmos_url',
                'apple_music_dolby_atmos_isrc',
            ),
            'description': (
                'Pre-order: Instant Grat (≥1, ≤50% of tracks). '
                'Dolby Atmos: BWF ADM .wav URL + distinct secondary ISRC; only delivered when the release owner has '
                '"Apple Music Dolby Atmos delivery" enabled on their user. See MERLIN_BRIDGE_APPLE_MUSIC.md.'
            ),
        }),
        ('Identifiers', {
            'fields': ('isrc', 'iswc'),
            'classes': ('collapse',)
        }),
        ('Publishing Rights', {
            'fields': (
                'publishing_rights_owner', 'publishing_rights_year'
            ),
            'classes': ('collapse',)
        }),
        ('Content', {
            'fields': ('lyrics', 'notes')
        }),
        ('Management', {
            'fields': ('created_by',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'release', 'created_by'
        )


@admin.register(Artist)
class ArtistAdmin(admin.ModelAdmin):
    list_display = ('name', 'artist_id', 'user', 'created_at')
    list_filter = ('created_at', 'user')
    search_fields = (
        'name', 'first_name', 'last_name', 'artist_id',
        'user__username', 'user__email'
    )
    readonly_fields = ('created_at', 'updated_at')
    autocomplete_fields = ('user',)
    list_per_page = 50
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'artist_id', 'name', 'first_name', 'last_name')
        }),
        ('Social Media & Platforms', {
            'fields': (
                'apple_music_id', 'spotify_id', 'youtube_username',
                'soundcloud_page', 'facebook_page', 'x_username', 'website'
            ),
            'classes': ('collapse',)
        }),
        ('Biography', {
            'fields': ('biography',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(RelatedArtists)
class RelatedArtistsAdmin(admin.ModelAdmin):
    list_display = ('artist', 'role', 'relation_key', 'get_related_item')
    list_filter = ('role', 'relation_key', 'created_at')
    search_fields = ('artist__name', 'role')
    autocomplete_fields = ('artist', 'release', 'track')
    readonly_fields = ('created_at', 'updated_at')
    list_per_page = 50
    
    def get_related_item(self, obj):
        if obj.relation_key == 'release' and obj.release:
            return obj.release.title
        elif obj.relation_key == 'track' and obj.track:
            return obj.track.title
        return '-'
    get_related_item.short_description = 'Related Item'
    
    fieldsets = (
        ('Relationship', {
            'fields': ('relation_key', 'release', 'track', 'artist', 'role')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Metadata)
class MetadataAdmin(admin.ModelAdmin):
    list_display = (
        'isrc', 'track', 'display_artist', 'release_launch', 
        'user', 'primary_genre'
    )
    list_filter = (
        'primary_genre', 'secondary_genre', 'release_launch',
        'track_primary_genre'
    )
    search_fields = (
        'isrc', 'track', 'release', 'display_artist', 
        'track_display_artist', 'user', 'upc'
    )
    readonly_fields = ('isrc',)  # ISRC is primary key, should be readonly in edit
    list_per_page = 50
    date_hierarchy = 'release_launch'
    
    fieldsets = (
        ('Identifiers', {
            'fields': ('isrc', 'upc')
        }),
        ('Release Information', {
            'fields': ('release', 'display_artist', 'release_launch', 'label_name')
        }),
        ('Track Information', {
            'fields': (
                'track_no', 'track', 'track_display_artist'
            )
        }),
        ('Genres', {
            'fields': ('primary_genre', 'secondary_genre', 'track_primary_genre')
        }),
        ('User Information', {
            'fields': ('user',)
        }),
    )


@admin.register(Royalties)
class RoyaltiesAdmin(admin.ModelAdmin):
    list_display = (
        'royalty_id', 'isrc', 'channel', 'country', 'type',
        'units', 'net_total_INR', 'start_date', 'end_date'
    )
    list_filter = (
        'channel', 'country', 'currency', 'type', 'start_date',
        'end_date', 'confirmed_date'
    )
    search_fields = ('isrc', 'royalty_id')
    readonly_fields = ('royalty_id',)
    list_per_page = 50
    date_hierarchy = 'start_date'
    
    # Custom actions
    actions = ['export_selected_royalties']
    
    def export_selected_royalties(self, request, queryset):
        # This is a placeholder for export functionality
        self.message_user(request, f"Export functionality for {queryset.count()} royalties")
    export_selected_royalties.short_description = "Export selected royalties"
    
    fieldsets = (
        ('Identifiers', {
            'fields': ('royalty_id', 'isrc')
        }),
        ('Period & Location', {
            'fields': ('start_date', 'end_date', 'country', 'channel', 'type')
        }),
        ('Original Currency', {
            'fields': (
                'currency', 'units', 'unit_price', 'gross_total',
                'channel_costs', 'taxes', 'net_total'
            )
        }),
        ('INR Conversion', {
            'fields': (
                'currency_rate', 'gross_total_INR', 'other_costs_INR',
                'channel_costs_INR', 'taxes_INR', 'net_total_INR'
            ),
            'classes': ('collapse',)
        }),
        ('Client Currency', {
            'fields': (
                'gross_total_client_currency', 'other_costs_client_currency',
                'channel_costs_client_currency', 'taxes_client_currency',
                'net_total_client_currency'
            ),
            'classes': ('collapse',)
        }),
        ('Confirmation', {
            'fields': ('confirmed_date',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request)


