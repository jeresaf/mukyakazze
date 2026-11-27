from datetime import timedelta
from django.db import IntegrityError, transaction
from django.db.models import Q
from rest_framework import generics, permissions, serializers
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView
from accounts.serializers import StrictSerializer
from accounts.services import audit
from catalog.directory import directory_lock
from events.models import Occurrence
from .models import Issue, IssueEvent


class EditorialAccess(permissions.BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return user.is_authenticated and user.has_perm('editorial.view_issue') and (request.method in permissions.SAFE_METHODS or user.has_perm('editorial.change_issue'))


class IssueCreate(StrictSerializer):
    number = serializers.IntegerField(min_value=1,max_value=2147483647)
    week_start = serializers.DateField()
    grid_day = serializers.DateField(required=False)

    def validate(self, data):
        start = data['week_start']
        if start.weekday() != 3 or start.year > 9998:
            raise serializers.ValidationError({'week_start':'Choose a Thursday before year 9999.'})
        day = data.setdefault('grid_day', start + timedelta(days=1))
        if not start <= day <= start + timedelta(days=6):
            raise serializers.ValidationError({'grid_day':'Grid day must be inside the issue week.'})
        return data


class IssueEdit(StrictSerializer):
    expected_version = serializers.IntegerField(min_value=1)
    grid_day = serializers.DateField(required=False)
    picks_title = serializers.CharField(max_length=120,required=False)
    picks_byline = serializers.CharField(max_length=150,required=False,allow_blank=True)
    picks_intro = serializers.CharField(max_length=2000,required=False,allow_blank=True)

    def validate(self, data):
        if len(data) == 1:
            raise serializers.ValidationError('No changes supplied.')
        return data


class Entry(StrictSerializer):
    occurrence_id = serializers.UUIDField()
    occurrence_version = serializers.IntegerField(min_value=1)
    rank = serializers.IntegerField(min_value=1,max_value=7,allow_null=True,required=False,default=None)
    why_go = serializers.CharField(max_length=500,allow_blank=True,required=False,default='')
    curator_playing = serializers.BooleanField(required=False,default=False)
    paid_feature = serializers.BooleanField(required=False,default=False)

    def validate(self, data):
        if data['rank'] is not None and not data['why_go']:
            raise serializers.ValidationError({'why_go':'Ranked picks require a recommendation.'})
        if data['rank'] is None and (data['why_go'] or data['curator_playing']):
            raise serializers.ValidationError({'rank':'Pick commentary and curator disclosure require a rank.'})
        return data


class Roster(StrictSerializer):
    expected_version = serializers.IntegerField(min_value=1)
    entries = Entry(many=True,max_length=500)

    def validate_entries(self, entries):
        ids = [x['occurrence_id'] for x in entries]
        ranks = [x['rank'] for x in entries if x['rank'] is not None]
        if len(ids) != len(set(ids)) or len(ranks) != len(set(ranks)):
            raise serializers.ValidationError('Occurrences and pick ranks must be unique.')
        return entries


def week_end(issue):
    return issue.week_start + timedelta(days=6)


def eligible(issue, row):
    return (row.status == 'VERIFIED' and not row.is_cancelled and row.editorial_date is not None and issue.week_start <= row.editorial_date <= week_end(issue))


def candidate(row):
    return {'occurrence_id':str(row.pk),'occurrence_version':row.version,'title':row.event.title,'category':row.event.category.label if row.event.category else '', 'venue':row.venue.name if row.venue else '', 'editorial_date':row.editorial_date,'starts_at':row.starts_at}


def entries(issue):
    return issue.entries.select_related('occurrence__event__category','occurrence__venue').order_by('rank','occurrence_id')


def entry_data(issue, item):
    row = item.occurrence
    return {**candidate(row),'occurrence_version':item.occurrence_version,'current_version':row.version,'eligible':eligible(issue,row),'stale':item.occurrence_version != row.version,'rank':item.rank,'why_go':item.why_go,'curator_playing':item.curator_playing,'paid_feature':item.paid_feature}


def output(issue, detail=False):
    result = {'id':str(issue.pk),'number':issue.number,'week_start':issue.week_start,'week_end':week_end(issue),'grid_day':issue.grid_day,'version':issue.version,'picks_title':issue.picks_title,'picks_byline':issue.picks_byline,'picks_intro':issue.picks_intro,'status':'DRAFT'}
    if detail:
        result['entries'] = [entry_data(issue,x) for x in entries(issue)]
    return result


def conflict():
    return Response({'code':'stale_version','message':'Refresh the issue or changed event before saving.'},status=409)


class Issues(generics.GenericAPIView):
    permission_classes = [EditorialAccess]

    def get(self, request):
        return self.get_paginated_response([output(x) for x in self.paginate_queryset(Issue.objects.all())])

    def post(self, request):
        data = IssueCreate(data=request.data); data.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                issue = Issue.objects.create(created_by=request.user,**data.validated_data)
                audit(request.user,'issue_created',issue.pk,number=issue.number,week_start=issue.week_start.isoformat())
        except IntegrityError:
            raise serializers.ValidationError({'issue':'Issue number or week already exists.'})
        return Response(output(issue,True),status=201)


class IssueDetail(APIView):
    permission_classes = [EditorialAccess]

    def get(self, request, pk):
        return Response(output(get_object_or_404(Issue,pk=pk),True))

    @transaction.atomic
    def patch(self, request, pk):
        data=IssueEdit(data=request.data); data.is_valid(raise_exception=True)
        issue=get_object_or_404(Issue.objects.select_for_update(),pk=pk)
        values=dict(data.validated_data)
        if issue.version != values.pop('expected_version'):
            return conflict()
        day=values.get('grid_day',issue.grid_day)
        if not issue.week_start <= day <= week_end(issue):
            raise serializers.ValidationError({'grid_day':'Grid day must be inside the issue week.'})
        for key,value in values.items(): setattr(issue,key,value)
        issue.version += 1; issue.save()
        audit(request.user,'issue_updated',issue.pk,fields=sorted(values),version=issue.version)
        return Response(output(issue,True))


class Candidates(generics.GenericAPIView):
    permission_classes=[EditorialAccess]

    def get(self,request,pk):
        issue=get_object_or_404(Issue,pk=pk)
        qs=Occurrence.objects.filter(status='VERIFIED',is_cancelled=False,editorial_date__range=(issue.week_start,week_end(issue))).select_related('event__category','venue').order_by('editorial_date','starts_at','pk')
        term=request.query_params.get('search','').strip()[:200]
        if term: qs=qs.filter(Q(event__title__icontains=term)|Q(venue__name__icontains=term))
        return self.get_paginated_response([candidate(row) for row in self.paginate_queryset(qs)])


class IssueRoster(APIView):
    permission_classes=[EditorialAccess]

    @transaction.atomic
    def put(self,request,pk):
        data=Roster(data=request.data); data.is_valid(raise_exception=True)
        # Event/catalog writers acquire this same transaction lock before mutations.
        directory_lock()
        issue=get_object_or_404(Issue.objects.select_for_update(),pk=pk)
        if issue.version != data.validated_data['expected_version']: return conflict()
        values=data.validated_data['entries']
        rows=Occurrence.objects.in_bulk([x['occurrence_id'] for x in values])
        for x in values:
            row=rows.get(x['occurrence_id'])
            if row is None or not eligible(issue,row):
                raise serializers.ValidationError({'entries':'Every selected occurrence must be verified, noncancelled and in this issue week.'})
            if x['occurrence_version'] != row.version: return conflict()
        # Draft roster replacement is atomic, with prior and new editorial selections retained in audit.
        def audit_roster(items):
            return [{k:str(v) if k=='occurrence_id' else v for k,v in item.items()} for item in items]
        fields=('occurrence_id','occurrence_version','rank','why_go','curator_playing','paid_feature')
        before=audit_roster(issue.entries.values(*fields))
        issue.entries.all().delete()
        IssueEvent.objects.bulk_create([IssueEvent(issue=issue,**x) for x in values])
        issue.version+=1; issue.save()
        audit(request.user,'issue_roster_replaced',issue.pk,before=before,after=audit_roster(values),version=issue.version)
        return Response(output(issue,True))
