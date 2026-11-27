"""Occurrence-local staff assignments and reusable additional event images."""
from django.db import transaction
from django.db.models import Q
from rest_framework import generics, serializers
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.generics import get_object_or_404
from accounts.models import User
from accounts.serializers import StrictSerializer
from accounts.services import audit
from catalog.directory import directory_lock
from catalog.models import MediaAsset
from .models import EventAttachment
from .api import EventAccess, scope, locked, can_edit, conflict, output, is_contributor

class AssignmentInput(StrictSerializer):
    expected_version = serializers.IntegerField(min_value=1)
    collector_id = serializers.UUIDField(allow_null=True)
    reviewer_id = serializers.UUIDField(allow_null=True)

class AssignmentChoices(generics.GenericAPIView):
    permission_classes = [EventAccess]
    def get(self, request):
        if not request.user.has_perm('events.manage_all_occurrences'):
            return Response({'code':'forbidden'}, status=403)
        role = request.query_params.get('role')
        roles = {'collector': ['Administrator','Collector','Verifier','Editor'], 'reviewer': ['Administrator','Verifier','Editor']}
        if role not in roles:
            raise serializers.ValidationError({'role':'Choose collector or reviewer.'})
        qs = User.objects.filter(is_active=True, groups__name__in=roles[role]).distinct().order_by('email','pk')
        term = request.query_params.get('search','').strip()[:150]
        if term:
            qs = qs.filter(Q(display_name__icontains=term)|Q(email__icontains=term))
        return self.get_paginated_response([{'id':u.pk,'name':u.display_name or u.email} for u in self.paginate_queryset(qs)])

def assigned_user(pk, permission):
    if pk is None:
        return None
    user = User.objects.filter(pk=pk, is_active=True).first()
    if user is None or not user.has_perms(['events.view_occurrence', permission]):
        raise serializers.ValidationError({'assignment':'Select an active staff member with the required permission.'})
    return user

def assignment_output(row):
    return {'version':row.version, 'collector_id':row.assigned_collector_id, 'reviewer_id':row.assigned_reviewer_id,
            'collector_name':(row.assigned_collector.display_name or row.assigned_collector.email) if row.assigned_collector else '',
            'reviewer_name':(row.assigned_reviewer.display_name or row.assigned_reviewer.email) if row.assigned_reviewer else ''}

class Assignments(APIView):
    permission_classes = [EventAccess]
    def get(self, request, pk):
        row = get_object_or_404(scope(request.user),pk=pk)
        # Non-managers receive assignment flags but not staff email addresses.
        result = assignment_output(row)
        if not request.user.has_perm('events.manage_all_occurrences'):
            result = {k:v for k,v in result.items() if not k.endswith('_name')}
        return Response(result)

    @transaction.atomic
    def put(self, request, pk):
        if not request.user.has_perm('events.manage_all_occurrences'):
            return Response({'code':'forbidden'},status=403)
        data = AssignmentInput(data=request.data); data.is_valid(raise_exception=True)
        v = data.validated_data
        directory_lock(); row = locked(request.user,pk)
        if row.version != v['expected_version']:
            return conflict()
        if row.is_cancelled or row.status not in ('DRAFT','RETURNED','SUBMITTED','UNDER_REVIEW'):
            return Response({'code':'state_conflict','message':'Reopen the event before changing assignments.'},status=409)
        collector = assigned_user(v['collector_id'],'events.change_occurrence')
        reviewer = assigned_user(v['reviewer_id'],'events.review_occurrence')
        if reviewer and (reviewer == collector or is_contributor(reviewer,row)):
            raise serializers.ValidationError({'reviewer_id':'A contributor or assigned collector cannot be assigned as reviewer.'})
        before = {'collector_id':str(row.assigned_collector_id or ''), 'reviewer_id':str(row.assigned_reviewer_id or '')}
        row.assigned_collector=collector; row.assigned_reviewer=reviewer; row.version+=1
        row.save(update_fields=['assigned_collector','assigned_reviewer','version','updated_at'])
        audit(request.user,'event_assignments_updated',row.pk,before=before,after={'collector_id':str(row.assigned_collector_id or ''),'reviewer_id':str(row.assigned_reviewer_id or '')},version=row.version)
        return Response(output(row,request.user))

class AttachmentInput(StrictSerializer):
    expected_version = serializers.IntegerField(min_value=1)
    asset_ids = serializers.ListField(child=serializers.UUIDField(),max_length=12)
    def validate_asset_ids(self, ids):
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError('Image IDs must be unique.')
        return ids

class Attachments(APIView):
    permission_classes = [EventAccess]
    def get(self, request, pk):
        row = get_object_or_404(scope(request.user),pk=pk)
        return Response({'version':row.version,'images':list(row.attachments.values('asset_id','asset__name','asset__kind','asset__is_active','position'))})

    @transaction.atomic
    def put(self, request, pk):
        data=AttachmentInput(data=request.data);data.is_valid(raise_exception=True);v=data.validated_data
        directory_lock();row=locked(request.user,pk)
        if not can_edit(request.user,row):
            return Response({'code':'forbidden'},status=403)
        if row.version!=v['expected_version']:
            return conflict()
        if row.is_cancelled or row.status not in ('DRAFT','RETURNED'):
            return Response({'code':'state_conflict','message':'Only active drafts or returned events may be edited.'},status=409)
        ids=v['asset_ids']
        if row.poster_id in ids or len(list(MediaAsset.objects.select_for_update().filter(pk__in=ids,is_active=True,kind__in=['poster','photo']).values_list('pk',flat=True)))!=len(ids):
            raise serializers.ValidationError({'asset_ids':'Select unique active posters or photos, excluding the main poster.'})
        before=list(row.attachments.values_list('asset_id',flat=True))
        row.attachments.all().delete()
        EventAttachment.objects.bulk_create([EventAttachment(occurrence=row,asset_id=pk,position=i) for i,pk in enumerate(ids,1)])
        row.status='DRAFT';row.version+=1;row.save(update_fields=['status','version','updated_at'])
        audit(request.user,'event_attachments_updated',row.pk,before=list(map(str,before)),after=list(map(str,ids)),version=row.version)
        return Response(output(row,request.user))
