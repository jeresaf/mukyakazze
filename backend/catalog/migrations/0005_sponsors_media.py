import uuid
import django.db.models.deletion
import django.db.models.functions.text
from django.conf import settings
from django.db import migrations, models


def common_fields():
    return [
        ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
        ('name', models.CharField(max_length=150)),
        ('is_active', models.BooleanField(default=True)),
        ('version', models.PositiveIntegerField(default=1)),
        ('created_at', models.DateTimeField(auto_now_add=True)),
        ('updated_at', models.DateTimeField(auto_now=True)),
        ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to=settings.AUTH_USER_MODEL)),
    ]


class Migration(migrations.Migration):
    dependencies = [('catalog', '0004_seed_locations'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name='Sponsor', fields=common_fields()+[
            ('contact_name', models.CharField(blank=True, default='', max_length=150)),
            ('contact_phone', models.CharField(blank=True, default='', max_length=40)),
            ('contact_email', models.EmailField(blank=True, default='', max_length=254)),
            ('website', models.URLField(blank=True, default='', max_length=250)),
        ], options={'ordering': ['name', 'id'], 'abstract': False, 'constraints': [models.CheckConstraint(condition=models.Q(version__gte=1), name='catalog_sponsor_version_positive'), models.UniqueConstraint(django.db.models.functions.text.Lower('name'), name='catalog_sponsor_name_unique')]}),
        migrations.CreateModel(name='MediaAsset', fields=common_fields()+[
            ('kind', models.CharField(choices=[('poster', 'Event poster'), ('cover', 'Cover photo'), ('logo', 'Logo'), ('photo', 'Other photo')], max_length=16)),
            ('mime_type', models.CharField(max_length=16)),
            ('width', models.PositiveIntegerField()),
            ('height', models.PositiveIntegerField()),
            ('size_bytes', models.PositiveIntegerField()),
            ('sha256', models.CharField(db_index=True, max_length=64)),
            ('content', models.BinaryField(editable=False)),
            ('alt_text', models.CharField(blank=True, default='', max_length=250)),
        ], options={'ordering': ['name', 'id'], 'abstract': False, 'constraints': [models.CheckConstraint(condition=models.Q(version__gte=1), name='catalog_mediaasset_version_positive'), models.CheckConstraint(condition=models.Q(kind__in=['poster', 'cover', 'logo', 'photo']), name='catalog_media_kind_valid'), models.CheckConstraint(condition=models.Q(mime_type__in=['image/jpeg', 'image/png']), name='catalog_media_mime_valid'), models.CheckConstraint(condition=models.Q(size_bytes__gte=1, size_bytes__lte=5242880), name='catalog_media_size_valid')]}),
    ]
