from django.db import IntegrityError, transaction
from rest_framework import status

from files.models import FileMetadata

from .base import FILES_URL, FileVaultTestCase


class UploadDeduplicationTests(FileVaultTestCase):

    def test_first_upload_is_stored_as_original(self):
        response = self.upload(b'unique content', name='report.pdf', content_type='application/pdf')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        body = response.json()
        self.assertFalse(body['is_duplicate'])
        self.assertFalse(body['is_reference'])
        self.assertIsNone(body['original_file'])
        self.assertEqual(body['upload_count'], 1)
        self.assertEqual(body['file_hash'], self.sha256(b'unique content'))
        self.assertEqual(body['user_id'], 'alice')
        self.assertEqual(body['name'], 'report.pdf')
        self.assertEqual(body['mime_type'], 'application/pdf')
        self.assertEqual(body['file_size'], len(b'unique content'))
        self.assertEqual(len(self.stored_blobs()), 1)

    def test_duplicate_becomes_reference_and_writes_nothing_new(self):
        first = self.upload(b'same bytes', name='a.txt').json()
        second = self.upload(b'same bytes', name='copy-of-a.txt').json()

        self.assertTrue(second['is_duplicate'])
        self.assertTrue(second['is_reference'])
        self.assertEqual(second['original_file'], first['id'])
        self.assertEqual(second['name'], 'copy-of-a.txt')  # keeps its own name
        self.assertEqual(second['upload_count'], 2)
        self.assertEqual(len(self.stored_blobs()), 1)
        self.assertEqual(FileMetadata.objects.get(pk=first['id']).upload_count, 2)
        # Both entries are listed for the user.
        self.assertEqual(len(self.results(self.get())), 2)

    def test_different_content_is_not_deduplicated(self):
        self.upload(b'one')
        self.assertFalse(self.upload(b'two').json()['is_duplicate'])
        self.assertEqual(len(self.stored_blobs()), 2)

    def test_deduplication_is_per_user(self):
        self.upload(b'shared bytes', user='alice')
        response = self.upload(b'shared bytes', user='bob')

        # Bob must not learn that Alice already has this content.
        self.assertFalse(response.json()['is_duplicate'])

    def test_on_disk_name_is_random_not_user_supplied(self):
        self.upload(b'x', name='../../etc/passwd')
        [blob] = self.stored_blobs()
        self.assertNotIn('passwd', blob)

    def test_database_rejects_two_originals_for_same_user_and_content(self):
        fields = dict(user_id='alice', file_path='uploads/a', name='a', file_size=1, file_hash='h' * 64)
        FileMetadata.objects.create(**fields)
        with self.assertRaises(IntegrityError), transaction.atomic():
            FileMetadata.objects.create(**fields)


class StatsTests(FileVaultTestCase):

    def test_stats_report_savings(self):
        self.upload(b'a' * 100, name='one.txt')
        self.upload(b'a' * 100, name='two.txt')
        self.upload(b'b' * 50, name='three.txt')

        for url in (f'{FILES_URL}stats/', f'{FILES_URL}storage_stats/'):
            with self.subTest(url=url):
                stats = self.get(url).json()
                self.assertEqual(stats['user_id'], 'alice')
                self.assertEqual(stats['total_files'], 3)
                self.assertEqual(stats['unique_files'], 2)
                self.assertEqual(stats['duplicate_entries'], 1)
                self.assertEqual(stats['original_storage_used'], 250)
                self.assertEqual(stats['total_storage_used'], 150)
                self.assertEqual(stats['storage_savings'], 100)
                self.assertEqual(stats['savings_percentage'], 40.0)
                self.assertEqual(stats['space_saved_bytes'], 100)

    def test_stats_for_new_user_are_zero(self):
        stats = self.get(f'{FILES_URL}stats/', user='nobody').json()
        self.assertEqual(stats['total_files'], 0)
        self.assertEqual(stats['savings_percentage'], 0.0)

    def test_stats_use_a_single_query(self):
        for i in range(5):
            self.upload(b'z' * 10, name=f'{i}.txt')
        with self.assertNumQueries(1):
            self.get(f'{FILES_URL}stats/')


class DeleteTests(FileVaultTestCase):

    def test_deleting_reference_keeps_original_and_blob(self):
        original = self.upload(b'data').json()
        reference = self.upload(b'data', name='copy.txt').json()

        self.assertEqual(self.delete(reference['id']).status_code, status.HTTP_204_NO_CONTENT)

        self.assertEqual(FileMetadata.objects.get(pk=original['id']).upload_count, 1)
        self.assertEqual(len(self.stored_blobs()), 1)

    def test_deleting_original_promotes_oldest_reference(self):
        original = self.upload(b'data', name='orig.txt').json()
        heir = self.upload(b'data', name='ref1.txt').json()
        other = self.upload(b'data', name='ref2.txt').json()

        self.assertEqual(self.delete(original['id']).status_code, status.HTTP_204_NO_CONTENT)

        promoted = FileMetadata.objects.get(pk=heir['id'])
        self.assertFalse(promoted.is_reference)
        self.assertIsNone(promoted.original_file_id)
        self.assertEqual(promoted.upload_count, 2)
        self.assertEqual(FileMetadata.objects.get(pk=other['id']).original_file_id, promoted.pk)
        self.assertEqual(len(self.stored_blobs()), 1)
        # Remaining copies still download.
        response = self.get(f'{FILES_URL}{other["id"]}/download/')
        self.assertEqual(b''.join(response.streaming_content), b'data')

    def test_upload_after_promotion_references_new_original(self):
        original = self.upload(b'data').json()
        heir = self.upload(b'data', name='ref.txt').json()
        self.delete(original['id'])

        again = self.upload(b'data', name='again.txt').json()
        self.assertEqual(again['original_file'], heir['id'])

    def test_deleting_last_copy_removes_blob(self):
        original = self.upload(b'data').json()

        with self.captureOnCommitCallbacks(execute=True):
            self.delete(original['id'])

        self.assertEqual(self.stored_blobs(), [])
        self.assertFalse(FileMetadata.objects.exists())

    def test_cannot_delete_another_users_file(self):
        original = self.upload(b'data', user='alice').json()
        self.assertEqual(self.delete(original['id'], user='mallory').status_code, 404)
        self.assertTrue(FileMetadata.objects.filter(pk=original['id']).exists())


class DownloadTests(FileVaultTestCase):

    def test_download_returns_content_as_attachment(self):
        file_id = self.upload(b'pdf bytes', name='doc.pdf', content_type='application/pdf').json()['id']

        response = self.get(f'{FILES_URL}{file_id}/download/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(b''.join(response.streaming_content), b'pdf bytes')
        self.assertIn('attachment', response['Content-Disposition'])
        self.assertIn('doc.pdf', response['Content-Disposition'])

    def test_cannot_download_another_users_file(self):
        file_id = self.upload(b'secret', user='alice').json()['id']
        self.assertEqual(self.get(f'{FILES_URL}{file_id}/download/', user='bob').status_code, 404)
