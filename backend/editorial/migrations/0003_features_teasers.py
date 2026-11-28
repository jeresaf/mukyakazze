import uuid
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('editorial', '0002_cover_grid')]
    operations = [
        migrations.AddField('issue', 'feature_title', models.CharField(blank=True, default='', max_length=150)),
        migrations.AddField('issue', 'feature_subtitle', models.CharField(blank=True, default='', max_length=250)),
        migrations.AddField('issue', 'feature_kicker', models.CharField(blank=True, default='', max_length=150)),
        migrations.AddField('issue', 'feature_tips', models.JSONField(blank=True, default=list)),
        migrations.AddField('issue', 'sponsor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to='catalog.sponsor')),
        migrations.AddField('issue', 'sponsor_logo', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to='catalog.mediaasset')),
        migrations.AddField('issue', 'website_label', models.CharField(blank=True, default='', max_length=250)),
        migrations.AddField('issue', 'whatsapp_label', models.CharField(blank=True, default='', max_length=250)),
        migrations.AddField('issue', 'submission_contact', models.CharField(blank=True, default='', max_length=250)),
        migrations.CreateModel(name='ComingUp', fields=[
            ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ('date', models.DateField()), ('name', models.CharField(max_length=200)), ('place', models.CharField(max_length=200)),
            ('source', models.CharField(max_length=500)), ('position', models.PositiveSmallIntegerField()),
            ('issue', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='teasers', to='editorial.issue')),
            ('category', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='catalog.category')),
        ], options={'ordering': ['position', 'id'], 'constraints': [models.UniqueConstraint(fields=('issue', 'position'), name='editorial_teaser_position_unique'), models.CheckConstraint(condition=models.Q(position__gte=1, position__lte=30), name='editorial_teaser_position_range')]}),
    ]
