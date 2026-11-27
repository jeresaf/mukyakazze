import uuid
from django.conf import settings
from django.db import models
from django.db.models import Q


class Issue(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    number = models.PositiveIntegerField(unique=True)
    week_start = models.DateField(unique=True)
    grid_day = models.DateField()
    picks_title = models.CharField(max_length=120, default="BUGY'S PICKS")
    picks_byline = models.CharField(max_length=150, blank=True, default='')
    picks_intro = models.TextField(blank=True, default='')
    version = models.PositiveIntegerField(default=1)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-week_start', 'id']
        constraints = [models.CheckConstraint(condition=Q(number__gte=1), name='editorial_issue_number_positive'), models.CheckConstraint(condition=Q(version__gte=1), name='editorial_issue_version_positive')]


class IssueEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    issue = models.ForeignKey(Issue, on_delete=models.PROTECT, related_name='entries')
    occurrence = models.ForeignKey('events.Occurrence', on_delete=models.PROTECT)
    occurrence_version = models.PositiveIntegerField()
    rank = models.PositiveSmallIntegerField(null=True, blank=True)
    why_go = models.CharField(max_length=500, blank=True, default='')
    curator_playing = models.BooleanField(default=False)
    paid_feature = models.BooleanField(default=False)

    class Meta:
        ordering = ['rank', 'id']
        constraints = [
            models.UniqueConstraint(fields=['issue','occurrence'], name='editorial_issue_occurrence_unique'),
            models.UniqueConstraint(fields=['issue','rank'], name='editorial_issue_rank_unique'),
            models.CheckConstraint(condition=Q(rank__isnull=True) | Q(rank__gte=1,rank__lte=7), name='editorial_issue_rank_range'),
        ]
