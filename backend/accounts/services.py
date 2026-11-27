from datetime import timedelta
import hashlib
from django.contrib.auth.models import Group, Permission
from django.db import transaction
from django.utils import timezone
from .models import AuditEvent, LoginBucket

ROLES = ('Administrator', 'Collector', 'Verifier', 'Editor', 'Publisher')

def audit(actor, action, target_id=None, **details):
    return AuditEvent.objects.create(actor=actor, action=action, target_id=target_id, details=details)

@transaction.atomic
def provision_roles():
    for name in ROLES:
        group, _ = Group.objects.get_or_create(name=name)
        permissions = Permission.objects.filter(content_type__app_label='accounts', codename__in=['manage_accounts', 'view_security_audit']) if name == 'Administrator' else Permission.objects.none()
        catalog_permissions = Permission.objects.filter(content_type__app_label='catalog', codename__in=['view_category', 'manage_categories'] if name in ('Administrator', 'Editor') else ['view_category'])
        directory_models = ('country', 'city', 'area', 'venue', 'promoter', 'sponsor')
        codes = ['view_' + model for model in directory_models]
        if name in ('Administrator', 'Editor'):
            codes += [action + '_' + model for action in ('add', 'change') for model in directory_models]
            codes += ['view_private_contacts']
        directory_permissions = Permission.objects.filter(content_type__app_label='catalog', codename__in=codes)
        media_codes = ['view_mediaasset']
        if name in ('Administrator', 'Editor'):
            media_codes += ['add_mediaasset', 'change_mediaasset']
        media_permissions = Permission.objects.filter(content_type__app_label='catalog', codename__in=media_codes)
        event_codes = []
        if name in ('Administrator', 'Collector', 'Verifier', 'Editor'):
            event_codes += ['view_occurrence','add_occurrence','change_occurrence']
        if name in ('Administrator', 'Verifier', 'Editor'):
            event_codes += ['review_occurrence']
        if name in ('Administrator', 'Editor'):
            event_codes += ['manage_all_occurrences']
        event_permissions = Permission.objects.filter(content_type__app_label='events', codename__in=event_codes)
        group.permissions.set(list(permissions) + list(catalog_permissions) + list(directory_permissions) + list(media_permissions) + list(event_permissions))

@transaction.atomic
def allow_login(email, remote_address):
    now = timezone.now()
    keys = sorted([(hashlib.sha256(('account:' + email).encode()).hexdigest(), 10), (hashlib.sha256(('address:' + remote_address).encode()).hexdigest(), 40)])
    allowed = True
    for key, limit in keys:
        LoginBucket.objects.get_or_create(key=key)
        bucket = LoginBucket.objects.select_for_update().get(key=key)
        if now - bucket.window_start >= timedelta(minutes=15):
            bucket.window_start = now
            bucket.attempts = 0
        if bucket.attempts >= limit:
            allowed = False
        else:
            bucket.attempts += 1
        bucket.save(update_fields=['window_start', 'attempts'])
    return allowed
