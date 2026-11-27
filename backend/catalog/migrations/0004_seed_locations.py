from django.db import migrations


def seed(apps, schema_editor):
    Country = apps.get_model('catalog', 'Country')
    City = apps.get_model('catalog', 'City')
    alias = schema_editor.connection.alias
    uganda, _ = Country.objects.using(alias).get_or_create(name='Uganda')
    City.objects.using(alias).get_or_create(country=uganda, name='Kampala')


class Migration(migrations.Migration):
    dependencies = [('catalog', '0003_directory')]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
