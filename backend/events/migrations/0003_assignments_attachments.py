from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [('events','0002_verification_guard')]
    operations = [
        migrations.AddField(model_name='occurrence', name='assigned_collector', field=models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=django.db.models.deletion.PROTECT, related_name='+')),
        migrations.AddField(model_name='occurrence', name='assigned_reviewer', field=models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=django.db.models.deletion.PROTECT, related_name='+')),
        migrations.CreateModel(name='EventAttachment', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('position', models.PositiveSmallIntegerField()),
            ('occurrence', models.ForeignKey('events.occurrence', on_delete=django.db.models.deletion.PROTECT, related_name='attachments')),
            ('asset', models.ForeignKey('catalog.mediaasset', on_delete=django.db.models.deletion.PROTECT)),
        ], options={'ordering':['position','pk'], 'constraints':[models.UniqueConstraint(fields=['occurrence','asset'], name='events_attachment_asset_unique'),models.UniqueConstraint(fields=['occurrence','position'], name='events_attachment_position_unique')]}),
    ]
