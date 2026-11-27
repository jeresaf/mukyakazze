import uuid
import django.db.models.deletion
import django.db.models.functions.text
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('catalog', '0002_seed_categories'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name='Country',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=150)),
                ('is_active', models.BooleanField(default=True)),
                ('version', models.PositiveIntegerField(default=1)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['name', 'id'], 'abstract': False, 'constraints': [models.CheckConstraint(condition=models.Q(version__gte=1), name='catalog_country_version_positive'), models.UniqueConstraint(django.db.models.functions.text.Lower('name'), name='catalog_country_name_unique')]},
        ),
        migrations.CreateModel(
            name='City',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=150)),
                ('is_active', models.BooleanField(default=True)),
                ('version', models.PositiveIntegerField(default=1)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('country', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='catalog.country')),
            ],
            options={'ordering': ['name', 'id'], 'abstract': False, 'constraints': [models.CheckConstraint(condition=models.Q(version__gte=1), name='catalog_city_version_positive'), models.UniqueConstraint(django.db.models.functions.text.Lower('name'), 'country', name='catalog_city_parent_name_unique')]},
        ),
        migrations.CreateModel(
            name='Area',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=150)),
                ('is_active', models.BooleanField(default=True)),
                ('version', models.PositiveIntegerField(default=1)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('city', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='catalog.city')),
            ],
            options={'ordering': ['name', 'id'], 'abstract': False, 'constraints': [models.CheckConstraint(condition=models.Q(version__gte=1), name='catalog_area_version_positive'), models.UniqueConstraint(django.db.models.functions.text.Lower('name'), 'city', name='catalog_area_parent_name_unique')]},
        ),
        migrations.CreateModel(
            name='Venue',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=150)),
                ('is_active', models.BooleanField(default=True)),
                ('version', models.PositiveIntegerField(default=1)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('venue_type', models.CharField(blank=True, default='', max_length=100)),
                ('address', models.CharField(blank=True, default='', max_length=250)),
                ('website', models.URLField(blank=True, default='', max_length=250)),
                ('contact_phone', models.CharField(blank=True, default='', max_length=40)),
                ('latitude', models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
                ('longitude', models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
                ('area', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='catalog.area')),
            ],
            options={'ordering': ['name', 'id'], 'abstract': False, 'constraints': [models.CheckConstraint(condition=models.Q(version__gte=1), name='catalog_venue_version_positive'), models.UniqueConstraint(django.db.models.functions.text.Lower('name'), 'area', name='catalog_venue_parent_name_unique'), models.CheckConstraint(condition=(models.Q(latitude__isnull=True, longitude__isnull=True) | (models.Q(latitude__isnull=False, longitude__isnull=False) & models.Q(latitude__gte=-90, latitude__lte=90, longitude__gte=-180, longitude__lte=180))), name='catalog_venue_coordinates_valid')]},
        ),
        migrations.CreateModel(
            name='Promoter',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=150)),
                ('is_active', models.BooleanField(default=True)),
                ('version', models.PositiveIntegerField(default=1)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('contact_name', models.CharField(blank=True, default='', max_length=150)),
                ('contact_phone', models.CharField(blank=True, default='', max_length=40)),
                ('contact_email', models.EmailField(blank=True, default='', max_length=254)),
                ('website', models.URLField(blank=True, default='', max_length=250)),
            ],
            options={'ordering': ['name', 'id'], 'abstract': False, 'constraints': [models.CheckConstraint(condition=models.Q(version__gte=1), name='catalog_promoter_version_positive'), models.UniqueConstraint(django.db.models.functions.text.Lower('name'), name='catalog_promoter_name_unique')], 'permissions': [('view_private_contacts', 'View private directory contacts')]},
        ),
    ]
