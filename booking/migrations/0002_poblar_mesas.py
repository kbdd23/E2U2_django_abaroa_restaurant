# Data migration: poblacion inicial del salon con las 8 mesas del diseno.
from django.db import migrations


def poblar_mesas(apps, schema_editor):
    Mesa = apps.get_model('booking', 'Mesa')
    mesas = [
        {'numero': 1, 'capacidad': 4, 'ubicacion': 'ventana', 'es_grande': False},
        {'numero': 2, 'capacidad': 4, 'ubicacion': 'terraza', 'es_grande': False},
        {'numero': 3, 'capacidad': 4, 'ubicacion': 'ventana', 'es_grande': False},
        {'numero': 4, 'capacidad': 4, 'ubicacion': 'salon central', 'es_grande': False},
        {'numero': 5, 'capacidad': 4, 'ubicacion': 'terraza', 'es_grande': False},
        {'numero': 6, 'capacidad': 4, 'ubicacion': 'salon central', 'es_grande': False},
        {'numero': 7, 'capacidad': 8, 'ubicacion': 'salon central', 'es_grande': True},
        {'numero': 8, 'capacidad': 8, 'ubicacion': 'terraza', 'es_grande': True},
    ]
    Mesa.objects.bulk_create(Mesa(**mesa) for mesa in mesas)


def vaciar_mesas(apps, schema_editor):
    Mesa = apps.get_model('booking', 'Mesa')
    Mesa.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('booking', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(poblar_mesas, vaciar_mesas),
    ]
