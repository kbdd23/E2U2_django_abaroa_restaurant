from django.conf import settings
from django.db import models
from django.utils import timezone

from booking.models import Reserva
from menu.models import Item


class Orden(models.Model):
    """La cuenta que un mesero abre sobre una reserva en curso.

    Cruza las tres piezas del sistema: la reserva (quien esta en la mesa y
    hasta cuando), el mesero (quien la atiende) y los items del menu (que
    se consumio). La orden no guarda el estado de la mesa: el estado de la
    mesa se deriva de si existe una orden abierta aqui.
    """

    ESTADO_ABIERTA = 'abierta'
    ESTADO_CERRADA = 'cerrada'

    ESTADOS = [
        (ESTADO_ABIERTA, 'Abierta'),
        (ESTADO_CERRADA, 'Cerrada'),
    ]

    # PROTECT y no CASCADE: una cuenta con consumo no se puede borrar por
    # debajo. La reserva y el mesero sobreviven a la orden, y la orden
    # sobrevive a ellos.
    reserva = models.ForeignKey(Reserva, on_delete=models.PROTECT, related_name='ordenes')
    mesero = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='ordenes')
    estado = models.CharField(max_length=20, choices=ESTADOS, default=ESTADO_ABIERTA)
    abierta_en = models.DateTimeField(auto_now_add=True)
    cerrada_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-abierta_en']

    def __str__(self):
        return f"Orden de {self.mesero} | Mesa {self.reserva.mesa.numero} | {self.estado}"

    @property
    def esta_abierta(self):
        return self.estado == self.ESTADO_ABIERTA

    @property
    def total(self):
        """Suma de los subtotales, calculada al vuelo.

        No se guarda: si se quita una linea o cambia un precio, un total
        almacenado mentiria. Es la misma regla que el estado de la mesa,
        el derivado no se guarda.
        """
        return sum(linea.subtotal for linea in self.lineas.all())

    @classmethod
    def tomar(cls, reserva, mesero, momento=None):
        """Abre la cuenta de una reserva que esta en curso ahora mismo.

        Fail-closed: si ya hay una orden abierta para esa reserva revienta
        en vez de crear una segunda. En Mongo no existe constraint que lo
        impida, asi que esta comprobacion ES la regla, no un adorno.
        """
        momento = momento or timezone.localtime()
        cls._validar_reserva_en_curso(reserva, momento)

        if cls.objects.filter(reserva=reserva, estado=cls.ESTADO_ABIERTA).exists():
            raise ValueError('Esa mesa ya tiene una orden abierta.')

        return cls.objects.create(reserva=reserva, mesero=mesero)

    @staticmethod
    def _validar_reserva_en_curso(reserva, momento):
        """El mesero solo puede tomar una mesa con clientes sentados ahora."""
        if reserva.estado != Reserva.ESTADO_CONFIRMADO:
            raise ValueError('La reserva no esta confirmada.')

        if reserva.fecha != momento.date():
            raise ValueError('La reserva no es de hoy.')

        if not (reserva.hora_inicio <= momento.time() < reserva.hora_fin):
            raise ValueError('La reserva no esta en curso en este momento.')

    def agregar_item(self, item, cantidad=1):
        """Suma un plato a la cuenta, congelando su precio actual.

        Si el plato ya estaba en la orden sube la cantidad en vez de
        duplicar la linea. El precio se copia, no se referencia: el dia
        que el item suba de precio, esta cuenta sigue valiendo lo mismo.
        """
        if not self.esta_abierta:
            raise ValueError('No se puede agregar items a una orden cerrada.')
        if cantidad < 1:
            raise ValueError('La cantidad debe ser al menos 1.')

        linea, creada = self.lineas.get_or_create(
            item=item,
            defaults={'cantidad': cantidad, 'precio_unitario': item.precio},
        )
        if not creada:
            linea.cantidad += cantidad
            linea.save(update_fields=['cantidad'])
        return linea

    def quitar_item(self, item, cantidad=1):
        """Baja la cantidad de un plato. Si llega a cero, la linea se va."""
        if not self.esta_abierta:
            raise ValueError('No se puede quitar items de una orden cerrada.')
        if cantidad < 1:
            raise ValueError('La cantidad debe ser al menos 1.')

        linea = self.lineas.filter(item=item).first()
        if linea is None:
            raise ValueError('Ese plato no esta en la orden.')

        if cantidad >= linea.cantidad:
            linea.delete()
            return None

        linea.cantidad -= cantidad
        linea.save(update_fields=['cantidad'])
        return linea

    def cerrar(self):
        """Cierra la cuenta: la mesa deja de estar atendida."""
        if not self.esta_abierta:
            raise ValueError('La orden ya esta cerrada.')

        self.estado = self.ESTADO_CERRADA
        self.cerrada_en = timezone.now()
        self.save(update_fields=['estado', 'cerrada_en'])


class LineaOrden(models.Model):
    """Un plato dentro de una cuenta, con su precio congelado.

    precio_unitario se copia del item al momento de pedir. Sin esto, subir
    el precio de un plato reescribiria la cuenta de todas las ordenes
    historicas.
    """

    orden = models.ForeignKey(Orden, on_delete=models.CASCADE, related_name='lineas')
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name='lineas')
    cantidad = models.PositiveSmallIntegerField(default=1)
    precio_unitario = models.PositiveIntegerField()
    agregada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['agregada_en']

    def __str__(self):
        return f"{self.cantidad} x {self.item.nombre}"

    @property
    def subtotal(self):
        return self.cantidad * self.precio_unitario
