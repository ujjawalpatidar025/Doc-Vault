import datetime

from django.utils import timezone
from rest_framework import status

from files.models import FileMetadata

from .base import FILES_URL, FileVaultTestCase


def aware(year, month, day, hour=12):
    return timezone.make_aware(datetime.datetime(year, month, day, hour))


class SearchAndFilterTests(FileVaultTestCase):

    def setUp(self):
        super().setUp()
        fixtures = [
            ('Quarterly Report.pdf', b'r' * 1000, 'application/pdf', aware(2025, 1, 10)),
            ('holiday-photo.png', b'p' * 5000, 'image/png', aware(2025, 2, 15)),
            ('report-draft.docx', b'd' * 200, 'application/msword', aware(2025, 3, 20, 23)),
            ('logo.jpg', b'j' * 3000, 'image/jpeg', aware(2025, 4, 1)),
        ]
        self.ids = {}
        for name, content, mime, uploaded_at in fixtures:
            file_id = self.upload(content, name=name, content_type=mime).json()['id']
            FileMetadata.objects.filter(pk=file_id).update(uploaded_at=uploaded_at)
            self.ids[name] = file_id
        # Another user's matching file must never show up in alice's results.
        self.upload(b'secret', name='report-of-bob.pdf', user='bob', content_type='application/pdf')

    def names(self, response):
        return [f['original_filename'] for f in self.results(response)]

    def test_lists_only_own_files_newest_first(self):
        self.assertEqual(
            self.names(self.get()),
            ['logo.jpg', 'report-draft.docx', 'holiday-photo.png', 'Quarterly Report.pdf'],
        )

    def test_search_is_case_insensitive(self):
        self.assertEqual(
            sorted(self.names(self.get(search='REPORT'))),
            ['Quarterly Report.pdf', 'report-draft.docx'],
        )

    def test_filter_by_exact_file_type(self):
        self.assertEqual(self.names(self.get(file_type='image/png')), ['holiday-photo.png'])

    def test_filter_by_several_file_types(self):
        self.assertEqual(
            sorted(self.names(self.get(file_type='image/png,application/pdf'))),
            ['Quarterly Report.pdf', 'holiday-photo.png'],
        )

    def test_filter_by_mime_category(self):
        self.assertEqual(sorted(self.names(self.get(file_type='image'))), ['holiday-photo.png', 'logo.jpg'])

    def test_filter_by_size_range_inclusive(self):
        self.assertEqual(
            sorted(self.names(self.get(min_size=1000, max_size=3000))),
            ['Quarterly Report.pdf', 'logo.jpg'],
        )

    def test_bare_end_date_includes_the_whole_day(self):
        # report-draft was uploaded at 23:00 on 2025-03-20.
        self.assertEqual(
            sorted(self.names(self.get(start_date='2025-02-01', end_date='2025-03-20'))),
            ['holiday-photo.png', 'report-draft.docx'],
        )

    def test_iso8601_datetimes_with_timezone(self):
        # The contract specifies ISO 8601 with timezone, e.g. ...Z or ...+05:30.
        self.assertEqual(
            sorted(self.names(self.get(start_date='2025-02-15T00:00:00Z', end_date='2025-03-20T23:30:00+00:00'))),
            ['holiday-photo.png', 'report-draft.docx'],
        )
        # 2025-04-01T17:00+05:30 is 11:30 UTC, just before logo.jpg's 12:00 UTC upload.
        self.assertEqual(self.names(self.get(start_date='2025-04-01T17:00:00+05:30')), ['logo.jpg'])

    def test_old_parameter_names_still_work(self):
        self.assertEqual(self.names(self.get(mime_type='image/png')), ['holiday-photo.png'])
        self.assertEqual(self.names(self.get(date_from='2025-03-31')), ['logo.jpg'])

    def test_datetime_without_timezone_uses_server_time_zone(self):
        self.assertEqual(self.names(self.get(start_date='2025-03-31T00:00:00')), ['logo.jpg'])

    def test_duplicates_only(self):
        self.upload(b'p' * 5000, name='photo-copy.png', content_type='image/png')
        self.assertEqual(
            sorted(self.names(self.get(duplicates_only='true'))),
            ['holiday-photo.png', 'photo-copy.png'],
        )

    def test_blank_parameters_are_ignored(self):
        # The React filter form sends empty strings for unused fields.
        response = self.get(search='', min_size='', file_type='', start_date='', duplicates_only='false')
        self.assertEqual(len(self.names(response)), 4)

    def test_filters_combine(self):
        self.assertEqual(
            self.names(self.get(search='report', file_type='application/pdf', max_size=1000)),
            ['Quarterly Report.pdf'],
        )

    def test_ordering(self):
        self.assertEqual(
            self.names(self.get(ordering='size')),
            ['report-draft.docx', 'Quarterly Report.pdf', 'logo.jpg', 'holiday-photo.png'],
        )

    def test_invalid_parameters_return_400_not_500(self):
        for params in (
            {'min_size': 'abc'},
            {'min_size': -1},
            {'start_date': 'yesterday'},
            {'end_date': '2025-02-30'},
            {'ordering': 'file_hash'},
            {'min_size': 500, 'max_size': 100},
            {'start_date': '2025-05-01', 'end_date': '2025-01-01'},
        ):
            with self.subTest(params=params):
                self.assertEqual(self.get(**params).status_code, status.HTTP_400_BAD_REQUEST)

    def test_file_types_lists_distinct_own_types(self):
        self.assertEqual(
            self.get(f'{FILES_URL}file_types/').json(),
            ['application/msword', 'application/pdf', 'image/jpeg', 'image/png'],
        )

    def test_retrieve_other_users_file_is_404(self):
        self.assertEqual(self.get(f'{FILES_URL}{self.ids["logo.jpg"]}/', user='bob').status_code, 404)

    def test_list_query_count_is_constant(self):
        self.upload(b'r' * 1000, name='dup.pdf', content_type='application/pdf')  # a reference
        with self.assertNumQueries(2):  # page count + page rows, regardless of row count
            self.get()
