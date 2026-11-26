from unittest import mock

from django.test import override_settings
from rest_framework import status

from files.models import FileMetadata

from .base import FILES_URL, FileVaultTestCase


class UserIdHeaderTests(FileVaultTestCase):

    def test_missing_user_id_is_rejected(self):
        response = self.client.get(FILES_URL)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.json(), {'error': 'UserId header is required'})

    def test_malformed_user_id_is_rejected(self):
        self.assertEqual(self.client.get(FILES_URL, HTTP_USERID='has spaces').status_code, 401)

    def test_upload_without_file_returns_400(self):
        response = self.client.post(FILES_URL, {}, format='multipart', HTTP_USERID='alice')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {'error': 'No file provided'})

    def test_update_is_not_allowed(self):
        file_id = self.upload().json()['id']
        response = self.client.patch(f'{FILES_URL}{file_id}/', {}, HTTP_USERID='alice')
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


class RateLimitTests(FileVaultTestCase):
    """Default policy: 2 calls per second per user."""

    def setUp(self):
        super().setUp()
        overrides = override_settings(RATE_LIMIT_CALLS=2, RATE_LIMIT_WINDOW_SECONDS=1)
        overrides.enable()
        self.addCleanup(overrides.disable)
        clock = mock.patch('files.throttling._now')
        self.now = clock.start()
        self.addCleanup(clock.stop)
        self.now.return_value = 1_000_000.10

    def test_third_call_in_a_second_is_rejected(self):
        self.assertEqual(self.get().status_code, 200)
        self.assertEqual(self.get().status_code, 200)

        response = self.get()

        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(response.json(), {'error': 'Call Limit Reached'})
        self.assertIn('Retry-After', response)

    def test_limit_covers_every_endpoint(self):
        self.upload()
        self.get(f'{FILES_URL}stats/')
        self.assertEqual(self.get(f'{FILES_URL}file_types/').status_code, 429)

    def test_limit_is_per_user(self):
        self.get(user='alice')
        self.get(user='alice')
        self.assertEqual(self.get(user='alice').status_code, 429)
        self.assertEqual(self.get(user='bob').status_code, 200)

    def test_calls_allowed_again_after_window(self):
        self.get()
        self.get()
        self.assertEqual(self.get().status_code, 429)
        self.now.return_value += 2.0
        self.assertEqual(self.get().status_code, 200)

    def test_no_double_burst_across_window_boundary(self):
        self.now.return_value = 1_000_000.95
        self.get()
        self.get()
        self.now.return_value = 1_000_001.05  # a fixed window would allow 2 more here
        self.assertEqual(self.get().status_code, 429)

    def test_rejected_calls_do_not_use_up_allowance(self):
        self.get()
        self.get()
        for _ in range(5):
            self.get()  # rejected
        self.now.return_value += 1.99
        self.assertEqual(self.get().status_code, 200)


class StorageQuotaTests(FileVaultTestCase):

    def setUp(self):
        super().setUp()
        overrides = override_settings(USER_STORAGE_LIMIT_BYTES=100)
        overrides.enable()
        self.addCleanup(overrides.disable)

    def test_upload_over_quota_is_rejected_and_nothing_stored(self):
        self.assertEqual(self.upload(b'a' * 60, name='a.bin').status_code, 201)

        response = self.upload(b'b' * 41, name='b.bin')

        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(response.json(), {'error': 'Storage Quota Exceeded'})
        self.assertEqual(FileMetadata.objects.count(), 1)
        self.assertEqual(len(self.stored_blobs()), 1)

    def test_upload_reaching_exactly_the_quota_is_allowed(self):
        self.upload(b'a' * 60)
        self.assertEqual(self.upload(b'b' * 40).status_code, 201)

    def test_single_file_bigger_than_quota_is_rejected(self):
        self.assertEqual(self.upload(b'z' * 101).status_code, 429)
        self.assertEqual(self.stored_blobs(), [])

    def test_duplicates_are_free(self):
        self.upload(b'a' * 90)
        response = self.upload(b'a' * 90, name='copy.bin')
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json()['is_duplicate'])

    def test_deleting_frees_quota(self):
        file_id = self.upload(b'a' * 90).json()['id']
        self.assertEqual(self.upload(b'b' * 20).status_code, 429)
        with self.captureOnCommitCallbacks(execute=True):
            self.delete(file_id)
        self.assertEqual(self.upload(b'b' * 20).status_code, 201)

    def test_quota_is_per_user(self):
        self.upload(b'a' * 100, user='alice')
        self.assertEqual(self.upload(b'b' * 100, user='bob').status_code, 201)

    def test_stats_show_limit_and_remaining(self):
        self.upload(b'a' * 30)
        stats = self.get(f'{FILES_URL}stats/').json()
        self.assertEqual(stats['storage_limit'], 100)
        self.assertEqual(stats['storage_remaining'], 70)
