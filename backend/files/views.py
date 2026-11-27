from django.core.files.storage import default_storage
from django.http import FileResponse
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from . import services
from .filters import apply_filters
from .models import FileMetadata
from .serializers import FileMetadataSerializer


class FileMetadataViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """
    Files of the caller identified by the `UserId` header. Each user only ever
    sees their own files; other users' IDs return 404.

    - Upload with per-user deduplication
    - Validated search & filtering (see files/filters.py)
    - Download, delete, storage statistics
    - Every call is rate limited per user; uploads are subject to a storage quota
    """

    serializer_class = FileMetadataSerializer
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    lookup_value_regex = r'\d+'  # non-numeric IDs 404 instead of erroring

    def get_queryset(self):
        return (
            FileMetadata.objects.filter(user_id=self.request.user.user_id)
            .select_related('original_file')  # serializer reads it for references: avoid N+1
        )

    def filter_queryset(self, queryset):
        if self.action == 'list':
            return apply_filters(queryset, self.request.query_params)
        return queryset

    def create(self, request, *args, **kwargs):
        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            return Response({'error': 'No file provided'}, status=status.HTTP_400_BAD_REQUEST)

        file_metadata, is_duplicate = services.save_file_with_deduplication(
            uploaded_file, user_id=request.user.user_id
        )
        data = self.get_serializer(file_metadata).data
        return Response(
            {
                **data,
                'is_duplicate': is_duplicate,
                'message': (
                    'Duplicate file detected, referencing existing file'
                    if is_duplicate else 'File uploaded successfully'
                ),
            },
            status=status.HTTP_201_CREATED,
        )

    def perform_destroy(self, instance):
        services.delete_file(instance)

    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        file_metadata = self.get_object()  # scoped to the caller
        if not default_storage.exists(file_metadata.file_path):
            return Response({'error': 'File not found on disk'}, status=status.HTTP_404_NOT_FOUND)
        return FileResponse(
            default_storage.open(file_metadata.file_path, 'rb'),
            as_attachment=True,
            filename=file_metadata.original_filename,
            content_type=file_metadata.file_type or 'application/octet-stream',
        )

    @action(detail=False, methods=['get'])
    def stats(self, request):
        return Response(services.get_storage_stats(request.user.user_id))

    @action(detail=False, methods=['get'])
    def storage_stats(self, request):
        return Response(services.get_storage_stats(request.user.user_id))

    @action(detail=False, methods=['get'])
    def file_types(self, request):
        file_types = (
            FileMetadata.objects.filter(user_id=request.user.user_id)
            .order_by('file_type')
            .values_list('file_type', flat=True)
            .distinct()
        )
        return Response(list(file_types))
