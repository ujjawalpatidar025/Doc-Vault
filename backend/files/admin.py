from django.contrib import admin

from .models import FileMetadata


@admin.register(FileMetadata)
class FileMetadataAdmin(admin.ModelAdmin):
    list_display = ['name', 'user_id', 'file_size', 'upload_count', 'is_reference', 'uploaded_at']
    list_filter = ['is_reference', 'uploaded_at', 'mime_type']
    search_fields = ['name', 'file_hash', 'user_id']
    readonly_fields = [f.name for f in FileMetadata._meta.fields]
    list_select_related = ['original_file']
