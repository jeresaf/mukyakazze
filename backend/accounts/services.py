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
        group.permissions.set(permissions)

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
