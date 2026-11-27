"""
Validated search & filtering for GET /api/files/.

All parameters are optional and combine with AND:

    search            case-insensitive partial match on the original filename
    file_type         MIME type: "application/pdf" (exact), "image/png,image/jpeg" (any of),
                      or a bare category like "image" (prefix match)
    min_size          minimum size in bytes, inclusive
    max_size          maximum size in bytes, inclusive
    start_date        uploaded at/after: ISO 8601 datetime with timezone
                      (e.g. 2025-01-31T10:00:00+05:30 or ...Z), or a bare date (YYYY-MM-DD)
    end_date          uploaded at/before; a bare date includes that whole day
    duplicates_only   "true" to show only files whose content was uploaded more than once
    ordering          uploaded_at | original_filename | size | file_type, "-" for descending

Older names are still accepted as aliases: mime_type, date_from, date_to.

Bad values return HTTP 400 with a message per field instead of crashing.
"""
import datetime

from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from rest_framework import serializers

ORDERING_FIELDS = ('uploaded_at', 'original_filename', 'size', 'file_type')
DEFAULT_ORDERING = '-uploaded_at'
PARAM_ALIASES = {'mime_type': 'file_type', 'date_from': 'start_date', 'date_to': 'end_date'}


class FlexibleDateTimeField(serializers.Field):
    """Accepts an ISO datetime or a bare ISO date. Returns (aware datetime, is_date_only)."""

    default_error_messages = {
        'invalid': 'Use an ISO 8601 date (YYYY-MM-DD) or datetime (YYYY-MM-DDTHH:MM:SS).',
    }

    def to_internal_value(self, data):
        value = str(data).strip()
        # Try a bare date first: on Python 3.11+ parse_datetime also accepts
        # "2025-03-20" (as midnight), which would make end_date exclude that day.
        try:
            parsed_date = parse_date(value)
        except ValueError:  # well-formed but impossible, e.g. 2025-02-30
            self.fail('invalid')
        if parsed_date is not None:
            start_of_day = datetime.datetime.combine(parsed_date, datetime.time.min)
            return timezone.make_aware(start_of_day), True
        try:
            parsed = parse_datetime(value)
        except ValueError:
            parsed = None
        if parsed is None:
            self.fail('invalid')
        if timezone.is_naive(parsed):
            parsed = timezone.make_aware(parsed)
        return parsed, False

    def to_representation(self, value):
        return value


class FileFilterSerializer(serializers.Serializer):
    search = serializers.CharField(required=False, allow_blank=True, max_length=255)
    file_type = serializers.CharField(required=False, allow_blank=True, max_length=1000)
    min_size = serializers.IntegerField(required=False, min_value=0)
    max_size = serializers.IntegerField(required=False, min_value=0)
    start_date = FlexibleDateTimeField(required=False)
    end_date = FlexibleDateTimeField(required=False)
    duplicates_only = serializers.BooleanField(required=False, default=False)
    ordering = serializers.ChoiceField(
        required=False,
        choices=[choice for name in ORDERING_FIELDS for choice in (name, f'-{name}')],
    )

    def validate(self, attrs):
        min_size, max_size = attrs.get('min_size'), attrs.get('max_size')
        if min_size is not None and max_size is not None and min_size > max_size:
            raise serializers.ValidationError({'min_size': 'min_size cannot be greater than max_size.'})
        start, end = attrs.get('start_date'), attrs.get('end_date')
        if start and end and start[0] > end[0]:
            raise serializers.ValidationError({'start_date': 'start_date cannot be after end_date.'})
        return attrs


def _normalise(query_params):
    """Single-valued dict with aliases mapped and blank values dropped (the UI sends empty strings)."""
    params = {}
    for key, value in query_params.items():
        if value is None or str(value).strip() == '':
            continue
        params[PARAM_ALIASES.get(key, key)] = value
    return params


def apply_filters(queryset, query_params):
    params = FileFilterSerializer(data=_normalise(query_params))
    params.is_valid(raise_exception=True)
    data = params.validated_data

    search = data.get('search', '').strip()
    if search:
        queryset = queryset.filter(original_filename__icontains=search)

    file_types = [t.strip() for t in data.get('file_type', '').split(',') if t.strip()]
    if file_types:
        condition = Q()
        for file_type in file_types:
            # Full types use the (user_id, file_type) index; a bare "image" matches image/*.
            condition |= (
                Q(file_type=file_type) if '/' in file_type
                else Q(file_type__istartswith=f'{file_type}/')
            )
        queryset = queryset.filter(condition)

    if 'min_size' in data:
        queryset = queryset.filter(size__gte=data['min_size'])
    if 'max_size' in data:
        queryset = queryset.filter(size__lte=data['max_size'])

    if 'start_date' in data:
        queryset = queryset.filter(uploaded_at__gte=data['start_date'][0])
    if 'end_date' in data:
        end, date_only = data['end_date']
        if date_only:
            queryset = queryset.filter(uploaded_at__lt=end + datetime.timedelta(days=1))
        else:
            queryset = queryset.filter(uploaded_at__lte=end)

    if data.get('duplicates_only'):
        # References, plus originals whose content has at least one reference.
        queryset = queryset.filter(Q(is_reference=True) | Q(reference_count__gt=1))

    ordering = data.get('ordering', DEFAULT_ORDERING)
    # Tie-break on id so pages are stable when values are equal.
    return queryset.order_by(ordering, '-id' if ordering.startswith('-') else 'id')
