"""Authenticated master-data endpoints; all mutations share a transaction lock."""
from django.db import IntegrityError, connection, transaction
from django.db.models import Q
from rest_framework import generics, permissions, serializers
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView
from accounts.serializers import StrictSerializer
from accounts.services import audit
from .models import Country, City, Area, Venue, Promoter

RESOURCES = {
    'countries': (Country, None, None),
    'cities': (City, 'country', Country),
    'areas': (Area, 'city', City),
    'venues': (Venue, 'area', Area),
    'promoters': (Promoter, None, None),
}
CHILDREN = {Country: (City, 'country'), City: (Area, 'city'), Area: (Venue, 'area')}
PRIVATE_FIELDS = {'contact_name', 'contact_phone', 'contact_email'}
EXTRA_FIELDS = {
    Venue: ('venue_type', 'address', 'website', 'contact_phone', 'latitude', 'longitude'),
    Promoter: ('contact_name', 'contact_phone', 'contact_email', 'website'),
}


def directory_lock():
    # PostgreSQL transaction-level advisory lock. Every directory mutation uses
    # this key to serialize parent activation checks and child writes.
    with connection.cursor() as cursor:
        cursor.execute('SELECT pg_advisory_xact_lock(%s)', [726202602])


class DirectoryAccess(permissions.BasePermission):
    def has_permission(self, request, view):
        model = RESOURCES[view.resource][0]
        action = 'view' if request.method in permissions.SAFE_METHODS else ('add' if request.method == 'POST' else 'change')
        return request.user.is_authenticated and request.user.has_perm(f'catalog.{action}_{model._meta.model_name}')


class DirectoryInput(StrictSerializer):
    def get_fields(self):
        model, parent, _ = self.context['spec']
        editing = self.context['editing']
        fields = {'name': serializers.CharField(max_length=150, required=not editing)}
        if editing:
            fields.update(expected_version=serializers.IntegerField(min_value=1), is_active=serializers.BooleanField(required=False))
        elif parent:
            fields[parent+'_id'] = serializers.UUIDField()
        for key in EXTRA_FIELDS.get(model, ()):
            if key in PRIVATE_FIELDS and not self.context['private']:
                continue
            if key == 'website':
                fields[key] = serializers.URLField(max_length=250, allow_blank=True, required=False)
            elif key == 'contact_email':
                fields[key] = serializers.EmailField(max_length=254, allow_blank=True, required=False)
            elif key in ('latitude', 'longitude'):
                limit = 90 if key == 'latitude' else 180
                fields[key] = serializers.DecimalField(max_digits=9, decimal_places=6, min_value=-limit, max_value=limit, required=False, allow_null=True)
            else:
                fields[key] = serializers.CharField(max_length=model._meta.get_field(key).max_length, allow_blank=True, required=False)
        return fields

    def validate(self, attrs):
        if self.context['editing'] and len(attrs) == 1:
            raise serializers.ValidationError('No changes supplied.')
        if 'website' in attrs and attrs['website'] and not attrs['website'].lower().startswith(('https://', 'http://')):
            raise serializers.ValidationError({'website': 'Use an HTTP or HTTPS URL.'})
        return attrs


def output(record, parent, private):
    data = {key: getattr(record, key) for key in ('id', 'name', 'is_active', 'version', 'created_at', 'updated_at')}
    if parent:
        data[parent+'_id'] = getattr(record, parent+'_id')
        data['parent_name'] = getattr(record, parent).name
    for key in EXTRA_FIELDS.get(type(record), ()):
        if key in PRIVATE_FIELDS and not private:
            continue
        value = getattr(record, key)
        data[key] = str(value) if key in ('latitude', 'longitude') and value is not None else value
    return data


def validate_record(model, parent, parent_model, values, record=None):
    active = values.get('is_active', record.is_active if record else True)
    if active and parent:
        parent_id = getattr(record, parent+'_id') if record else values[parent+'_id']
        if not parent_model.objects.filter(pk=parent_id, is_active=True).exists():
            raise serializers.ValidationError({parent+'_id': 'Select an active parent.'})
    if record and not active and model in CHILDREN:
        child, field = CHILDREN[model]
        if child.objects.filter(**{field: record, 'is_active': True}).exists():
            raise serializers.ValidationError({'is_active': 'Archive active child records first.'})
    if model is Venue:
        lat = values.get('latitude', record.latitude if record else None)
        lon = values.get('longitude', record.longitude if record else None)
        if (lat is None) != (lon is None):
            raise serializers.ValidationError({'latitude': 'Enter both coordinates or leave both blank.'})


class DirectoryBase:
    resource = None
    permission_classes = [DirectoryAccess]

    @property
    def spec(self):
        return RESOURCES[self.resource]

    def private(self):
        return self.request.user.has_perm('catalog.view_private_contacts')

    def input(self, editing):
        data = DirectoryInput(data=self.request.data, context={'spec': self.spec, 'editing': editing, 'private': self.private()})
        data.is_valid(raise_exception=True)
        return dict(data.validated_data)

    def queryset(self):
        model, parent, _ = self.spec
        qs = model.objects.all()
        return qs.select_related(parent) if parent else qs


class DirectoryList(DirectoryBase, generics.GenericAPIView):
    def get(self, request):
        _, parent, _ = self.spec
        qs = self.queryset()
        status = request.query_params.get('status', 'active')
        if status not in ('active', 'archived', 'all'):
            raise serializers.ValidationError({'status': 'Expected active, archived or all.'})
        if status != 'all':
            qs = qs.filter(is_active=status == 'active')
        term = request.query_params.get('search', '').strip()[:150]
        if term:
            query = Q(name__icontains=term)
            if parent:
                query |= Q(**{parent+'__name__icontains': term})
            qs = qs.filter(query)
        if 'parent' in request.query_params:
            if not parent:
                raise serializers.ValidationError({'parent': 'Not applicable.'})
            parent_id = serializers.UUIDField().run_validation(request.query_params['parent'])
            qs = qs.filter(**{parent+'_id': parent_id})
        page = self.paginate_queryset(qs)
        return self.get_paginated_response([output(r, parent, self.private()) for r in page])

    def post(self, request):
        model, parent, parent_model = self.spec
        values = self.input(False)
        try:
            with transaction.atomic():
                directory_lock()
                validate_record(model, parent, parent_model, values)
                record = model.objects.create(created_by=request.user, **values)
                audit(request.user, model._meta.model_name+'_created', record.pk, fields=sorted(values))
        except IntegrityError:
            raise serializers.ValidationError({'name': 'Duplicate name in this directory or another constraint was violated.'})
        return Response(output(record, parent, self.private()), status=201)


class DirectoryDetail(DirectoryBase, APIView):
    def get(self, request, pk):
        return Response(output(get_object_or_404(self.queryset(), pk=pk), self.spec[1], self.private()))

    def patch(self, request, pk):
        model, parent, parent_model = self.spec
        values = self.input(True)
        expected = values.pop('expected_version')
        try:
            with transaction.atomic():
                directory_lock()
                record = get_object_or_404(model.objects.select_for_update(), pk=pk)
                if record.version != expected:
                    return Response({'code':'stale_version','message':'Refresh record before editing.'}, status=409)
                validate_record(model, parent, parent_model, values, record)
                before = record.is_active
                for key, value in values.items():
                    setattr(record, key, value)
                record.version += 1
                record.save()
                action = 'updated' if before == record.is_active else ('restored' if record.is_active else 'archived')
                # Record changed field names, not private contact values.
                audit(request.user, model._meta.model_name+'_'+action, record.pk, fields=sorted(values), version=record.version)
        except IntegrityError:
            raise serializers.ValidationError({'name': 'Duplicate name in this directory or another constraint was violated.'})
        return Response(output(record, parent, self.private()))
