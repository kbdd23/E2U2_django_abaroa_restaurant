"""Estado del salon en un instante dado: la unica fuente de verdad.

El estado de una mesa no vive en ningun campo de Mesa. Se calcula, porque
tiene tres entradas que cambian solas: el reloj, la reserva del dia y la
orden abierta. Guardarlo obligaria a actualizarlo al cruzar la hora, al
cancelar una reserva y al cerrar una cuenta: tres escritores y ningun
invariante que los ate.

Cuatro consultas para todo el salon, no una por mesa. Mongo no soporta
prefetch_related, asi que el bucle se cierra aqui y no en el template.
"""

from booking.horario import motivo_de_invitado, opciones_de_invitado
from booking.models import Mesa, Reserva
from orders.models import Orden

LIBRE = 'libre'
POR_ATENDER = 'por_atender'
ATENDIDA = 'atendida'

# Traduccion unica de estado a texto visible. La usan el template y el
# JSON del polling, para que no existan dos listas de etiquetas que se
# desincronicen.
ETIQUETAS = {
    LIBRE: 'Libre',
    POR_ATENDER: 'Sin mesero',
    ATENDIDA: 'Atendida',
}


def mapa_del_salon(momento):
    """Las mesas activas con su estado en ese instante.

    Devuelve una lista de entradas con esta forma:
        {'mesa': Mesa, 'reserva': Reserva|None, 'orden': Orden|None,
         'proxima': Reserva|None, 'estado': str, 'etiqueta': str}

    Usa `lte` y no `lt` en hora_inicio: a las 10:00:00 en punto la reserva
    que empieza a las 10:00 ya esta en curso. Con `<` la mesa parpadearia
    apagada durante el primer segundo de cada bloque.
    """
    mesas = list(Mesa.objects.filter(activa=True).order_by('numero'))

    reservas = list(Reserva.objects.filter(
        fecha=momento.date(),
        estado=Reserva.ESTADO_CONFIRMADO,
        hora_inicio__lte=momento.time(),
        hora_fin__gt=momento.time(),
    ))

    ordenes_abiertas = {
        orden.reserva_id: orden
        for orden in Orden.objects.filter(
            reserva__in=reservas,
            estado=Orden.ESTADO_ABIERTA,
        )
    }
    reserva_por_mesa = {reserva.mesa_id: reserva for reserva in reservas}
    # El proximo compromiso de cada mesa: es lo que decide hasta cuando
    # puede quedarse un invitado sentado ahora.
    proximas_por_mesa = Reserva.proximas(mesas, momento)

    mapa = []
    for mesa in mesas:
        reserva = reserva_por_mesa.get(mesa.pk)
        orden = ordenes_abiertas.get(reserva.pk) if reserva else None
        estado = _estado_de(reserva, orden)
        mapa.append({
            'mesa': mesa,
            'reserva': reserva,
            'orden': orden,
            'proxima': proximas_por_mesa.get(mesa.pk),
            'estado': estado,
            'etiqueta': ETIQUETAS[estado],
        })
    return mapa


def _estado_de(reserva, orden):
    """Traduce (reserva, orden) al estado visible de la mesa."""
    if reserva is None:
        return LIBRE
    if orden is not None:
        return ATENDIDA
    return POR_ATENDER


def reserva_en_curso(mesa, momento):
    """La reserva confirmada que cubre este instante en esta mesa, o None.

    Es la misma condicion que usa mapa_del_salon() para el salon entero,
    pero para una sola mesa: la usan las acciones que necesitan saber si
    el mesero tiene derecho a sentarse en esa mesa ahora mismo.
    """
    return Reserva.objects.filter(
        mesa=mesa,
        fecha=momento.date(),
        estado=Reserva.ESTADO_CONFIRMADO,
        hora_inicio__lte=momento.time(),
        hora_fin__gt=momento.time(),
    ).first()


def opciones_del_invitado(entrada, momento):
    """Que puede ofrecerle el mesero a un invitado en esta mesa, ahora mismo.

    El tope del rango es la proxima reserva de la mesa: con un compromiso a
    las 14:00, el invitado se sienta hasta las 14:00 y ni un minuto mas.

    Devuelve las opciones de horario mas 'motivo': el texto que explica la
    negativa, o None si el mesero puede sentar a alguien.
    """
    proxima = entrada['proxima']
    tope = proxima.hora_inicio if proxima else None
    opciones = opciones_de_invitado(momento, tope)
    opciones['motivo'] = motivo_de_invitado(opciones, tope)
    return opciones
