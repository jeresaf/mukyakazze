from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [('accounts', '0001_initial')]
    operations = [migrations.RunSQL(
        """CREATE FUNCTION accounts_reject_audit_change() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'audit records are append-only'; END; $$;
        CREATE TRIGGER accounts_audit_append_only BEFORE UPDATE OR DELETE ON accounts_auditevent FOR EACH ROW EXECUTE FUNCTION accounts_reject_audit_change();""",
        "DROP TRIGGER accounts_audit_append_only ON accounts_auditevent; DROP FUNCTION accounts_reject_audit_change();"
    )]
