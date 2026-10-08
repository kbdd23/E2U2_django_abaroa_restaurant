from django.db import models


class Alergeno(models.Model):
    """Catalogo de alergenos. Es la fuente de los tags que el frontend filtra.

    Existe como modelo y no como lista fija porque la relacion es N:M: un
    plato tiene varios alergenos y un alergeno aplica a varios platos. El
    slug es el valor que viaja al HTML (data-alergeno="gluten"); el nombre
    es lo que se muestra en pantalla.
    """

    nombre = models.CharField(max_length=30, unique=True)
    slug = models.SlugField(max_length=30, unique=True)

    class Meta:
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class Item(models.Model):
    """Un plato de la carta. Es catalogo: describe lo que se puede vender.

    No sabe nada de mesas ni de ordenes. Cualquier vista lo consulta igual,
    sea del cliente o del mesero: Item.objects.filter(disponible=True).
    Quien decide que se hace con un Item es la orden, y esa vive en orders.
    """

    class Categoria(models.TextChoices):
        CARNES = 'carnes', 'Carnes'
        VEGANO = 'vegano', 'Vegano'
        BEBIDAS = 'bebidas', 'Bebidas'

    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True)
    precio = models.PositiveIntegerField()  # pesos chilenos: entero, sin centavos
    categoria = models.CharField(max_length=20, choices=Categoria.choices, default=Categoria.CARNES)
    badge = models.CharField(max_length=30, blank=True)  # "Clasico", "Favorito", ...
    imagen = models.URLField(max_length=500, blank=True)
    alergenos = models.ManyToManyField(Alergeno, blank=True, related_name='items')
    disponible = models.BooleanField(default=True)  # soft delete, igual que Mesa.activa
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['categoria', 'nombre']

    def __str__(self):
        return f"{self.nombre} (${self.precio})"

    @classmethod
    def crear_item(cls, nombre, precio, categoria, descripcion='', badge='', imagen='', alergenos=None):
        """Alta controlada de un plato de la carta.

        Los alergenos se asignan despues del create: un M2M no acepta
        valores en el constructor, necesita que la fila exista primero
        para tener los dos extremos que unir.
        """
        item = cls.objects.create(
            nombre=nombre,
            precio=precio,
            categoria=categoria,
            descripcion=descripcion,
            badge=badge,
            imagen=imagen,
        )
        if alergenos:
            item.alergenos.set(alergenos)
        return item

    def retirar(self):
        """Soft delete: el plato sale de la carta pero su historia vive."""
        self.disponible = False
        self.save(update_fields=['disponible'])

    def reactivar(self):
        """Devuelve el plato a la carta."""
        self.disponible = True
        self.save(update_fields=['disponible'])

    @property
    def precio_formateado(self):
        """Precio en formato chileno: $12.990.

        El separador de miles chileno es el punto. f"{precio:,}" usa la
        convencion inglesa (12,990), asi que se intercambia.
        """
        return f"${self.precio:,}".replace(',', '.')
