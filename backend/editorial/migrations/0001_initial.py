import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL), ('events','0003_assignments_attachments')]
    operations = [
        migrations.CreateModel(name='Issue', fields=[
            ('id',models.UUIDField(default=uuid.uuid4,editable=False,primary_key=True,serialize=False)),
            ('number',models.PositiveIntegerField(unique=True)), ('week_start',models.DateField(unique=True)), ('grid_day',models.DateField()),
            ('picks_title',models.CharField(default="BUGY'S PICKS",max_length=120)), ('picks_byline',models.CharField(blank=True,default='',max_length=150)),
            ('picks_intro',models.TextField(blank=True,default='')), ('version',models.PositiveIntegerField(default=1)),
            ('created_at',models.DateTimeField(auto_now_add=True)), ('updated_at',models.DateTimeField(auto_now=True)),
            ('created_by',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name='+',to=settings.AUTH_USER_MODEL)),
        ], options={'ordering':['-week_start','id'],'constraints':[models.CheckConstraint(condition=models.Q(number__gte=1),name='editorial_issue_number_positive'),models.CheckConstraint(condition=models.Q(version__gte=1),name='editorial_issue_version_positive')]}),
        migrations.CreateModel(name='IssueEvent', fields=[
            ('id',models.UUIDField(default=uuid.uuid4,editable=False,primary_key=True,serialize=False)),
            ('occurrence_version',models.PositiveIntegerField()), ('rank',models.PositiveSmallIntegerField(blank=True,null=True)),
            ('why_go',models.CharField(blank=True,default='',max_length=500)), ('curator_playing',models.BooleanField(default=False)),
            ('paid_feature',models.BooleanField(default=False)),
            ('issue',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name='entries',to='editorial.issue')),
            ('occurrence',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,to='events.occurrence')),
        ], options={'ordering':['rank','id'],'constraints':[
            models.UniqueConstraint(fields=('issue','occurrence'),name='editorial_issue_occurrence_unique'),
            models.UniqueConstraint(fields=('issue','rank'),name='editorial_issue_rank_unique'),
            models.CheckConstraint(condition=models.Q(rank__isnull=True)|models.Q(rank__gte=1,rank__lte=7),name='editorial_issue_rank_range'),
        ]}),
    ]
