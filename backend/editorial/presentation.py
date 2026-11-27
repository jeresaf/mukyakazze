"""Draft cover and grid settings. Editorial layout never changes event time."""
from collections import defaultdict
from datetime import timedelta
from zoneinfo import ZoneInfo
from django.db import transaction
from rest_framework import serializers
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView
from accounts.serializers import StrictSerializer
from accounts.services import audit
from catalog.directory import directory_lock
from catalog.models import MediaAsset
from .api import EditorialAccess, conflict, eligible
from .models import Issue

KAMPALA = ZoneInfo('Africa/Kampala')
SLOTS = ['6PM', '8PM', '10PM', 'MIDNIGHT', '2AM+']


class CoverLine(StrictSerializer):
    title = serializers.CharField(max_length=120, allow_blank=True)
    body = serializers.CharField(max_length=300, allow_blank=True)

    def validate(self, attrs):
        if bool(attrs['title']) != bool(attrs['body']):
            raise serializers.ValidationError('Provide both headline and text, or leave both blank.')
        return attrs


class CoverInput(StrictSerializer):
    expected_version = serializers.IntegerField(min_value=1)
    accent = serializers.RegexField(r'^#[0-9a-fA-F]{6}$')
    name = serializers.CharField(max_length=150, allow_blank=True)
    subtitle = serializers.CharField(max_length=250, allow_blank=True)
    lines = CoverLine(many=True, max_length=3)
    photo_id = serializers.UUIDField(allow_null=True)
    headshot_id = serializers.UUIDField(allow_null=True)


def asset_output(asset, kind):
    if asset is None:
        return None
    return {'id': str(asset.pk), 'name': asset.name, 'version': asset.version,
            'valid': asset.is_active and asset.kind == kind, 'width': asset.width,
            'height': asset.height, 'mime_type': asset.mime_type}


def cover_data(issue):
    assets = MediaAsset.objects.defer('content').in_bulk([x for x in (issue.cover_photo_id, issue.headshot_id) if x])
    photo = asset_output(assets.get(issue.cover_photo_id), 'cover')
    headshot = asset_output(assets.get(issue.headshot_id), 'photo')
    warnings = []
    for label, asset in [('Cover photo', photo), ('Curator headshot', headshot)]:
        if asset and not asset['valid']:
            warnings.append(label + ' is archived or no longer the correct media type.')
    if photo and photo['mime_type'] != 'image/png':
        warnings.append('Transparent PNG is preferred for the cover cut-out.')
    if headshot and headshot['width'] != headshot['height']:
        warnings.append('Square curator headshot is preferred.')
    return {'version': issue.version, 'accent': issue.cover_accent, 'name': issue.cover_name,
            'subtitle': issue.cover_subtitle, 'lines': issue.cover_lines, 'photo': photo,
            'headshot': headshot, 'warnings': warnings}


def cover_snapshot(issue):
    return {'accent': issue.cover_accent, 'name': issue.cover_name, 'subtitle': issue.cover_subtitle,
            'lines': issue.cover_lines, 'photo_id': str(issue.cover_photo_id) if issue.cover_photo_id else None,
            'headshot_id': str(issue.headshot_id) if issue.headshot_id else None}


class Cover(APIView):
    permission_classes = [EditorialAccess]

    def get(self, request, pk):
        return Response(cover_data(get_object_or_404(Issue, pk=pk)))

    @transaction.atomic
    def put(self, request, pk):
        data = CoverInput(data=request.data); data.is_valid(raise_exception=True)
        v = data.validated_data
        directory_lock()
        issue = get_object_or_404(Issue.objects.select_for_update(), pk=pk)
        if issue.version != v['expected_version']:
            return conflict()
        ids = sorted({x for x in (v['photo_id'], v['headshot_id']) if x})
        assets = MediaAsset.objects.defer('content').select_for_update().in_bulk(ids)
        for field, kind in [('photo_id', 'cover'), ('headshot_id', 'photo')]:
            key = v[field]
            if key and (key not in assets or not assets[key].is_active or assets[key].kind != kind):
                raise serializers.ValidationError({field: 'Select an active image of the correct media type.'})
        before = cover_snapshot(issue)
        issue.cover_accent = v['accent'].upper()
        issue.cover_name = v['name']; issue.cover_subtitle = v['subtitle']
        issue.cover_lines = list(v['lines']); issue.cover_photo_id = v['photo_id']; issue.headshot_id = v['headshot_id']
        issue.version += 1; issue.save()
        audit(request.user, 'issue_cover_updated', issue.pk, before=before, after=cover_snapshot(issue), version=issue.version)
        return Response(cover_data(issue))


def slot_for(row, day):
    if not row.starts_at:
        return None
    local = row.starts_at.astimezone(KAMPALA)
    hour = local.hour
    if local.date() == day:
        if 17 <= hour < 20: return 0
        if 20 <= hour < 22: return 1
        if hour >= 22: return 2
    elif local.date() == day + timedelta(days=1):
        if hour < 2: return 3
        if hour < 4: return 4
    return None


def grid_candidates(issue):
    rows = []
    entries = issue.entries.select_related('occurrence__event__category', 'occurrence__venue').filter(occurrence__editorial_date=issue.grid_day)
    for entry in entries:
        row = entry.occurrence; cat = row.event.category
        slot = slot_for(row, issue.grid_day)
        if not eligible(issue, row) or not cat or slot is None or row.version != entry.occurrence_version:
            continue
        rows.append({'occurrence_id': str(row.pk), 'occurrence_version': row.version, 'title': row.event.title,
                     'category_id': str(cat.pk), 'category': cat.label, 'colour': cat.colour, 'order': cat.display_order,
                     'venue': row.venue.name if row.venue else '', 'starts_at': row.starts_at.astimezone(KAMPALA).isoformat(), 'slot': slot})
    return sorted(rows, key=lambda x: (x['order'], x['category'], x['slot'], x['starts_at'], x['occurrence_id']))


def grid_data(issue):
    candidates = grid_candidates(issue)
    by_id = {x['occurrence_id']: x for x in candidates}
    configuration = issue.grid_configuration
    warnings = []
    explicit = bool(configuration)
    if explicit and configuration['day'] != issue.grid_day.isoformat():
        warnings.append('Grid date changed. Review and save a new grid configuration.')
        placements = []
    else:
        placements = configuration.get('entries', []) if explicit else [dict(occurrence_id=x['occurrence_id'], occurrence_version=x['occurrence_version'], span=1) for x in candidates]
    cells = defaultdict(list); visible = []
    for item in placements:
        row = by_id.get(item['occurrence_id'])
        if not row or row['occurrence_version'] != item['occurrence_version']:
            warnings.append('A saved grid entry is stale or no longer eligible: ' + item['occurrence_id'])
            continue
        if row['slot'] + item['span'] > len(SLOTS):
            warnings.append('Span exceeds grid: ' + row['title']); continue
        visible.append({**row, 'span': item['span']})
        for index in range(row['slot'], row['slot'] + item['span']):
            cells[(row['category_id'], index)].append(row['title'])
    for (_, index), titles in cells.items():
        if len(titles) > 1:
            warnings.append(f"Collision at {SLOTS[index]}: " + ' / '.join(titles))
    if len({x['category_id'] for x in visible}) > 8:
        warnings.append('More than eight category rows; refine the grid selection.')
    return {'version': issue.version, 'grid_day': issue.grid_day.isoformat(), 'slots': SLOTS, 'candidates': candidates,
            'placements': visible, 'explicit': explicit, 'warnings': warnings}


class GridEntry(StrictSerializer):
    occurrence_id = serializers.UUIDField()
    occurrence_version = serializers.IntegerField(min_value=1)
    span = serializers.IntegerField(min_value=1, max_value=5)


class GridInput(StrictSerializer):
    expected_version = serializers.IntegerField(min_value=1)
    entries = GridEntry(many=True, max_length=500)

    def validate_entries(self, entries):
        ids = [x['occurrence_id'] for x in entries]
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError('An occurrence may only appear once.')
        return entries


class Grid(APIView):
    permission_classes = [EditorialAccess]

    def get(self, request, pk):
        return Response(grid_data(get_object_or_404(Issue, pk=pk)))

    @transaction.atomic
    def put(self, request, pk):
        data = GridInput(data=request.data); data.is_valid(raise_exception=True)
        directory_lock()
        issue = get_object_or_404(Issue.objects.select_for_update(), pk=pk)
        if issue.version != data.validated_data['expected_version']:
            return conflict()
        candidates = {x['occurrence_id']: x for x in grid_candidates(issue)}
        entries = []
        for item in data.validated_data['entries']:
            key = str(item['occurrence_id']); row = candidates.get(key)
            if not row or row['occurrence_version'] != item['occurrence_version']:
                return conflict()
            if row['slot'] + item['span'] > len(SLOTS):
                raise serializers.ValidationError({'entries': 'Span must fit from its actual time slot.'})
            entries.append({**item, 'occurrence_id': key})
        before = issue.grid_configuration
        issue.grid_configuration = {'day': issue.grid_day.isoformat(), 'entries': entries}
        issue.version += 1; issue.save()
        audit(request.user, 'issue_grid_updated', issue.pk, before=before, after=issue.grid_configuration, version=issue.version)
        return Response(grid_data(issue))
