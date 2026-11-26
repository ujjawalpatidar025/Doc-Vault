from rest_framework import serializers

from .models import FileMetadata


class FileMetadataSerializer(serializers.ModelSerializer):
    """Read-only representation of a user's file."""

    file_url = serializers.SerializerMethodField()
    size_mb = serializers.SerializerMethodField()
    upload_count = serializers.SerializerMethodField()

    class Meta:
        model = FileMetadata
        fields = [
            'id', 'user_id', 'name', 'file_hash', 'file_url', 'file_size', 'size_mb',
            'mime_type', 'uploaded_at', 'upload_count', 'is_reference', 'original_file',
        ]
        read_only_fields = fields

    def get_file_url(self, obj):
        request = self.context.get('request')
        path = f'/api/files/{obj.pk}/download/'
        return request.build_absolute_uri(path) if request else path

    def get_size_mb(self, obj):
        return round(obj.file_size / (1024 * 1024), 2)

    def get_upload_count(self, obj):
        # A reference reports how many uploads share its content (the original's count).
        if obj.is_reference and obj.original_file is not None:
            return obj.original_file.upload_count
        return obj.upload_count
