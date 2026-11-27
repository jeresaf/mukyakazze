from django.db import migrations

# Exact labels and colours from the original workbook Lists sheet.
CATEGORIES = [
    ('MUSIC', 'MUSIC', '#FFD400'),
    ('NIGHTLIFE', 'NIGHTLIFE', '#FF4FA3'),
    ('COMEDY', 'COMEDY', '#5CF0A0'),
    ('STAGE', 'STAGE', '#FF8A3D'),
    ('FILM', 'FILM', '#5EC4FF'),
    ('ART', 'ART', '#C3A2FF'),
    ('FOOD', 'FOOD', '#C6F432'),
    ('FAMILY', 'FAMILY', '#F4F1EA'),
    ('SPORT', 'SPORT', '#7FE3D8'),
    ('FAITH', 'FAITH', '#FFC9A8'),
    ('BUSINESS_NETWORKING', 'BUSINESS & NETWORKING', '#B9C7DA'),
]


def seed(apps, schema_editor):
    Category = apps.get_model('catalog', 'Category')
    for order, (code, label, colour) in enumerate(CATEGORIES, 1):
        Category.objects.using(schema_editor.connection.alias).get_or_create(
            code=code, defaults={'label': label, 'colour': colour, 'display_order': order}
        )


class Migration(migrations.Migration):
    dependencies = [('catalog', '0001_initial')]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
