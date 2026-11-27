from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import Group
from django.db import IntegrityError, connection, transaction
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.views.decorators.http import require_GET
from django.utils.decorators import method_decorator
from rest_framework import generics, permissions, serializers
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import User, AuditEvent
from .serializers import LoginSerializer, UserOutput, UserCreate, UserChange, RevokeSerializer, AuditOutput
from .services import allow_login, audit, ROLES

class ManageAccounts(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.has_perm('accounts.manage_accounts')

class ViewAudit(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.has_perm('accounts.view_security_audit')

@method_decorator(csrf_protect, name='dispatch')
class Login(APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    def post(self, request):
        data = LoginSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        email = data.validated_data['email'].strip().lower()
        if not allow_login(email, request.META.get('REMOTE_ADDR', 'unknown')):
            return Response({'code': 'rate_limited', 'message': 'Try again later.'}, status=429)
        user = authenticate(request, email=email, password=data.validated_data['password'])
        if user is None:
            return Response({'code': 'invalid_credentials', 'message': 'Invalid credentials.'}, status=403)
        with transaction.atomic():
            user = User.objects.select_for_update().get(pk=user.pk)
            if not user.is_active or not user.check_password(data.validated_data['password']):
                return Response({'code': 'invalid_credentials', 'message': 'Invalid credentials.'}, status=403)
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            request.session.cycle_key()
            request.session['account_version'] = user.session_version
            audit(user, 'login', user.pk)
        return Response({'user': UserOutput(user).data, 'csrf_token': get_token(request)})

class Logout(APIView):
    def post(self, request):
        audit(request.user, 'logout', request.user.pk)
        logout(request)
        return Response(status=204)

@method_decorator(ensure_csrf_cookie, name='dispatch')
class Session(APIView):
    permission_classes = [permissions.AllowAny]
    def get(self, request):
        return Response({'user': UserOutput(request.user).data if request.user.is_authenticated else None, 'csrf_token': get_token(request), 'permissions': {'manage_accounts': request.user.has_perm('accounts.manage_accounts'), 'view_audit': request.user.has_perm('accounts.view_security_audit'), 'view_categories': request.user.has_perm('catalog.view_category'), 'manage_categories': request.user.has_perm('catalog.manage_categories'), 'view_directory': all(request.user.has_perm('catalog.view_' + model) for model in ('country', 'city', 'area', 'venue', 'promoter', 'sponsor')), 'manage_directory': all(request.user.has_perm('catalog.' + action + '_' + model) for action in ('add', 'change') for model in ('country', 'city', 'area', 'venue', 'promoter', 'sponsor')), 'view_private_contacts': request.user.has_perm('catalog.view_private_contacts'), 'view_media': request.user.has_perm('catalog.view_mediaasset'), 'manage_media': request.user.has_perms(['catalog.add_mediaasset', 'catalog.change_mediaasset']), 'view_events': request.user.has_perm('events.view_occurrence'), 'create_events': request.user.has_perm('events.add_occurrence'), 'review_events': request.user.has_perm('events.review_occurrence'), 'view_issues': request.user.has_perm('editorial.view_issue'), 'manage_issues': request.user.has_perm('editorial.change_issue'), 'manage_events': request.user.has_perm('events.manage_all_occurrences')}}, headers={'Cache-Control': 'no-store'})

class Roles(APIView):
    permission_classes = [ManageAccounts]
    def get(self, request):
        return Response(list(Group.objects.filter(name__in=ROLES).order_by('name').values_list('name', flat=True)))

class Users(generics.ListAPIView):
    permission_classes = [ManageAccounts]
    serializer_class = UserOutput
    queryset = User.objects.order_by('email')
    def post(self, request):
        data = UserCreate(data=request.data)
        data.is_valid(raise_exception=True)
        values = dict(data.validated_data)
        roles = values.pop('roles')
        try:
            with transaction.atomic():
                user = User.objects.create_user(**values)
                user.groups.set(Group.objects.filter(name__in=roles))
                audit(request.user, 'account_created', user.pk, roles=roles)
        except IntegrityError:
            raise serializers.ValidationError({'email': 'Account already exists.'})
        return Response(UserOutput(user).data, status=201)

class UserDetail(APIView):
    permission_classes = [ManageAccounts]
    def get(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        return Response(UserOutput(user).data)
    @transaction.atomic
    def patch(self, request, pk):
        data = UserChange(data=request.data)
        data.is_valid(raise_exception=True)
        values = dict(data.validated_data)
        user = get_object_or_404(User.objects.select_for_update(), pk=pk)
        if user.is_superuser or user.pk == request.user.pk:
            return Response({'code': 'protected_account', 'message': 'Self and recovery accounts cannot be modified here.'}, status=403)
        if values.pop('expected_version') != user.session_version:
            return Response({'code': 'stale_version', 'message': 'Refresh account before editing.'}, status=409)
        before = {'display_name': user.display_name, 'is_active': user.is_active, 'roles': list(user.groups.values_list('name', flat=True))}
        roles = values.pop('roles', None)
        if roles is not None:
            groups = Group.objects.filter(name__in=roles)
            if groups.count() != len(set(roles)):
                raise serializers.ValidationError({'roles': 'Roles not provisioned.'})
            user.groups.set(groups)
        for key, value in values.items():
            setattr(user, key, value)
        user.session_version += 1
        user.save()
        audit(request.user, 'account_updated', user.pk, before=before, after={'display_name': user.display_name, 'is_active': user.is_active, 'roles': list(user.groups.values_list('name', flat=True))})
        return Response(UserOutput(user).data)

class Revoke(APIView):
    permission_classes = [ManageAccounts]
    @transaction.atomic
    def post(self, request, pk):
        data = RevokeSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        user = get_object_or_404(User.objects.select_for_update(), pk=pk)
        if user.is_superuser or user.pk == request.user.pk:
            return Response({'code': 'protected_account'}, status=403)
        if user.session_version != data.validated_data['expected_version']:
            return Response({'code': 'stale_version'}, status=409)
        user.session_version += 1
        user.save(update_fields=['session_version'])
        audit(request.user, 'sessions_revoked', user.pk)
        return Response(UserOutput(user).data)

class Audit(generics.ListAPIView):
    permission_classes = [ViewAudit]
    serializer_class = AuditOutput
    queryset = AuditEvent.objects.all()

@require_GET
def live(request):
    return JsonResponse({'status': 'ok'})

@require_GET
def ready(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
    except Exception:
        return JsonResponse({'status': 'unavailable'}, status=503)
    return JsonResponse({'status': 'ready'})
