"""
Validated search & filtering for GET /api/files/.

All parameters are optional and combine with AND:

    search            case-insensitive substring of the file name
    mime_type         "image/png" (exact), "image/png,image/jpeg" (any of), or a bare
                      category like "image" (prefix match). Alias: file_type
    min_size          minimum size in bytes, inclusive
    max_size          maximum size in bytes, inclusive
    date_from         uploaded on/after: ISO date (YYYY-MM-DD) or datetime. Alias: start_date
    date_to           uploaded on/before; a bare date includes that whole day. Alias: end_date
    duplicates_only   "true" to show only files whose content was uploaded more than once
    ordering          uploaded_at | name | file_size | mime_type, prefix "-" for descending

Bad values return HTTP 400 with a message per field instead of crashing.
"""
import datetime

from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from rest_framework import serializers

ORDERING_FIELDS = ('uploaded_at', 'name', 'file_size', 'mime_type')
DEFAULT_ORDERING = '-uploaded_at'
PARAM_ALIASES = {'file_type': 'mime_type', 'start_date': 'date_from', 'end_date': 'date_to'}


class FlexibleDateTimeField(serializers.Field):
    """Accepts an ISO datetime or a bare ISO date. Returns (aware datetime, is_date_only)."""

    default_error_messages = {
        'invalid': 'Use an ISO 8601 date (YYYY-MM-DD) or datetime (YYYY-MM-DDTHH:MM:SS).',
    }

    def to_internal_value(self, data):
        value = str(data).strip()
        # Try a bare date first: on Python 3.11+ parse_datetime also accepts
        # "2025-03-20" (as midnight), which would make date_to exclude that day.
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
    mime_type = serializers.CharField(required=False, allow_blank=True, max_length=1000)
    min_size = serializers.IntegerField(required=False, min_value=0)
    max_size = serializers.IntegerField(required=False, min_value=0)
    date_from = FlexibleDateTimeField(required=False)
    date_to = FlexibleDateTimeField(required=False)
    duplicates_only = serializers.BooleanField(required=False, default=False)
    ordering = serializers.ChoiceField(
        required=False,
        choices=[choice for name in ORDERING_FIELDS for choice in (name, f'-{name}')],
    )

    def validate(self, attrs):
        min_size, max_size = attrs.get('min_size'), attrs.get('max_size')
        if min_size is not None and max_size is not None and min_size > max_size:
            raise serializers.ValidationError({'min_size': 'min_size cannot be greater than max_size.'})
        date_from, date_to = attrs.get('date_from'), attrs.get('date_to')
        if date_from and date_to and date_from[0] > date_to[0]:
            raise serializers.ValidationError({'date_from': 'date_from cannot be after date_to.'})
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
        queryset = queryset.filter(name__icontains=search)

    mime_types = [m.strip() for m in data.get('mime_type', '').split(',') if m.strip()]
    if mime_types:
        condition = Q()
        for mime in mime_types:
            # Full types use the (user_id, mime_type) index; a bare "image" matches image/*.
            condition |= Q(mime_type=mime) if '/' in mime else Q(mime_type__istartswith=f'{mime}/')
        queryset = queryset.filter(condition)

    if 'min_size' in data:
        queryset = queryset.filter(file_size__gte=data['min_size'])
    if 'max_size' in data:
        queryset = queryset.filter(file_size__lte=data['max_size'])

    if 'date_from' in data:
        queryset = queryset.filter(uploaded_at__gte=data['date_from'][0])
    if 'date_to' in data:
        date_to, date_only = data['date_to']
        if date_only:
            queryset = queryset.filter(uploaded_at__lt=date_to + datetime.timedelta(days=1))
        else:
            queryset = queryset.filter(uploaded_at__lte=date_to)

    if data.get('duplicates_only'):
        # References, plus originals whose content has at least one reference.
        queryset = queryset.filter(Q(is_reference=True) | Q(upload_count__gt=1))

    ordering = data.get('ordering', DEFAULT_ORDERING)
    # Tie-break on id so pages are stable when values are equal.
    return queryset.order_by(ordering, '-id' if ordering.startswith('-') else 'id')
