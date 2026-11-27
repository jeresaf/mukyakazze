from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [('events','0001_initial')]
    operations = [migrations.RunSQL(
        """CREATE FUNCTION events_reject_verification_change() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'verification records are append-only'; END; $$;
        CREATE TRIGGER events_verification_append_only BEFORE UPDATE OR DELETE ON events_verification FOR EACH ROW EXECUTE FUNCTION events_reject_verification_change();""",
        "DROP TRIGGER events_verification_append_only ON events_verification; DROP FUNCTION events_reject_verification_change();"
    )]
