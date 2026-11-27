import uuid
from django.conf import settings
from django.db import models
from django.db.models.functions import Lower


class Category(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=64, unique=True)
    label = models.CharField(max_length=100)
    colour = models.CharField(max_length=7)
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['display_order', 'code']
        permissions = [('manage_categories', 'Manage entertainment categories')]
        constraints = [
            models.UniqueConstraint(Lower('label'), name='catalog_category_label_lower_unique'),
            models.CheckConstraint(condition=models.Q(code__regex=r'^[A-Z][A-Z0-9_]*$'), name='catalog_category_code_format'),
            models.CheckConstraint(condition=models.Q(colour__regex=r'^#[0-9A-F]{6}$'), name='catalog_category_colour_format'),
            models.CheckConstraint(condition=models.Q(version__gte=1), name='catalog_category_version_positive'),
        ]
