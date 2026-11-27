import uuid
from django.conf import settings
from django.db import models
from django.db.models import Q

STATES = [(s, s.replace('_', ' ').title()) for s in ('DRAFT','SUBMITTED','UNDER_REVIEW','RETURNED','VERIFIED','REJECTED')]
PRICE_TYPES = [(s, s.replace('_', ' ').title()) for s in ('UNKNOWN','FREE','PAID','CONDITIONAL_FREE')]

class Event(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    category = models.ForeignKey('catalog.Category', null=True, blank=True, on_delete=models.PROTECT)
    promoter = models.ForeignKey('catalog.Promoter', null=True, blank=True, on_delete=models.PROTECT)
    description = models.TextField(blank=True, default='')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class Occurrence(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.PROTECT, related_name='occurrences')
    venue = models.ForeignKey('catalog.Venue', null=True, blank=True, on_delete=models.PROTECT)
    poster = models.ForeignKey('catalog.MediaAsset', null=True, blank=True, on_delete=models.PROTECT)
    editorial_date = models.DateField(null=True, blank=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    source = models.CharField(max_length=500, blank=True, default='')
    notes = models.TextField(blank=True, default='')
    status = models.CharField(max_length=16, choices=STATES, default='DRAFT', db_index=True)
    is_cancelled = models.BooleanField(default=False)
    version = models.PositiveIntegerField(default=1)
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at','id']
        permissions = [('review_occurrence','Review entertainment submissions'), ('manage_all_occurrences','Manage all event records')]
        constraints = [
            models.CheckConstraint(condition=Q(status__in=[s for s,_ in STATES]),name='events_occurrence_status_valid'),
            models.CheckConstraint(condition=Q(version__gte=1),name='events_occurrence_version_positive'),
            models.CheckConstraint(condition=Q(ends_at__isnull=True) | (Q(starts_at__isnull=False) & Q(ends_at__gt=models.F('starts_at'))),name='events_occurrence_end_after_start'),
            models.CheckConstraint(condition=Q(status='DRAFT') | (Q(venue__isnull=False) & Q(starts_at__isnull=False) & Q(editorial_date__isnull=False) & Q(submitted_by__isnull=False)),name='events_occurrence_submitted_complete'),
        ]

class Price(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    occurrence = models.ForeignKey(Occurrence, on_delete=models.PROTECT, related_name='prices')
    tier = models.CharField(max_length=80, default='General')
    kind = models.CharField(max_length=16, choices=PRICE_TYPES, default='UNKNOWN')
    amount_ugx = models.PositiveBigIntegerField(null=True, blank=True)
    note = models.CharField(max_length=250, blank=True, default='')
    ticket_url = models.URLField(max_length=500, blank=True, default='')

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['occurrence','tier'],name='events_price_tier_unique'),
            models.CheckConstraint(condition=(Q(kind='FREE',amount_ugx=0,amount_ugx__isnull=False) | Q(kind='PAID',amount_ugx__gt=0,amount_ugx__isnull=False) | Q(kind__in=['UNKNOWN','CONDITIONAL_FREE'],amount_ugx__isnull=True)),name='events_price_amount_valid'),
        ]

class Verification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    occurrence = models.ForeignKey(Occurrence, on_delete=models.PROTECT, related_name='decisions')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    action = models.CharField(max_length=16)
    reason = models.TextField()
    method = models.CharField(max_length=100, blank=True, default='')
    evidence = models.TextField(blank=True, default='')
    version = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at','id']
        constraints = [models.UniqueConstraint(fields=['occurrence','version'],name='events_decision_version_unique')]
