from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from .horario import motivo_de_invitado, opciones_de_invitado


class SalonConfig(models.Model):
    """Configuracion del salon: cuantas mesas caben (el 'Y' del contador).

    Es un singleton: siempre existe un unico registro. Redimensionar cambia
    `capacidad`; no borra mesas, solo ajusta el tamano declarado. Bajar la
    capacidad por debajo de las mesas activas se rechaza en la vista.
    """

    capacidad = models.PositiveSmallIntegerField(default=8)

    @classmethod
    def actual(cls):
        config = cls.objects.first()
        if config is None:
            config = cls.objects.create(capacidad=8)
        return config


class Mesa(models.Model):
    numero = models.PositiveSmallIntegerField(unique=True) #pk
    capacidad = models.PositiveSmallIntegerField() #4, 8, 10, 12
    ubicacion = models.CharField(max_length=50) #terraza, barra, ventana, etc
    es_grande = models.BooleanField(default=False)
    activa = models.BooleanField(default=True) # Soft delete: retirar() la saca del salon sin perder su historia. borrar() solo aplica si no tiene reservas.

    def __str__(self):
        return f"Mesa :{self.numero}"

    @classmethod
    def crear_mesa(cls, numero, capacidad, ubicacion, es_grande=False):
        """Alta controlada de una mesa en el salon."""
        return cls.objects.create(
            numero=numero,
            capacidad=capacidad,
            ubicacion=ubicacion,
            es_grande=es_grande,
        )

    @classmethod
    def siguiente_numero(cls):
        """El proximo numero de mesa libre: max(numero) + 1.

        El numero se auto-asigna para que crear una mesa nunca colisione con
        una retirada que siga existiendo.
        """
        ultima = cls.objects.order_by('-numero').first()
        return (ultima.numero + 1) if ultima else 1

    def reservas_pendientes(self):
        """Cuantas reservas confirmadas le quedan por delante a esta mesa."""
        return Reserva.pendientes(mesa=self).count()

    def retirar(self):
        """Soft delete: la mesa sale del salon pero su historia vive.

        No sale si tiene reservas pendientes: esas reservas quedarian
        apuntando a una mesa que ya no esta en el salon.
        """
        if self.reservas_pendientes():
            raise ValueError('No se puede retirar: la mesa tiene reservas pendientes.')
        self.activa = False
        self.save(update_fields=['activa'])

    def reactivar(self):
        """Devuelve la mesa al salon."""
        self.activa = True
        self.save(update_fields=['activa'])

    def editar_ubicacion(self, nueva_ubicacion):
        """Edición de la 'ubicación' de una mesa, esto sirve para poder 'orientar' donde está cada mesa
        ejemplo: primer piso-ventana, o ventanal, o editar las mismas mesas inicializadas. (Se crean 8 mesas por defecto al iniciar el proyecto)"""
        self.ubicacion = nueva_ubicacion
        self.save(update_fields=['ubicacion'])

    def borrar(self):
        """Hard delete: solo si la mesa no tiene reservas.

        Es la unica excepcion al soft delete. Una mesa con historia (reservas
        PROTECT) no se borra: sus reservas apuntan a ella.
        """
        if self.reservas.exists():
            raise ValueError('No se puede borrar: la mesa tiene reservas.')
        self.delete()


class Reserva(models.Model):
    ESTADO_CONFIRMADO = 'confirmado'
    ESTADO_CANCELADO = 'cancelado'

    ESTADOS = [
        (ESTADO_CONFIRMADO, 'Confirmado'),
        (ESTADO_CANCELADO, 'Cancelado'),
    ]

    # Nullable: un invitado no tiene cuenta. La reserva sin cliente es la
    # reserva de walk-in que abre el mesero, y creada_por dice quien la
    # sento. Las reservas de cliente siguen naciendo desde el navegador con
    # el usuario de la sesion; creada_por queda vacio y no significa nada.
    cliente = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='reservas', null=True, blank=True,
    )
    creada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='reservas_creadas', null=True, blank=True,
    )
    mesa = models.ForeignKey(Mesa, on_delete=models.PROTECT, related_name='reservas')
    fecha = models.DateField()
    hora_inicio = models.TimeField()  # Bloque desde las 14:00
    hora_fin = models.TimeField()     # Bloque hasta las 15:00
    estado = models.CharField(max_length=20, choices=ESTADOS, default=ESTADO_CONFIRMADO)
    creada_en = models.DateTimeField(auto_now_add=True)  # Trigger -> now()

    def __str__(self):
        return f"Reserva de: {self.nombre_cliente} | Mesa: {self.mesa.numero} | Fecha: {self.fecha} | {self.hora_inicio}--{self.hora_fin}"

    class Meta:
        ordering = ['fecha', 'hora_inicio']

    @property
    def es_invitado(self):
        """Una reserva sin cliente es de un invitado, no de un usuario.

        Se deriva y no se guarda: un booleano al lado de `cliente` seria una
        segunda verdad que puede contradecir a la primera.
        """
        return self.cliente_id is None

    @property
    def nombre_cliente(self):
        """Como se nombra al ocupante de la mesa: cliente, o 'Invitado'."""
        if self.cliente is None:
            return 'Invitado'
        return self.cliente.first_name or self.cliente.username

    def clean(self):  # clean() es un metodo de django
        super().clean()
        if self.hora_inicio and self.hora_fin and self.hora_fin <= self.hora_inicio:
            raise ValidationError({'hora_fin': 'La hora de fin debe ser posterior a la de inicio'})
        if self.es_invitado and self.creada_por_id is None:
            raise ValidationError('Una reserva de invitado debe registrar quien la sento.')

    @classmethod  # metodo para calcular el solapamiento de un bloque, evitar choques
    def solapamiento(cls, mesa, fecha, hora_inicio, hora_fin):
        """Devuelve las reservas confirmadas que chocan con ese bloque."""
        return cls.objects.filter(
            mesa=mesa,
            fecha=fecha,
            estado=cls.ESTADO_CONFIRMADO,
            hora_inicio__lt=hora_fin,  # alguna reserva empieza antes de que yo termine
            hora_fin__gt=hora_inicio,  # alguna reserva termina despues de que yo empiece
        )

    @classmethod
    def pendientes(cls, mesa=None):
        """Reservas confirmadas que aun no han terminado.

        Una reserva pasada ya se consumio: no bloquea retirar su mesa. Solo
        cuentan las que dejan un compromiso por delante (futuras o en curso).
        """
        ahora = timezone.localtime()
        vigentes = Q(fecha__gt=ahora.date()) | Q(
            fecha=ahora.date(), hora_fin__gt=ahora.time(),
        )
        consulta = cls.objects.filter(vigentes, estado=cls.ESTADO_CONFIRMADO)
        if mesa is not None:
            consulta = consulta.filter(mesa=mesa)
        return consulta

    @classmethod
    def proxima(cls, mesa, momento):
        """La reserva confirmada de hoy que empieza despues de este instante.

        Es el tope del invitado: una mesa con un compromiso a las 14:00 solo
        puede recibir walk-in hasta las 14:00, no hasta el cierre.
        """
        return cls.objects.filter(
            mesa=mesa,
            fecha=momento.date(),
            estado=cls.ESTADO_CONFIRMADO,
            hora_inicio__gt=momento.time(),
        ).order_by('hora_inicio').first()

    @classmethod
    def proximas(cls, mesas, momento):
        """La proxima reserva de cada mesa, en una consulta para todo el salon.

        Mongo no soporta prefetch: el bucle que se queda con la primera
        reserva de cada mesa se cierra aqui, no en la vista ni en el template.
        """
        reservas = cls.objects.filter(
            mesa__in=mesas,
            fecha=momento.date(),
            estado=cls.ESTADO_CONFIRMADO,
            hora_inicio__gt=momento.time(),
        ).order_by('hora_inicio')

        proximas = {}
        for reserva in reservas:
            proximas.setdefault(reserva.mesa_id, reserva)
        return proximas

    @classmethod
    def sentar_invitado(cls, mesa, mesero, momento, hora_fin):
        """Sienta a un invitado: reserva sin cliente, creada por el mesero.

        La regla vive aca, no en la vista, por lo mismo que en el resto del
        modelo: ningun camino la puede saltar. Un invitado solo se sienta
        hoy, en el bloque en curso (el mesero lo esta sentando ahora) y con
        el fin antes del proximo compromiso de la mesa. El solapamiento se
        comprueba igual, como red de seguridad: si algo entra entre el
        calculo y el guardado, revienta en vez de duplicar la mesa.
        """
        if not mesa.activa:
            raise ValueError('Esa mesa no esta en el salon.')

        proxima = cls.proxima(mesa, momento)
        tope = proxima.hora_inicio if proxima else None
        opciones = opciones_de_invitado(momento, tope)

        motivo = motivo_de_invitado(opciones, tope)
        if motivo is not None:
            raise ValueError(motivo)

        if hora_fin not in opciones['fines']:
            raise ValueError('Elige un fin de bloque dentro del servicio de hoy.')

        inicio = opciones['inicio']
        if cls.solapamiento(mesa, momento.date(), inicio, hora_fin).exists():
            raise ValueError('Esa mesa ya tiene una reserva en ese horario.')

        return cls.objects.create(
            cliente=None,
            creada_por=mesero,
            mesa=mesa,
            fecha=momento.date(),
            hora_inicio=inicio,
            hora_fin=hora_fin,
        )

    def cancelar(self, cerrar_cuenta=False):
        """Cancela la reserva.

        Rechaza si ya no esta confirmada o si la mesa tiene una cuenta
        abierta: un cliente con consumo es un cliente presente, y su
        reserva no se cancela, se termina cuando el mesero cierra la orden.

        cerrar_cuenta rompe esa ultima regla a proposito: la usa el admin
        cuando desactiva a un cliente que se va, para cerrar su consumo
        antes de cancelar la reserva.
        """
        from orders.models import Orden  # import local: evita el ciclo booking <-> orders

        if self.estado != self.ESTADO_CONFIRMADO:
            raise ValueError('La reserva ya no esta confirmada.')

        abierta = self.ordenes.filter(estado=Orden.ESTADO_ABIERTA).first()
        if abierta is not None:
            if not cerrar_cuenta:
                raise ValueError('No se puede cancelar: la mesa tiene una cuenta abierta.')
            abierta.cerrar()

        self.estado = self.ESTADO_CANCELADO
        self.save(update_fields=['estado'])
