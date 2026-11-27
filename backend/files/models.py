import hashlib

from django.db import models
from django.db.models import Q


class FileMetadata(models.Model):
    """
    One file as seen by one user (identified by the `UserId` request header).

    Deduplication: a user's first upload of some content (by SHA-256) is the
    *original* and owns the physical blob in storage. Every later upload of the
    same content by that user becomes a *reference*: its own row, with its own
    filename and upload time, pointing at the original and sharing its blob, so the
    bytes are stored once.

    `reference_count` on an original counts every row sharing the blob (original
    included). Deduplication is per user on purpose: across users it would tell
    user B that user A already holds a given file.
    """

    user_id = models.CharField(max_length=255)
    original_filename = models.CharField(max_length=255)
    file_hash = models.CharField(max_length=64)  # SHA-256 hex digest
    file_path = models.CharField(max_length=500)  # path of the blob, relative to MEDIA_ROOT
    size = models.BigIntegerField()  # bytes
    file_type = models.CharField(max_length=100, blank=True)  # MIME type
    uploaded_at = models.DateTimeField(auto_now_add=True)
    reference_count = models.PositiveIntegerField(default=1)
    is_reference = models.BooleanField(default=False)
    original_file = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.PROTECT,  # deletes go through services.delete_file
        related_name='references',
    )

    class Meta:
        ordering = ['-uploaded_at']
        indexes = [
            # Every query is scoped to one user, so user_id leads each index.
            models.Index(fields=['user_id', '-uploaded_at'], name='file_user_uploaded_idx'),
            models.Index(fields=['user_id', 'original_filename'], name='file_user_name_idx'),
            models.Index(fields=['user_id', 'file_type'], name='file_user_mime_idx'),
            models.Index(fields=['user_id', 'size'], name='file_user_size_idx'),
            # Storage accounting: SUM(size) WHERE user_id = ? AND is_reference = false
            models.Index(fields=['user_id', 'is_reference'], name='file_user_isref_idx'),
        ]
        constraints = [
            # At most one original per (user, content). This partial unique index also
            # serves the duplicate lookup on upload, and means two concurrent uploads of
            # the same content can't both become originals: the loser retries as a reference.
            models.UniqueConstraint(
                fields=['user_id', 'file_hash'],
                condition=Q(is_reference=False),
                name='unique_original_per_user_hash',
            ),
        ]

    def __str__(self):
        return f"{self.original_filename} ({self.file_hash[:8]})"

    @staticmethod
    def calculate_file_hash(file):
        """SHA-256 of an uploaded file, read in chunks so large files never sit in memory."""
        hash_sha256 = hashlib.sha256()
        file.seek(0)
        for chunk in file.chunks():
            hash_sha256.update(chunk)
        file.seek(0)
        return hash_sha256.hexdigest()
