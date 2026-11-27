import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('editorial', '0001_initial'), ('catalog', '0005_sponsors_media')]
    operations = [
        migrations.AddField('issue', 'cover_accent', models.CharField(default='#FFD400', max_length=7)),
        migrations.AddField('issue', 'cover_name', models.CharField(blank=True, default='', max_length=150)),
        migrations.AddField('issue', 'cover_subtitle', models.CharField(blank=True, default='', max_length=250)),
        migrations.AddField('issue', 'cover_lines', models.JSONField(blank=True, default=list)),
        migrations.AddField('issue', 'cover_photo', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to='catalog.mediaasset')),
        migrations.AddField('issue', 'headshot', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to='catalog.mediaasset')),
        migrations.AddField('issue', 'grid_configuration', models.JSONField(blank=True, default=dict)),
    ]
