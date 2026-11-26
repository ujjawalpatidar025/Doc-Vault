import hashlib
import os
import shutil
import tempfile

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APITestCase

FILES_URL = '/api/files/'


class FileVaultTestCase(APITestCase):
    """
    Isolated MEDIA_ROOT, a fresh cache, and a rate limit high enough that normal
    tests never hit it (the rate-limit tests lower it explicitly).
    """

    def setUp(self):
        super().setUp()
        self.media_root = tempfile.mkdtemp(prefix='file-vault-tests-')
        self.addCleanup(shutil.rmtree, self.media_root, ignore_errors=True)
        overrides = override_settings(
            MEDIA_ROOT=self.media_root,
            RATE_LIMIT_CALLS=10_000,
            RATE_LIMIT_WINDOW_SECONDS=1,
            USER_STORAGE_LIMIT_BYTES=10 * 1024 * 1024,
        )
        overrides.enable()
        self.addCleanup(overrides.disable)
        cache.clear()
        self.addCleanup(cache.clear)

    def upload(self, content=b'hello world', name='hello.txt', user='alice', content_type='text/plain'):
        upload = SimpleUploadedFile(name, content, content_type=content_type)
        return self.client.post(FILES_URL, {'file': upload}, format='multipart', HTTP_USERID=user)

    def get(self, url=FILES_URL, user='alice', **params):
        return self.client.get(url, params, HTTP_USERID=user)

    def delete(self, file_id, user='alice'):
        return self.client.delete(f'{FILES_URL}{file_id}/', HTTP_USERID=user)

    def results(self, response):
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()['results']

    def stored_blobs(self):
        uploads_dir = os.path.join(self.media_root, 'uploads')
        return sorted(os.listdir(uploads_dir)) if os.path.isdir(uploads_dir) else []

    @staticmethod
    def sha256(content):
        return hashlib.sha256(content).hexdigest()
