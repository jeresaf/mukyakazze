import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.db.models import Q

STATES = [(s, s.replace('_', ' ').title()) for s in ('DRAFT','SUBMITTED','UNDER_REVIEW','RETURNED','VERIFIED','REJECTED')]
PRICE_TYPES = [(s, s.replace('_', ' ').title()) for s in ('UNKNOWN','FREE','PAID','CONDITIONAL_FREE')]

class Migration(migrations.Migration):
    initial = True
    dependencies = [('catalog','0005_sponsors_media'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name='Event', fields=[
            ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
            ('title', models.CharField(max_length=200)),
            ('category', models.ForeignKey('catalog.category', null=True, blank=True, on_delete=django.db.models.deletion.PROTECT)),
            ('promoter', models.ForeignKey('catalog.promoter', null=True, blank=True, on_delete=django.db.models.deletion.PROTECT)),
            ('description', models.TextField(blank=True, default='')),
            ('created_by', models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.PROTECT, related_name='+')),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('updated_at', models.DateTimeField(auto_now=True)),
        ], options={}),
        migrations.CreateModel(name='Occurrence', fields=[
            ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
            ('event', models.ForeignKey('events.event', on_delete=django.db.models.deletion.PROTECT, related_name='occurrences')),
            ('venue', models.ForeignKey('catalog.venue', null=True, blank=True, on_delete=django.db.models.deletion.PROTECT)),
            ('poster', models.ForeignKey('catalog.mediaasset', null=True, blank=True, on_delete=django.db.models.deletion.PROTECT)),
            ('editorial_date', models.DateField(null=True, blank=True)),
            ('starts_at', models.DateTimeField(null=True, blank=True)),
            ('ends_at', models.DateTimeField(null=True, blank=True)),
            ('source', models.CharField(max_length=500, blank=True, default='')),
            ('notes', models.TextField(blank=True, default='')),
            ('status', models.CharField(max_length=16, choices=STATES, default='DRAFT', db_index=True)),
            ('is_cancelled', models.BooleanField(default=False)),
            ('version', models.PositiveIntegerField(default=1)),
            ('submitted_by', models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=django.db.models.deletion.PROTECT, related_name='+')),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('updated_at', models.DateTimeField(auto_now=True)),
        ], options={'ordering': ['-created_at', 'id'], 'permissions': [('review_occurrence', 'Review entertainment submissions'), ('manage_all_occurrences', 'Manage all event records')], 'constraints': [models.CheckConstraint(condition=Q(status__in=[s for s, _ in STATES]), name='events_occurrence_status_valid'), models.CheckConstraint(condition=Q(version__gte=1), name='events_occurrence_version_positive'), models.CheckConstraint(condition=Q(ends_at__isnull=True) | Q(starts_at__isnull=False) & Q(ends_at__gt=models.F('starts_at')), name='events_occurrence_end_after_start'), models.CheckConstraint(condition=Q(status='DRAFT') | Q(venue__isnull=False) & Q(starts_at__isnull=False) & Q(editorial_date__isnull=False) & Q(submitted_by__isnull=False), name='events_occurrence_submitted_complete')]}),
        migrations.CreateModel(name='Price', fields=[
            ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
            ('occurrence', models.ForeignKey('events.occurrence', on_delete=django.db.models.deletion.PROTECT, related_name='prices')),
            ('tier', models.CharField(max_length=80, default='General')),
            ('kind', models.CharField(max_length=16, choices=PRICE_TYPES, default='UNKNOWN')),
            ('amount_ugx', models.PositiveBigIntegerField(null=True, blank=True)),
            ('note', models.CharField(max_length=250, blank=True, default='')),
            ('ticket_url', models.URLField(max_length=500, blank=True, default='')),
        ], options={'constraints': [models.UniqueConstraint(fields=['occurrence', 'tier'], name='events_price_tier_unique'), models.CheckConstraint(condition=Q(kind='FREE', amount_ugx=0, amount_ugx__isnull=False) | Q(kind='PAID', amount_ugx__gt=0, amount_ugx__isnull=False) | Q(kind__in=['UNKNOWN', 'CONDITIONAL_FREE'], amount_ugx__isnull=True), name='events_price_amount_valid')]}),
        migrations.CreateModel(name='Verification', fields=[
            ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
            ('occurrence', models.ForeignKey('events.occurrence', on_delete=django.db.models.deletion.PROTECT, related_name='decisions')),
            ('actor', models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.PROTECT, related_name='+')),
            ('action', models.CharField(max_length=16)),
            ('reason', models.TextField()),
            ('method', models.CharField(max_length=100, blank=True, default='')),
            ('evidence', models.TextField(blank=True, default='')),
            ('version', models.PositiveIntegerField()),
            ('created_at', models.DateTimeField(auto_now_add=True)),
        ], options={'ordering': ['-created_at', 'id'], 'constraints': [models.UniqueConstraint(fields=['occurrence', 'version'], name='events_decision_version_unique')]}),
    ]
