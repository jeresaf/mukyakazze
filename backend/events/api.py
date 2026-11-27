from datetime import timedelta, time
from zoneinfo import ZoneInfo
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import generics, permissions, serializers
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView
from accounts.serializers import StrictSerializer
from accounts.services import audit
from accounts.models import AuditEvent
from catalog.directory import directory_lock
from catalog.models import Category, Venue, Promoter, MediaAsset
from .models import Event, Occurrence, Price, Verification, STATES, PRICE_TYPES

KAMPALA = ZoneInfo('Africa/Kampala')
EVENT_FIELDS = ('title','category_id','promoter_id','description')
OCC_FIELDS = ('venue_id','poster_id','editorial_date','starts_at','ends_at','source','notes')
PRICE_FIELDS = {'price_type':'kind','amount_ugx':'amount_ugx','price_note':'note','ticket_url':'ticket_url'}
REFERENCES = {'category_id':Category,'promoter_id':Promoter,'venue_id':Venue,'poster_id':MediaAsset}

class EventInput(StrictSerializer):
    title = serializers.CharField(max_length=200, required=False)
    category_id = serializers.UUIDField(required=False, allow_null=True)
    promoter_id = serializers.UUIDField(required=False, allow_null=True)
    description = serializers.CharField(max_length=5000, required=False, allow_blank=True)
    venue_id = serializers.UUIDField(required=False, allow_null=True)
    poster_id = serializers.UUIDField(required=False, allow_null=True)
    editorial_date = serializers.DateField(required=False, allow_null=True)
    starts_at = serializers.DateTimeField(required=False, allow_null=True, default_timezone=KAMPALA)
    ends_at = serializers.DateTimeField(required=False, allow_null=True, default_timezone=KAMPALA)
    source = serializers.CharField(max_length=500, required=False, allow_blank=True)
    notes = serializers.CharField(max_length=5000, required=False, allow_blank=True)
    price_type = serializers.ChoiceField(choices=PRICE_TYPES, required=False)
    amount_ugx = serializers.IntegerField(min_value=0, max_value=999999999999, required=False, allow_null=True)
    price_note = serializers.CharField(max_length=250, required=False, allow_blank=True)
    ticket_url = serializers.URLField(max_length=500, required=False, allow_blank=True)

    def validate_ticket_url(self, value):
        if value and not value.lower().startswith(('http://','https://')):
            raise serializers.ValidationError('Use an HTTP or HTTPS URL.')
        return value

class CreateInput(EventInput):
    title = serializers.CharField(max_length=200)

class EditInput(EventInput):
    expected_version = serializers.IntegerField(min_value=1)
    def validate(self, attrs):
        if len(attrs) == 1:
            raise serializers.ValidationError('No changes supplied.')
        return attrs

class ActionInput(StrictSerializer):
    expected_version = serializers.IntegerField(min_value=1)
    action = serializers.ChoiceField(choices=['submit','review','verify','return','reject','reopen','cancel','restore'])
    reason = serializers.CharField(max_length=2000, required=False, allow_blank=True)
    method = serializers.CharField(max_length=100, required=False, allow_blank=True)
    evidence = serializers.CharField(max_length=3000, required=False, allow_blank=True)

class EventAccess(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.has_perm('events.view_occurrence')

def scope(user):
    qs = Occurrence.objects.select_related('event','event__category','event__promoter','venue','venue__area','venue__area__city','poster').defer('poster__content')
    if not user.has_perm('events.manage_all_occurrences'):
        if user.has_perm('events.review_occurrence'):
            qs = qs.filter(Q(event__created_by=user) | Q(assigned_collector=user) | ~Q(status='DRAFT'))
        else:
            qs = qs.filter(Q(event__created_by=user) | Q(assigned_collector=user))
    return qs

def can_edit(user, row):
    return user.has_perm('events.change_occurrence') and (user.has_perm('events.manage_all_occurrences') or user.pk in (row.event.created_by_id, row.assigned_collector_id))

def is_contributor(user, row):
    # Conservative series-wide exclusion: shared metadata and repeated content may
    # have been supplied by editors of any sibling. Historical submissions count.
    if user.pk in (row.event.created_by_id, row.submitted_by_id, row.assigned_collector_id):
        return True
    return AuditEvent.objects.filter(actor=user, target_id__in=Occurrence.objects.filter(event_id=row.event_id).values('pk'), action__in=['event_updated','event_submit','event_ticket_tiers_updated','event_attachments_updated']).exists()

def can_review(user, row):
    return (user.has_perm('events.review_occurrence') and not is_contributor(user, row)
            and row.assigned_reviewer_id in (None, user.pk))

def validate_attachments(row, poster_id):
    ids = list(row.attachments.values_list('asset_id', flat=True))
    if poster_id in ids:
        raise serializers.ValidationError({'poster_id':'The main poster cannot also be an additional image.'})
    if len(list(MediaAsset.objects.select_for_update().filter(pk__in=ids, is_active=True, kind__in=['poster','photo']).values_list('pk', flat=True))) != len(ids):
        raise serializers.ValidationError({'attachments':'Additional images must be active event posters or photos.'})

def output(row, user):
    event = row.event
    price = row.prices.get(tier='General')
    return {'id':str(row.pk),'event_id':str(event.pk),'title':event.title,'category_id':event.category_id,'category_name':event.category.label if event.category else '',
            'promoter_id':event.promoter_id,'promoter_name':event.promoter.name if event.promoter else '', 'description':event.description,
            'venue_id':row.venue_id,'venue_name':row.venue.name if row.venue else '', 'area_name':row.venue.area.name if row.venue else '',
            'poster_id':row.poster_id,'poster_name':row.poster.name if row.poster else '',
            'editorial_date':row.editorial_date,'starts_at':row.starts_at.astimezone(KAMPALA).isoformat() if row.starts_at else None,'ends_at':row.ends_at.astimezone(KAMPALA).isoformat() if row.ends_at else None,
            'source':row.source,'notes':row.notes,'price_type':price.kind,'amount_ugx':price.amount_ugx,'price_note':price.note,'ticket_url':price.ticket_url,
            'can_repeat':user.pk == event.created_by_id and user.has_perm('events.add_occurrence') and can_edit(user,row),
            'shared_event':event.occurrences.count() > 1, 'status':row.status,'is_cancelled':row.is_cancelled,'version':row.version,'can_edit':can_edit(user,row),
            'can_review':can_review(user,row), 'created_at':row.created_at,'updated_at':row.updated_at}

def validate_refs(values):
    for field, model in REFERENCES.items():
        pk = values.get(field)
        if pk is None:
            continue
        ref = model.objects.select_for_update().filter(pk=pk,is_active=True).first()
        if ref is None:
            raise serializers.ValidationError({field:'Select an active record.'})
        if field == 'venue_id' and not (ref.area.is_active and ref.area.city.is_active and ref.area.city.country.is_active):
            raise serializers.ValidationError({field:'Venue location must be active.'})
        if field == 'poster_id' and ref.kind != 'poster':
            raise serializers.ValidationError({field:'Select an event poster.'})

def validate_values(values, *, exclude=None, complete=False):
    validate_refs(values)
    start,end,day = (values.get(k) for k in ('starts_at','ends_at','editorial_date'))
    if end and (not start or end <= start):
        raise serializers.ValidationError({'ends_at':'End must be after the actual start, including date.'})
    if start and day:
        local = start.astimezone(KAMPALA)
        allowed = {local.date()}
        if local.time() < time(6):
            allowed.add(local.date()-timedelta(days=1))
        if day not in allowed:
            raise serializers.ValidationError({'editorial_date':'Use actual date or previous night for starts before 06:00 Kampala time.'})
    kind,amount = values.get('price_type','UNKNOWN'),values.get('amount_ugx')
    if not ((kind=='FREE' and amount==0) or (kind=='PAID' and amount is not None and amount>0) or (kind in ('UNKNOWN','CONDITIONAL_FREE') and amount is None)):
        raise serializers.ValidationError({'amount_ugx':'Free requires 0; paid requires a positive amount; unknown/conditional requires blank amount.'})
    if complete:
        missing = [k for k in ('title','category_id','venue_id','editorial_date','starts_at','source') if not values.get(k)]
        if kind=='CONDITIONAL_FREE' and not values.get('price_note'):
            missing.append('price_note')
        if missing:
            raise serializers.ValidationError({k:'Required for submission or review.' for k in missing})
    if start and values.get('venue_id') and values.get('title'):
        same = Occurrence.objects.filter(event__title__iexact=values['title'],venue_id=values['venue_id'],starts_at=start)
        if exclude:
            same = same.exclude(pk=exclude)
        if same.exists():
            raise serializers.ValidationError({'title':'Possible duplicate: same title, venue and actual start. Review the existing record.'})

def current(row):
    price = row.prices.get(tier='General')
    return {**{k:getattr(row.event,k) for k in EVENT_FIELDS}, **{k:getattr(row,k) for k in OCC_FIELDS}, **{k:getattr(price,v) for k,v in PRICE_FIELDS.items()}}

def locked(user, pk):
    # Lock only the occurrence first; joined nullable references cannot be FOR UPDATE locked.
    permitted = scope(user).filter(pk=pk).values('pk')
    return get_object_or_404(Occurrence.objects.select_for_update().filter(pk__in=permitted),pk=pk)

def stale(row, expected):
    return row.version != expected

def conflict():
    return Response({'code':'stale_version','message':'Refresh the event before editing.'},status=409)

class Events(generics.GenericAPIView):
    permission_classes = [EventAccess]
    def get(self, request):
        qs = scope(request.user)
        status = request.query_params.get('status','all')
        if status not in ['all',*[s for s,_ in STATES]]:
            raise serializers.ValidationError({'status':'Invalid status.'})
        if status != 'all':
            qs = qs.filter(status=status)
        term = request.query_params.get('search','').strip()[:200]
        if term:
            qs = qs.filter(Q(event__title__icontains=term)|Q(venue__name__icontains=term))
        for key,lookup in [('from','editorial_date__gte'),('to','editorial_date__lte')]:
            if key in request.query_params:
                qs=qs.filter(**{lookup:serializers.DateField().run_validation(request.query_params[key])})
        for key, lookup in [('category','event__category_id'),('venue','venue_id'),('area','venue__area_id'),('promoter','event__promoter_id'),('event','event_id')]:
            if key in request.query_params:
                qs=qs.filter(**{lookup:serializers.UUIDField().run_validation(request.query_params[key])})
        if 'assigned' in request.query_params:
            assignment = request.query_params['assigned']
            if assignment == 'collection': qs = qs.filter(assigned_collector=request.user)
            elif assignment == 'review': qs = qs.filter(assigned_reviewer=request.user)
            elif assignment == 'unassigned_review': qs = qs.filter(assigned_reviewer__isnull=True)
            else: raise serializers.ValidationError({'assigned':'Invalid assignment filter.'})
        if 'cancelled' in request.query_params:
            value=request.query_params['cancelled']
            if value not in ('true','false'):
                raise serializers.ValidationError({'cancelled':'Use true or false.'})
            qs=qs.filter(is_cancelled=value=='true')
        page = self.paginate_queryset(qs)
        return self.get_paginated_response([output(row,request.user) for row in page])

    @transaction.atomic
    def post(self, request):
        if not request.user.has_perm('events.add_occurrence'):
            return Response({'code':'forbidden'},status=403)
        data=CreateInput(data=request.data); data.is_valid(raise_exception=True)
        values=dict(data.validated_data)
        directory_lock()
        validate_values(values)
        event=Event.objects.create(created_by=request.user,**{k:values[k] for k in EVENT_FIELDS if k in values})
        row=Occurrence.objects.create(event=event,**{k:values[k] for k in OCC_FIELDS if k in values})
        Price.objects.create(occurrence=row,**{v:values[k] for k,v in PRICE_FIELDS.items() if k in values})
        audit(request.user,'event_created',row.pk,event_id=str(event.pk),version=row.version)
        return Response(output(row,request.user),status=201)

class EventDetail(APIView):
    permission_classes=[EventAccess]
    def get(self,request,pk):
        row=get_object_or_404(scope(request.user),pk=pk)
        return Response(output(row,request.user))
    @transaction.atomic
    def patch(self,request,pk):
        data=EditInput(data=request.data);data.is_valid(raise_exception=True)
        values=dict(data.validated_data); expected=values.pop('expected_version')
        directory_lock(); row=locked(request.user,pk)
        if not can_edit(request.user,row):
            return Response({'code':'forbidden'},status=403)
        if stale(row,expected):return conflict()
        if row.status not in ('DRAFT','RETURNED') or row.is_cancelled:
            return Response({'code':'state_conflict','message':'Only active drafts or returned events can be edited. Reopen first.'},status=409)
        merged={**current(row),**values}; validate_values(merged,exclude=row.pk)
        if merged.get("poster_id") in row.attachments.values_list("asset_id", flat=True):
            raise serializers.ValidationError({"poster_id":"The main poster cannot also be an additional image."})
        if row.event.occurrences.count()!=1 and any(k in values and values[k] != getattr(row.event,k) for k in EVENT_FIELDS):
            raise serializers.ValidationError({'event':'Shared event metadata requires a separate workflow.'})
        event=row.event; price=row.prices.get(tier='General')
        for key,value in values.items():
            if key in EVENT_FIELDS:setattr(event,key,value)
            elif key in OCC_FIELDS:setattr(row,key,value)
            else:setattr(price,PRICE_FIELDS[key],value)
        event.save();price.save();row.version+=1
        # A returned event may be incomplete while edited; it becomes a draft.
        row.status='DRAFT';row.save()
        audit(request.user,'event_updated',row.pk,fields=sorted(values),version=row.version)
        return Response(output(row,request.user))

class EventAction(APIView):
    permission_classes=[EventAccess]
    @transaction.atomic
    def post(self,request,pk):
        data=ActionInput(data=request.data);data.is_valid(raise_exception=True);v=data.validated_data
        directory_lock(); row=locked(request.user,pk)
        action=v['action']; reason=v.get('reason',''); method=v.get('method',''); evidence=v.get('evidence','')
        reviewer=request.user.has_perm('events.review_occurrence')
        manage=request.user.has_perm('events.manage_all_occurrences')
        if action=='submit':allowed=can_edit(request.user,row)
        elif action=='reopen':allowed=manage
        elif action in ('cancel','restore'):allowed=reviewer
        else:allowed=can_review(request.user,row)
        if not allowed:return Response({'code':'forbidden','message':'This action is not permitted. Self-review is not allowed.'},status=403)
        if stale(row,v['expected_version']):return conflict()
        transitions={'submit':(('DRAFT','RETURNED'),'SUBMITTED'),'review':(('SUBMITTED',),'UNDER_REVIEW'),'verify':(('UNDER_REVIEW',),'VERIFIED'),'return':(('SUBMITTED','UNDER_REVIEW'),'RETURNED'),'reject':(('UNDER_REVIEW',),'REJECTED'),'reopen':(('VERIFIED','REJECTED','SUBMITTED','UNDER_REVIEW'),'DRAFT')}
        if action!='submit' and not reason:
            raise serializers.ValidationError({'reason':'Record a reason for this action.'})
        if action=='verify' and (not method or not evidence):
            raise serializers.ValidationError({'evidence':'Verification requires a method and evidence.'})
        if action in ('cancel','restore'):
            if row.is_cancelled != (action=='restore'):
                return Response({'code':'state_conflict','message':'Cancellation state already set.'},status=409)
            row.is_cancelled=action=='cancel'
            if action=='restore':row.status='DRAFT'
        else:
            allowed_states,new=transitions[action]
            if row.is_cancelled or row.status not in allowed_states:
                return Response({'code':'state_conflict','message':'Action not allowed in the current state.'},status=409)
            if action in ('submit','verify'):
                validate_values(current(row),exclude=row.pk,complete=True)
                validate_attachments(row, row.poster_id)
            if action=='submit':row.submitted_by=request.user
            row.status=new
        row.version+=1;row.save()
        Verification.objects.create(occurrence=row,actor=request.user,action=action,reason=reason,method=method,evidence=evidence,version=row.version)
        audit(request.user,'event_'+action,row.pk,version=row.version,status=row.status,is_cancelled=row.is_cancelled)
        return Response(output(row,request.user))

class EventHistory(generics.GenericAPIView):
    permission_classes=[EventAccess]
    def get(self,request,pk):
        row=get_object_or_404(scope(request.user),pk=pk)
        page=self.paginate_queryset(row.decisions.all())
        return self.get_paginated_response([{'id':x.pk,'actor_id':x.actor_id,'action':x.action,'reason':x.reason,'method':x.method,'evidence':x.evidence,'version':x.version,'created_at':x.created_at} for x in page])
