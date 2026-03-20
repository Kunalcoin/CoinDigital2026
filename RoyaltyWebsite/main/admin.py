from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import AdminPasswordChangeForm
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django import forms
from .models import CDUser, Ratio, DueAmount, Request, Sharing, Announcement, Payment


class CDUserAdminForm(forms.ModelForm):
    new_password = forms.CharField(
        label='Set New Password',
        widget=forms.PasswordInput(attrs={'placeholder': 'Leave blank to keep current password'}),
        required=False,
        help_text='Enter a new password to change it, or leave blank to keep the current password.'
    )
    
    class Meta:
        model = CDUser
        fields = '__all__'


@admin.register(CDUser)
class CDUserAdmin(BaseUserAdmin):
    # Clear the inherited filter_horizontal configuration
    filter_horizontal = ()
    form = CDUserAdminForm
    change_password_form = AdminPasswordChangeForm
    
    # Display configuration
    list_display = [
        'email', 'first_name', 'last_name', 'role', 'country', 
        'is_active', 'is_staff', 'date_joined', 'parent_link'
    ]
    list_display_links = ['email', 'first_name', 'last_name']
    list_filter = [
        'role', 'country', 'language', 'is_active', 'is_staff', 
        'is_superuser', 'date_joined'
    ]
    search_fields = [
        'email', 'first_name', 'last_name', 'company', 'company_name',
        'contact_phone', 'city', 'pan', 'gst_number'
    ]
    ordering = ['email']
    list_per_page = 50
    
    # Fieldsets for form organization
    fieldsets = (
        ('Authentication', {
            'fields': ('email', 'new_password'),
            'description': 'Use the field below for quick password changes, or use the "Change Password" button for the standard form.'
        }),
        ('Personal Information', {
            'fields': ('first_name', 'last_name', 'contact_phone', 'language')
        }),
        ('Address Information', {
            'fields': ('country', 'city', 'street', 'postal_code', 'country_phone'),
            'classes': ('collapse',)
        }),
        ('Company Information', {
            'fields': ('company', 'company_name', 'company_contact_phone', 'fiskal_id_number'),
            'classes': ('collapse',)
        }),
        ('Tax Information', {
            'fields': ('pan', 'gst_number'),
            'classes': ('collapse',)
        }),
        ('Banking Information', {
            'fields': (
                'account_name', 'account_number', 'ifsc', 'sort_code', 
                'swift_code', 'iban', 'bank_country', 'bank_name'
            ),
            'classes': ('collapse',)
        }),
        ('Permissions', {
            'fields': ('role', 'is_active', 'is_staff', 'is_superuser', 'parent'),
            'classes': ('collapse',)
        }),
        ('Important Dates', {
            'fields': ('date_joined', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    add_fieldsets = (
        ('Create New User', {
            'classes': ('wide',),
            'fields': (
                'email', 'password1', 'password2', 'first_name', 'last_name',
                'role', 'country', 'contact_phone', 'parent'
            ),
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at', 'date_joined']
    
    def save_model(self, request, obj, form, change):
        """Custom save method to handle password setting"""
        # Check if new_password field has a value
        new_password = form.cleaned_data.get('new_password')
        if new_password:
            # Set and hash the new password
            obj.set_password(new_password)
        
        # Save the object
        super().save_model(request, obj, form, change)
    
    def parent_link(self, obj):
        """Display parent user as a clickable link"""
        if obj.parent:
            url = reverse('admin:main_cduser_change', args=[obj.parent.id])  # Fixed URL pattern
            return format_html('<a href="{}">{}</a>', url, obj.parent.email)
        return '-'
    parent_link.short_description = 'Parent User'
    parent_link.admin_order_field = 'parent__email'

    def get_queryset(self, request):
        """Optimize queries by selecting related parent"""
        return super().get_queryset(request).select_related('parent')


@admin.register(Ratio)
class RatioAdmin(admin.ModelAdmin):
    list_display = [
        'user_email', 'stores', 'youtube', 'sales_payout', 
        'sales_payout_threshold', 'status', 'created_at'
    ]
    list_display_links = ['user_email']
    list_filter = ['status', 'created_at', 'updated_at']
    search_fields = ['user__email', 'user__first_name', 'user__last_name']
    ordering = ['-created_at']
    list_per_page = 50
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('User Information', {
            'fields': ('user',)
        }),
        ('Ratio Configuration', {
            'fields': ('stores', 'youtube', 'sales_payout', 'sales_payout_threshold')
        }),
        ('Status & Timestamps', {
            'fields': ('status', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User Email'
    user_email.admin_order_field = 'user__email'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


@admin.register(DueAmount)
class DueAmountAdmin(admin.ModelAdmin):
    list_display = ['user_email', 'amount', 'created_at', 'updated_at']
    list_display_links = ['user_email']
    list_filter = ['created_at', 'updated_at']
    search_fields = ['user__email', 'user__first_name', 'user__last_name']
    ordering = ['-amount']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Due Amount Information', {
            'fields': ('user', 'amount')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User Email'
    user_email.admin_order_field = 'user__email'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


@admin.register(Request)
class RequestAdmin(admin.ModelAdmin):
    list_display = [
        'user_email', 'title', 'status', 'created_at', 'updated_at'
    ]
    list_display_links = ['user_email', 'title']
    list_filter = ['status', 'created_at', 'updated_at']
    search_fields = [
        'user__email', 'user__first_name', 'user__last_name', 
        'title', 'description'
    ]
    ordering = ['-created_at']
    list_per_page = 50
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Request Information', {
            'fields': ('user', 'title', 'status')
        }),
        ('Content', {
            'fields': ('description', 'feedback')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User Email'
    user_email.admin_order_field = 'user__email'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


@admin.register(Sharing)
class SharingAdmin(admin.ModelAdmin):
    list_display = [
        'user_email', 'store_ratio', 'youtube_ratio', 
        'payout_threshold', 'is_active', 'created_at'
    ]
    list_display_links = ['user_email']
    list_filter = ['is_active', 'created_at', 'updated_at']
    search_fields = ['user__email', 'user__first_name', 'user__last_name']
    ordering = ['-created_at']
    list_per_page = 50
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('User Information', {
            'fields': ('user',)
        }),
        ('Revenue Sharing Configuration', {
            'fields': ('store_ratio', 'youtube_ratio', 'payout_threshold')
        }),
        ('Status & Timestamps', {
            'fields': ('is_active', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User Email'
    user_email.admin_order_field = 'user__email'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ['announcement_id', 'announcement_preview', 'created_at']
    list_display_links = ['announcement_id']
    list_filter = ['created_at']
    search_fields = ['announcement']
    ordering = ['-created_at']
    readonly_fields = ['announcement_id', 'created_at']
    
    fieldsets = (
        ('Announcement Details', {
            'fields': ('announcement',)
        }),
        ('Meta Information', {
            'fields': ('announcement_id', 'created_at'),
            'classes': ('collapse',)
        }),
    )
    
    def announcement_preview(self, obj):
        """Show a preview of the announcement text"""
        if len(obj.announcement) > 100:
            return obj.announcement[:100] + '...'
        return obj.announcement
    announcement_preview.short_description = 'Announcement Preview'


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = [
        'username', 'date_of_payment', 'amount_paid', 'tds', 
        'tds_percentage', 'transfer_id'
    ]
    list_display_links = ['username', 'transfer_id']
    list_filter = [
        'date_of_payment', 'tds_percentage', 'source_account'
    ]
    search_fields = [
        'username', 'sent_to_name', 'sent_to_account_number', 
        'sent_to_ifsc_code', 'transfer_id'
    ]
    ordering = ['-date_of_payment']
    list_per_page = 50
    date_hierarchy = 'date_of_payment'
    
    fieldsets = (
        ('Payment Information', {
            'fields': ('username', 'date_of_payment', 'amount_paid', 'transfer_id')
        }),
        ('Tax Information', {
            'fields': ('tds', 'tds_percentage')
        }),
        ('Account Information', {
            'fields': (
                'source_account', 'sent_to_name', 'sent_to_account_number', 
                'sent_to_ifsc_code'
            ),
            'classes': ('collapse',)
        }),
    )
    
    def get_readonly_fields(self, request, obj=None):
        """Make certain fields readonly after creation"""
        if obj:  # Editing existing object
            return ['transfer_id', 'date_of_payment']
        return []

