from rest_framework import serializers

from .models import FileMetadata


class FileMetadataSerializer(serializers.ModelSerializer):
    """
    Read-only representation of a user's file, matching the API contract:

        id, file, original_filename, file_type, size, uploaded_at, user_id,
        file_hash, reference_count, is_reference, original_file
    """

    # Uploaded files are not served publicly; `file` is the authenticated download URL
    # (send the same UserId header to fetch it).
    file = serializers.SerializerMethodField()
    reference_count = serializers.SerializerMethodField()

    class Meta:
        model = FileMetadata
        fields = [
            'id', 'file', 'original_filename', 'file_type', 'size', 'uploaded_at',
            'user_id', 'file_hash', 'reference_count', 'is_reference', 'original_file',
        ]
        read_only_fields = fields

    def get_file(self, obj):
        request = self.context.get('request')
        path = f'/api/files/{obj.pk}/download/'
        return request.build_absolute_uri(path) if request else path

    def get_reference_count(self, obj):
        # A reference reports how many uploads share its content (the original's count).
        if obj.is_reference and obj.original_file is not None:
            return obj.original_file.reference_count
        return obj.reference_count
