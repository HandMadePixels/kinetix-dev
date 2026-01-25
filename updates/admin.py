from django.contrib import admin
from django import forms
from django.utils.html import format_html
from updates.models import Update, UpdatePush, ScanResult

class UpdateAdminForm(forms.ModelForm):
    class Meta:
        model = Update
        fields = '__all__'
        widgets = {
            'version': forms.TextInput(attrs={'placeholder': 'e.g. 1.2.3.4'}),
        }

@admin.register(Update)
class UpdateAdmin(admin.ModelAdmin):
    form = UpdateAdminForm
    list_display = ['name', 'version', 'download_link', 'scan_status', 'uploaded_at', 'uploaded_by']
    list_filter = ['scan_status', 'uploaded_at']
    search_fields = ['name', 'version', 'description']
    readonly_fields = ['sha256_hash', 'signature', 'uploaded_at', 'uploaded_by']

    def save_model(self, request, obj, form, change):
        if not obj.pk:  # If new object
            obj.uploaded_by = request.user
        super().save_model(request, obj, form, change)

    def download_link(self, obj):
        if obj.file:
            return format_html(
                '<a class="button" href="{}" download style="background-color: #447e9b; color: white; padding: 3px 10px; border-radius: 4px; text-decoration: none;">'
                '<i class="bi bi-download"></i> Download</a>',
                obj.file.url
            )
        return "No File"
    download_link.short_description = 'Installation File'

@admin.register(UpdatePush)
class UpdatePushAdmin(admin.ModelAdmin):
    list_display = ['update', 'device', 'status', 'pushed_at', 'retry_count']
    list_filter = ['status', 'pushed_at']
    search_fields = ['device__hostname', 'update__version']

@admin.register(ScanResult)
class ScanResultAdmin(admin.ModelAdmin):
    list_display = ['update', 'scanner', 'is_clean', 'scanned_at']
    list_filter = ['scanner', 'is_clean']
    search_fields = ['update__version', 'raw_response']
