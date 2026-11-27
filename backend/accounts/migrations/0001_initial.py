import uuid
import django.db.models.deletion
import django.db.models.functions.text
import django.utils.timezone
import accounts.models
from django.db import migrations, models

class Migration(migrations.Migration):
    initial = True
    dependencies = [('auth', '0012_alter_user_first_name_max_length')]
    operations = [
        migrations.CreateModel(name='User', fields=[('password', models.CharField(max_length=128, verbose_name='password')), ('last_login', models.DateTimeField(blank=True, null=True, verbose_name='last login')), ('is_superuser', models.BooleanField(default=False, help_text='Designates that this user has all permissions without explicitly assigning them.', verbose_name='superuser status')), ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)), ('email', models.EmailField(max_length=254, unique=True)), ('display_name', models.CharField(blank=True, max_length=150)), ('is_active', models.BooleanField(default=True)), ('is_staff', models.BooleanField(default=False)), ('date_joined', models.DateTimeField(default=django.utils.timezone.now)), ('session_version', models.PositiveIntegerField(default=1)), ('groups', models.ManyToManyField(blank=True, help_text='The groups this user belongs to. A user will get all permissions granted to each of their groups.', related_name='user_set', related_query_name='user', to='auth.group', verbose_name='groups')), ('user_permissions', models.ManyToManyField(blank=True, help_text='Specific permissions for this user.', related_name='user_set', related_query_name='user', to='auth.permission', verbose_name='user permissions'))], options={'permissions': [('manage_accounts', 'Manage administrative accounts'), ('view_security_audit', 'View security audit')], 'constraints': [models.UniqueConstraint(django.db.models.functions.text.Lower('email'), name='accounts_user_email_lower_unique')]}, managers=[('objects', accounts.models.UserManager())]),
        migrations.CreateModel(name='AuditEvent', fields=[('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)), ('action', models.CharField(max_length=64)), ('target_id', models.UUIDField(null=True)), ('details', models.JSONField(default=dict)), ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)), ('actor', models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name='audit_events', to='accounts.user'))], options={'ordering': ['-created_at', '-id']}),
        migrations.CreateModel(name='LoginBucket', fields=[('key', models.CharField(max_length=64, primary_key=True, serialize=False)), ('window_start', models.DateTimeField(default=django.utils.timezone.now)), ('attempts', models.PositiveIntegerField(default=0))]),
    ]
