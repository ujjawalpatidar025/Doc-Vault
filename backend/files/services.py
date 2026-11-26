"""
Business logic for uploads, deduplication, deletion and storage accounting.
Kept out of the views so it can be tested and reused without HTTP.
"""
import logging
import os
import re
import uuid

from django.conf import settings
from django.core.files.storage import default_storage
from django.db import IntegrityError, transaction
from django.db.models import Count, F, Q, Sum

from .exceptions import StorageQuotaExceeded
from .models import FileMetadata

logger = logging.getLogger(__name__)

DEFAULT_MIME_TYPE = 'application/octet-stream'
_SAFE_EXTENSION = re.compile(r'^\.[a-z0-9]{1,10}$')


def _blob_name(original_name):
    """Random on-disk name: user-supplied filenames never touch the filesystem."""
    ext = os.path.splitext(original_name)[1].lower()
    return f"uploads/{uuid.uuid4().hex}{ext if _SAFE_EXTENSION.match(ext) else ''}"


def get_storage_used(user_id):
    """Bytes physically stored for a user. Only originals count; references are free."""
    return (
        FileMetadata.objects.filter(user_id=user_id, is_reference=False)
        .aggregate(total=Sum('file_size', default=0))['total']
    )


def _ensure_quota(user_id, extra_bytes):
    used = get_storage_used(user_id)
    limit = settings.USER_STORAGE_LIMIT_BYTES
    if used + extra_bytes > limit:
        logger.info('Storage quota exceeded: user=%s used=%s incoming=%s limit=%s',
                    user_id, used, extra_bytes, limit)
        raise StorageQuotaExceeded()


def save_file_with_deduplication(uploaded_file, user_id):
    """
    Store an upload for `user_id`, deduplicating against that user's files.

    Returns (FileMetadata, is_duplicate). A duplicate gets its own row (keeping
    its own name and upload time) that references the original's blob.
    Raises StorageQuotaExceeded if new content would exceed the user's quota.
    """
    file_hash = FileMetadata.calculate_file_hash(uploaded_file)
    try:
        return _save(uploaded_file, user_id, file_hash)
    except IntegrityError:
        # Lost a race: a concurrent upload of the same content became the original
        # between our lookup and our insert. Retrying stores this one as a reference.
        logger.info('Dedup race for user=%s hash=%s; retrying as reference', user_id, file_hash)
        return _save(uploaded_file, user_id, file_hash)


def _save(uploaded_file, user_id, file_hash):
    common = {
        'user_id': user_id,
        'name': uploaded_file.name[:255],
        'file_hash': file_hash,
        'file_size': uploaded_file.size,
        'mime_type': (uploaded_file.content_type or DEFAULT_MIME_TYPE)[:100],
    }

    with transaction.atomic():
        original = (
            FileMetadata.objects.select_for_update()
            .filter(user_id=user_id, file_hash=file_hash, is_reference=False)
            .first()
        )
        if original is not None:
            FileMetadata.objects.filter(pk=original.pk).update(upload_count=F('upload_count') + 1)
            original.refresh_from_db(fields=['upload_count'])
            reference = FileMetadata.objects.create(
                file_path=original.file_path,
                is_reference=True,
                original_file=original,
                **common,
            )
            return reference, True

    # New content. Cheap pre-check so we never write bytes we will reject.
    _ensure_quota(user_id, uploaded_file.size)

    stored_path = default_storage.save(_blob_name(uploaded_file.name), uploaded_file)
    try:
        with transaction.atomic():
            file_metadata = FileMetadata.objects.create(file_path=stored_path, **common)
            # Re-check now that our row exists. On SQLite the write lock serialises
            # concurrent uploads, so two requests can't both slip under the limit.
            # (On Postgres, lock a per-user row to get the same guarantee.)
            _ensure_quota(user_id, 0)
    except Exception:
        default_storage.delete(stored_path)
        raise
    return file_metadata, False


@transaction.atomic
def delete_file(file_metadata):
    """
    Delete one user-visible file.

    - Reference: drop the row and decrement the original's count; the blob stays.
    - Original without references: drop the row, then the blob once the transaction commits.
    - Original with references: the oldest reference is promoted to original and
      inherits the blob, so every other copy keeps working.
    """
    file_metadata = FileMetadata.objects.select_for_update().get(pk=file_metadata.pk)

    if file_metadata.is_reference:
        FileMetadata.objects.filter(pk=file_metadata.original_file_id).update(
            upload_count=F('upload_count') - 1
        )
        file_metadata.delete()
        return

    references = list(
        FileMetadata.objects.select_for_update()
        .filter(original_file=file_metadata)
        .order_by('uploaded_at', 'id')
    )

    if not references:
        blob = file_metadata.file_path
        file_metadata.delete()
        transaction.on_commit(lambda: default_storage.delete(blob))
        return

    heir, others = references[0], references[1:]
    FileMetadata.objects.filter(pk__in=[ref.pk for ref in others]).update(original_file=heir)
    FileMetadata.objects.filter(pk=heir.pk).update(original_file=None)
    # Nothing points at the old original now, so PROTECT allows the delete. It must
    # happen before the heir becomes an original (one original per user + hash).
    file_metadata.delete()
    FileMetadata.objects.filter(pk=heir.pk).update(is_reference=False, upload_count=len(references))


def get_storage_stats(user_id):
    """One aggregate query; no Python-side loops over rows."""
    stats = FileMetadata.objects.filter(user_id=user_id).aggregate(
        total_files=Count('id'),
        unique_files=Count('id', filter=Q(is_reference=False)),
        original_storage_used=Sum('file_size', default=0),
        total_storage_used=Sum('file_size', filter=Q(is_reference=False), default=0),
    )
    logical = stats['original_storage_used']
    physical = stats['total_storage_used']
    saved = logical - physical
    limit = settings.USER_STORAGE_LIMIT_BYTES

    def mb(n):
        return round(n / (1024 * 1024), 2)

    return {
        'user_id': user_id,
        # File counts
        'total_files': stats['total_files'],
        'unique_files': stats['unique_files'],
        'duplicate_entries': stats['total_files'] - stats['unique_files'],
        # Storage: physical bytes on disk vs. bytes the user uploaded
        'total_storage_used': physical,
        'original_storage_used': logical,
        'storage_savings': saved,
        'savings_percentage': round(saved / logical * 100, 2) if logical else 0.0,
        # Quota
        'storage_limit': limit,
        'storage_remaining': max(limit - physical, 0),
        # Same figures in the shape the frontend already uses
        'total_size_bytes': physical,
        'total_size_mb': mb(physical),
        'space_saved_bytes': saved,
        'space_saved_mb': mb(saved),
        'storage_limit_mb': mb(limit),
    }
