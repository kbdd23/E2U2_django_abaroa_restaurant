from django.db import migrations

# Carta inicial: los 5 alergenos y los 9 platos que hasta ahora estaban
# escritos a mano en templates/menu.html. El slug de cada alergeno es el
# valor que el frontend ya usaba en data-alergeno, asi que el JS de
# filtros sigue funcionando sin cambios.

ALERGENOS = [
    ('Gluten', 'gluten'),
    ('Lácteos', 'lacteos'),
    ('Huevo', 'huevo'),
    ('Maní', 'mani'),
    ('Soja', 'soja'),
]

PLATOS = [
    {
        'nombre': 'Lomo a lo Pobre',
        'descripcion': 'Corte jugoso con papas fritas, cebolla caramelizada y huevo. Alérgenos: gluten, huevo.',
        'precio': 12990,
        'categoria': 'carnes',
        'badge': 'Personalizado',
        'imagen': 'https://tofuu.getjusto.com/orioneat-local/resized2/ztPNQwvpzEvBuXtk9-2400-x.webp',
        'alergenos': ['gluten', 'huevo'],
    },
    {
        'nombre': 'Desayuno Completo',
        'descripcion': 'Huevos revueltos, pan tostado, jugo natural y café recién hecho. Alérgenos: gluten, huevo.',
        'precio': 8790,
        'categoria': 'carnes',
        'badge': 'Favorito',
        'imagen': 'https://tofuu.getjusto.com/orioneat-local/resized2/zs3KperB46QojFCb2-2400-x.webp',
        'alergenos': ['gluten', 'huevo'],
    },
    {
        'nombre': 'Ensalada Vegana',
        'descripcion': 'Mix de lechugas, tomates, palta y aderezo cítrico. Alérgenos: ninguno.',
        'precio': 7200,
        'categoria': 'vegano',
        'badge': 'Saludable',
        'imagen': 'https://recetasveganas.net/wp-content/uploads/2020/03/ensalada-quinoa-espinaca-rucula-salsa-mango-recetas-vegetarianas1.jpg',
        'alergenos': [],
    },
    {
        'nombre': 'Jugo Natural de Mango',
        'descripcion': 'Jugo natural de mango sin azúcar añadida, ideal para acompañar tu pedido. Alérgenos: ninguno.',
        'precio': 3490,
        'categoria': 'bebidas',
        'badge': 'Fresco',
        'imagen': 'https://www.absolutdrinks.com/cdn-cgi/image/fit=cover,format=auto,height=540,quality=55,width=960/wp-content/uploads/ingredient_mango-juice_16x9_c39ef0c0569d5bf7f736ac6f2b10be33.jpg',
        'alergenos': [],
    },
    {
        'nombre': 'Barroluco',
        'descripcion': 'Pan, Carne de vacuno, queso derretido. Alérgenos: gluten, lácteos.',
        'precio': 3000,
        'categoria': 'carnes',
        'badge': 'Clásico',
        'imagen': 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQJvgGShGBPLyTYZ3hObQkgNxNgwZUiKT4egw&s',
        'alergenos': ['lacteos', 'gluten'],
    },
    {
        'nombre': 'Sándwich de Carne',
        'descripcion': 'Carne asada, queso fundido y ensalada en pan casero. Alérgenos: gluten, lácteos.',
        'precio': 10490,
        'categoria': 'carnes',
        'badge': 'Clásico',
        'imagen': 'https://gourmet.iprospect.cl/wp-content/uploads/2024/06/MECHADA.png',
        'alergenos': ['gluten', 'lacteos'],
    },
    {
        'nombre': 'Completo Italiano',
        'descripcion': 'Pan con mayonesa y palta, tomate. Alérgenos: gluten, lácteos.',
        'precio': 2000,
        'categoria': 'carnes',
        'badge': 'Clásico',
        'imagen': 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQF4pea9DYiAhEI8gjEQHprLAPqWzGu5Br2wA&s',
        'alergenos': ['gluten', 'lacteos'],
    },
    {
        'nombre': 'Limonada Natural',
        'descripcion': 'Limonada preparada con ingredientes frescos y aroma de hierbas. Alérgenos: ninguno.',
        'precio': 2990,
        'categoria': 'bebidas',
        'badge': 'Refrescante',
        'imagen': 'https://imag.bonviveur.com/limonada.jpg',
        'alergenos': [],
    },
    {
        'nombre': 'Jugo Natural Cítrico',
        'descripcion': 'Jugo fresco de naranja, limón y pomelo sin azúcar añadida. Alérgenos: ninguno.',
        'precio': 2990,
        'categoria': 'vegano',
        'badge': 'Refrescante',
        'imagen': 'https://imag.bonviveur.com/limonada.jpg',
        'alergenos': [],
    },
]


def poblar_carta(apps, schema_editor):
    """Carga la carta inicial.

    Usa get_or_create para poder correr dos veces sin duplicar: las
    migraciones de datos no siempre corren una sola vez en la vida del
    proyecto (un --fake o un rewind las puede volver a disparar).
    """
    Alergeno = apps.get_model('menu', 'Alergeno')
    Item = apps.get_model('menu', 'Item')

    catalogo = {}
    for nombre, slug in ALERGENOS:
        alergeno, _ = Alergeno.objects.get_or_create(slug=slug, defaults={'nombre': nombre})
        catalogo[slug] = alergeno

    for plato in PLATOS:
        datos = {clave: valor for clave, valor in plato.items() if clave != 'alergenos'}
        item, _ = Item.objects.get_or_create(nombre=datos['nombre'], defaults=datos)
        item.alergenos.set([catalogo[slug] for slug in plato['alergenos']])


def vaciar_carta(apps, schema_editor):
    """Revierte la carga: deja la carta como estaba antes de esta migracion."""
    Item = apps.get_model('menu', 'Item')
    Alergeno = apps.get_model('menu', 'Alergeno')
    Item.objects.all().delete()
    Alergeno.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('menu', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(poblar_carta, vaciar_carta),
    ]
