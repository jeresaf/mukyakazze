"""Draft feature content and explicitly unverified editorial teasers."""
from django.db import transaction
from rest_framework import serializers
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView
from accounts.serializers import StrictSerializer
from accounts.services import audit
from catalog.directory import directory_lock
from catalog.models import Category, MediaAsset, Sponsor
from .api import EditorialAccess, conflict, week_end
from .models import Issue, ComingUp
from .presentation import asset_output


class Tip(StrictSerializer):
    title = serializers.CharField(max_length=120)
    body = serializers.CharField(max_length=500)


class FeatureInput(StrictSerializer):
    expected_version = serializers.IntegerField(min_value=1)
    feature_title = serializers.CharField(max_length=150, allow_blank=True)
    feature_subtitle = serializers.CharField(max_length=250, allow_blank=True)
    feature_kicker = serializers.CharField(max_length=150, allow_blank=True)
    feature_tips = Tip(many=True, max_length=5)
    sponsor_id = serializers.UUIDField(allow_null=True)
    sponsor_logo_id = serializers.UUIDField(allow_null=True)
    website_label = serializers.CharField(max_length=250, allow_blank=True)
    whatsapp_label = serializers.CharField(max_length=250, allow_blank=True)
    submission_contact = serializers.CharField(max_length=250, allow_blank=True)

    def validate(self, attrs):
        if attrs['sponsor_logo_id'] and not attrs['sponsor_id']:
            raise serializers.ValidationError({'sponsor_logo_id': 'Select a sponsor before its logo.'})
        return attrs


FEATURE_FIELDS = ('feature_title', 'feature_subtitle', 'feature_kicker', 'feature_tips', 'website_label', 'whatsapp_label', 'submission_contact')


def feature_snapshot(issue):
    return {**{k: getattr(issue, k) for k in FEATURE_FIELDS},
            'sponsor_id': str(issue.sponsor_id) if issue.sponsor_id else None,
            'sponsor_logo_id': str(issue.sponsor_logo_id) if issue.sponsor_logo_id else None}


def feature_data(issue):
    sponsor = Sponsor.objects.filter(pk=issue.sponsor_id).first() if issue.sponsor_id else None
    logo = MediaAsset.objects.defer('content').filter(pk=issue.sponsor_logo_id).first() if issue.sponsor_logo_id else None
    logo_data = asset_output(logo, 'logo')
    warnings = [f'Tip {i} exceeds the suggested 110-character layout length.' for i, tip in enumerate(issue.feature_tips, 1) if len(tip['body']) > 110]
    if sponsor and not sponsor.is_active:
        warnings.append('Selected sponsor is archived.')
    if logo_data and not logo_data['valid']:
        warnings.append('Selected sponsor logo is archived or invalid.')
    if sponsor and not logo:
        warnings.append('Sponsor selected without a logo.')
    return {**feature_snapshot(issue), 'version': issue.version, 'sponsor': {'id': str(sponsor.pk), 'name': sponsor.name, 'valid': sponsor.is_active} if sponsor else None,
            'logo': logo_data, 'warnings': warnings}


class Feature(APIView):
    permission_classes = [EditorialAccess]

    def get(self, request, pk):
        return Response(feature_data(get_object_or_404(Issue, pk=pk)))

    @transaction.atomic
    def put(self, request, pk):
        data = FeatureInput(data=request.data); data.is_valid(raise_exception=True)
        values = dict(data.validated_data)
        directory_lock()
        issue = get_object_or_404(Issue.objects.select_for_update(), pk=pk)
        if issue.version != values.pop('expected_version'):
            return conflict()
        if values['sponsor_id'] and not Sponsor.objects.select_for_update().filter(pk=values['sponsor_id'], is_active=True).exists():
            raise serializers.ValidationError({'sponsor_id': 'Select an active sponsor.'})
        if values['sponsor_logo_id'] and not MediaAsset.objects.select_for_update().filter(pk=values['sponsor_logo_id'], is_active=True, kind='logo').exists():
            raise serializers.ValidationError({'sponsor_logo_id': 'Select an active logo image.'})
        before = feature_snapshot(issue)
        for key, value in values.items():
            setattr(issue, key, value)
        issue.version += 1; issue.save()
        audit(request.user, 'issue_feature_updated', issue.pk, before=before, after=feature_snapshot(issue), version=issue.version)
        return Response(feature_data(issue))


class Teaser(StrictSerializer):
    date = serializers.DateField()
    name = serializers.CharField(max_length=200)
    place = serializers.CharField(max_length=200)
    category_id = serializers.UUIDField()
    source = serializers.CharField(max_length=500)


class TeaserInput(StrictSerializer):
    expected_version = serializers.IntegerField(min_value=1)
    entries = Teaser(many=True, max_length=30)

    def validate_entries(self, entries):
        keys = [(x['date'], x['name'].casefold(), x['place'].casefold()) for x in entries]
        if len(keys) != len(set(keys)):
            raise serializers.ValidationError('Duplicate upcoming event date, name and place.')
        return entries


def teaser_snapshot(issue):
    return [{'date': x.date.isoformat(), 'name': x.name, 'place': x.place, 'category_id': str(x.category_id), 'source': x.source} for x in issue.teasers.all()]


def teaser_data(issue):
    rows = list(issue.teasers.select_related('category').all())
    return {'version': issue.version, 'week_end': week_end(issue), 'entries': [
        {'date': x.date.isoformat(), 'name': x.name, 'place': x.place, 'category_id': str(x.category_id), 'source': x.source,
         'category_name': x.category.label, 'category_valid': x.category.is_active, 'position': x.position,
         'verification_status': 'UNVERIFIED_EDITORIAL_TEASER'} for x in rows],
        'warnings': [f'{x.name}: category is archived.' for x in rows if not x.category.is_active] + [f'{x.name}: date is not after the issue.' for x in rows if x.date <= week_end(issue)]}


class Teasers(APIView):
    permission_classes = [EditorialAccess]

    def get(self, request, pk):
        return Response(teaser_data(get_object_or_404(Issue, pk=pk)))

    @transaction.atomic
    def put(self, request, pk):
        data = TeaserInput(data=request.data); data.is_valid(raise_exception=True)
        directory_lock()
        issue = get_object_or_404(Issue.objects.select_for_update(), pk=pk)
        if issue.version != data.validated_data['expected_version']:
            return conflict()
        values = data.validated_data['entries']
        ids = {x['category_id'] for x in values}
        active = Category.objects.select_for_update().filter(pk__in=ids, is_active=True).in_bulk()
        for i, row in enumerate(values, 1):
            if row['date'] <= week_end(issue):
                raise serializers.ValidationError({'entries': f'Row {i}: date must be after the issue week.'})
            if row['category_id'] not in active:
                raise serializers.ValidationError({'entries': f'Row {i}: select an active category.'})
        before = teaser_snapshot(issue)
        issue.teasers.all().delete()
        ComingUp.objects.bulk_create([ComingUp(issue=issue, position=i, **row) for i, row in enumerate(values, 1)])
        issue.version += 1; issue.save()
        audit(request.user, 'issue_teasers_replaced', issue.pk, before=before, after=teaser_snapshot(issue), version=issue.version)
        return Response(teaser_data(issue))
