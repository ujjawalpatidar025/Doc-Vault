from django.contrib import admin

from .models import FileMetadata


@admin.register(FileMetadata)
class FileMetadataAdmin(admin.ModelAdmin):
    list_display = ['original_filename', 'user_id', 'size', 'reference_count', 'is_reference', 'uploaded_at']
    list_filter = ['is_reference', 'uploaded_at', 'file_type']
    search_fields = ['original_filename', 'file_hash', 'user_id']
    readonly_fields = [f.name for f in FileMetadata._meta.fields]
    list_select_related = ['original_file']
