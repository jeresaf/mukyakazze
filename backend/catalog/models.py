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


class DirectoryRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=150)
    is_active = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ['name', 'id']
        constraints = [models.CheckConstraint(condition=models.Q(version__gte=1), name='%(app_label)s_%(class)s_version_positive')]


class Country(DirectoryRecord):
    class Meta(DirectoryRecord.Meta):
        constraints = DirectoryRecord.Meta.constraints + [models.UniqueConstraint(Lower('name'), name='catalog_country_name_unique')]


class City(DirectoryRecord):
    country = models.ForeignKey(Country, on_delete=models.PROTECT)

    class Meta(DirectoryRecord.Meta):
        constraints = DirectoryRecord.Meta.constraints + [models.UniqueConstraint(Lower('name'), 'country', name='catalog_city_parent_name_unique')]


class Area(DirectoryRecord):
    city = models.ForeignKey(City, on_delete=models.PROTECT)

    class Meta(DirectoryRecord.Meta):
        constraints = DirectoryRecord.Meta.constraints + [models.UniqueConstraint(Lower('name'), 'city', name='catalog_area_parent_name_unique')]


class Venue(DirectoryRecord):
    area = models.ForeignKey(Area, on_delete=models.PROTECT)
    venue_type = models.CharField(max_length=100, blank=True, default='')
    address = models.CharField(max_length=250, blank=True, default='')
    website = models.URLField(max_length=250, blank=True, default='')
    contact_phone = models.CharField(max_length=40, blank=True, default='')
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    class Meta(DirectoryRecord.Meta):
        constraints = DirectoryRecord.Meta.constraints + [
            models.UniqueConstraint(Lower('name'), 'area', name='catalog_venue_parent_name_unique'),
            models.CheckConstraint(condition=(models.Q(latitude__isnull=True, longitude__isnull=True) | (models.Q(latitude__isnull=False, longitude__isnull=False) & models.Q(latitude__gte=-90, latitude__lte=90, longitude__gte=-180, longitude__lte=180))), name='catalog_venue_coordinates_valid'),
        ]


class Promoter(DirectoryRecord):
    contact_name = models.CharField(max_length=150, blank=True, default='')
    contact_phone = models.CharField(max_length=40, blank=True, default='')
    contact_email = models.EmailField(blank=True, default='')
    website = models.URLField(max_length=250, blank=True, default='')

    class Meta(DirectoryRecord.Meta):
        constraints = DirectoryRecord.Meta.constraints + [models.UniqueConstraint(Lower('name'), name='catalog_promoter_name_unique')]
        permissions = [('view_private_contacts', 'View private directory contacts')]
