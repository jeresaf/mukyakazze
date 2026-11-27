"""Bounded schedule expansion and occurrence-local ticket tiers."""
from datetime import timedelta
from django.db import transaction
from django.db.models import Count
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import get_object_or_404
from accounts.serializers import StrictSerializer
from accounts.services import audit
from catalog.directory import directory_lock
from .models import Occurrence, Price, PRICE_TYPES, STATES, EventAttachment
from .api import (EventAccess, scope, locked, can_edit, conflict, current, output,
                  validate_values, OCC_FIELDS, KAMPALA, validate_attachments)

MAX_ADDITIONAL_DATES = 52

class RepeatInput(StrictSerializer):
    expected_version = serializers.IntegerField(min_value=1)
    dates = serializers.ListField(child=serializers.DateField(), min_length=1, max_length=MAX_ADDITIONAL_DATES)

    def validate_dates(self, dates):
        if len(set(dates)) != len(dates):
            raise serializers.ValidationError('Dates must be unique.')
        return sorted(dates)

class RepeatOccurrences(APIView):
    permission_classes = [EventAccess]

    @transaction.atomic
    def post(self, request, pk):
        data = RepeatInput(data=request.data)
        data.is_valid(raise_exception=True)
        directory_lock()
        row = locked(request.user, pk)
        # Event creator is also the provenance identity used by existing review rules.
        # Do not let another actor create a sibling under that identity.
        if row.event.created_by_id != request.user.pk or not can_edit(request.user, row) or not request.user.has_perm('events.add_occurrence'):
            return Response({'code': 'forbidden', 'message': 'Only the event creator can add repeat dates.'}, status=403)
        if row.version != data.validated_data['expected_version']:
            return conflict()
        if row.is_cancelled or row.status not in ('DRAFT', 'RETURNED'):
            return Response({'code': 'state_conflict', 'message': 'Repeat dates must be generated from an active draft or returned event.'}, status=409)
        original = current(row)
        validate_values(original, exclude=row.pk, complete=True)
        validate_attachments(row, row.poster_id)
        attachments = list(row.attachments.values("asset_id", "position"))
        origin = row.editorial_date
        dates = data.validated_data['dates']
        if any(d <= origin or d > origin + timedelta(days=366) for d in dates):
            raise serializers.ValidationError({'dates': 'Use later editorial dates within 366 days of the source.'})
        if row.event.occurrences.count() + len(dates) > 366:
            raise serializers.ValidationError({'dates': 'An event may have at most 366 occurrences.'})
        prices = list(row.prices.values('tier', 'kind', 'amount_ugx', 'note', 'ticket_url'))
        ids = []
        for day in dates:
            shift = day - origin
            values = dict(original, editorial_date=day,
                          starts_at=row.starts_at.astimezone(KAMPALA) + shift,
                          ends_at=row.ends_at.astimezone(KAMPALA) + shift if row.ends_at else None)
            validate_values(values, complete=True)
            child = Occurrence.objects.create(event=row.event, **{key: values[key] for key in OCC_FIELDS})
            Price.objects.bulk_create([Price(occurrence=child, **price) for price in prices])
            EventAttachment.objects.bulk_create([EventAttachment(occurrence=child, **asset) for asset in attachments])
            audit(request.user, 'event_occurrence_created', child.pk, source_occurrence_id=str(row.pk), event_id=str(row.event_id))
            ids.append(str(child.pk))
        row.version += 1
        row.save(update_fields=['version', 'updated_at'])
        audit(request.user, 'event_occurrences_generated', row.pk, occurrence_ids=ids, version=row.version)
        return Response({'created_ids': ids, 'source': output(row, request.user)}, status=201)

class TierInput(StrictSerializer):
    tier = serializers.CharField(max_length=80)
    kind = serializers.ChoiceField(choices=PRICE_TYPES)
    amount_ugx = serializers.IntegerField(min_value=0, max_value=999999999999, allow_null=True)
    note = serializers.CharField(max_length=250, allow_blank=True, required=False, default='')
    ticket_url = serializers.URLField(max_length=500, allow_blank=True, required=False, default='')

    def validate_tier(self, name):
        if name.casefold() == 'general':
            raise serializers.ValidationError('General price is edited in the event form.')
        return name

    def validate(self, attrs):
        kind, amount = attrs['kind'], attrs['amount_ugx']
        if not ((kind == 'FREE' and amount == 0) or (kind == 'PAID' and amount is not None and amount > 0) or (kind in ('UNKNOWN', 'CONDITIONAL_FREE') and amount is None)):
            raise serializers.ValidationError({'amount_ugx': 'Free requires zero; paid requires a positive amount; unknown/conditional requires no amount.'})
        if kind == 'CONDITIONAL_FREE' and not attrs['note']:
            raise serializers.ValidationError({'note': 'Record the conditions.'})
        if attrs['ticket_url'] and not attrs['ticket_url'].lower().startswith(('http://', 'https://')):
            raise serializers.ValidationError({'ticket_url': 'Use HTTP or HTTPS.'})
        return attrs

class TierSetInput(StrictSerializer):
    expected_version = serializers.IntegerField(min_value=1)
    tiers = TierInput(many=True, max_length=12)

    def validate_tiers(self, tiers):
        names = [tier['tier'].casefold() for tier in tiers]
        if len(names) != len(set(names)):
            raise serializers.ValidationError('Ticket tier names must be unique.')
        return tiers

class TicketTiers(APIView):
    permission_classes = [EventAccess]

    def get(self, request, pk):
        row = get_object_or_404(scope(request.user), pk=pk)
        return Response({'version': row.version, 'tiers': list(row.prices.exclude(tier='General').order_by('tier').values('tier','kind','amount_ugx','note','ticket_url'))})

    @transaction.atomic
    def put(self, request, pk):
        data = TierSetInput(data=request.data)
        data.is_valid(raise_exception=True)
        directory_lock()
        row = locked(request.user, pk)
        if not can_edit(request.user, row):
            return Response({'code': 'forbidden'}, status=403)
        if row.version != data.validated_data['expected_version']:
            return conflict()
        if row.is_cancelled or row.status not in ('DRAFT', 'RETURNED'):
            return Response({'code': 'state_conflict', 'message': 'Only active drafts or returned events may be edited.'}, status=409)
        before = list(row.prices.exclude(tier='General').order_by('tier').values('tier','kind','amount_ugx','note','ticket_url'))
        tiers = data.validated_data['tiers']
        row.prices.exclude(tier='General').delete()
        Price.objects.bulk_create([Price(occurrence=row, **tier) for tier in tiers])
        row.version += 1
        row.status = 'DRAFT'
        row.save(update_fields=['version','status','updated_at'])
        audit(request.user, 'event_ticket_tiers_updated', row.pk, before=before, after=tiers, version=row.version)
        return Response(output(row, request.user))

class EventStatistics(APIView):
    permission_classes = [EventAccess]

    def get(self, request):
        # Scope first: never reveal another collector's private drafts through counts.
        qs = scope(request.user)
        counts = dict(qs.filter(is_cancelled=False).order_by().values('status').annotate(n=Count('pk')).values_list('status','n'))
        return Response({'active': sum(counts.values()), 'cancelled': qs.filter(is_cancelled=True).count(),
                         'by_status': {state: counts.get(state, 0) for state, _ in STATES}})
