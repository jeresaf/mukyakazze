from django.db import IntegrityError, transaction
from django.db.models import Q
from rest_framework import generics, permissions, serializers
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView
from accounts.services import audit
from .models import Category
from .serializers import CategoryOutput, CategoryCreate, CategoryChange


class CategoryAccess(permissions.BasePermission):
    def has_permission(self, request, view):
        codename = 'view_category' if request.method in permissions.SAFE_METHODS else 'manage_categories'
        return request.user.is_authenticated and request.user.has_perm('catalog.' + codename)


def snapshot(category):
    return {key: getattr(category, key) for key in ('code', 'label', 'colour', 'display_order', 'is_active', 'version')}


class Categories(generics.ListAPIView):
    permission_classes = [CategoryAccess]
    serializer_class = CategoryOutput

    def get_queryset(self):
        qs = Category.objects.all()
        status = self.request.query_params.get('status', 'active')
        if status not in ('active', 'archived', 'all'):
            raise serializers.ValidationError({'status': 'Expected active, archived or all.'})
        if status != 'all':
            qs = qs.filter(is_active=status == 'active')
        term = self.request.query_params.get('search', '').strip()[:100]
        if term:
            qs = qs.filter(Q(label__icontains=term) | Q(code__icontains=term))
        return qs

    def post(self, request):
        data = CategoryCreate(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                category = Category.objects.create(created_by=request.user, **data.validated_data)
                audit(request.user, 'category_created', category.pk, after=snapshot(category))
        except IntegrityError:
            raise serializers.ValidationError({'category': 'Category code or label already exists, or a constraint was violated.'})
        return Response(CategoryOutput(category).data, status=201)


class CategoryDetail(APIView):
    permission_classes = [CategoryAccess]

    def get(self, request, pk):
        return Response(CategoryOutput(get_object_or_404(Category, pk=pk)).data)

    def patch(self, request, pk):
        data = CategoryChange(data=request.data)
        data.is_valid(raise_exception=True)
        values = dict(data.validated_data)
        expected = values.pop('expected_version')
        try:
            with transaction.atomic():
                category = get_object_or_404(Category.objects.select_for_update(), pk=pk)
                if expected != category.version:
                    return Response({'code': 'stale_version', 'message': 'Refresh category before editing.'}, status=409)
                before = snapshot(category)
                for key, value in values.items():
                    setattr(category, key, value)
                category.version += 1
                category.save()
                after = snapshot(category)
                action = 'category_updated'
                if before['is_active'] != after['is_active']:
                    action = 'category_restored' if category.is_active else 'category_archived'
                audit(request.user, action, category.pk, before=before, after=after)
        except IntegrityError:
            raise serializers.ValidationError({'category': 'Category label already exists, or a constraint was violated.'})
        return Response(CategoryOutput(category).data)
