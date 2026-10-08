"""Horario de atencion del restaurante: la unica fuente de verdad.

Reglas del negocio (reflejadas en el pie de pagina del sitio):
- Lunes a viernes: 08:00 - 16:00
- Sabado:          09:00 - 15:00
- Domingo:         cerrado

Las reservas se hacen por bloques de exactamente 1 hora dentro de ese
rango: un bloque es (hora_inicio, hora_inicio + 1h).
"""

from datetime import datetime, time, timedelta

DURACION_BLOQUE = timedelta(hours=1)

# Politica operativa, no invariante: un invitado que se sienta con menos de
# una hora por delante no alcanza a comer antes del proximo compromiso de la
# mesa. El invariante duro (nunca solapar) lo impone el tope de la proxima
# reserva; esto es solo el piso que hace util sentar a alguien.
MINUTOS_MINIMOS_INVITADO = 60
MINIMO_INVITADO = timedelta(minutes=MINUTOS_MINIMOS_INVITADO)

# Indices de date.weekday(): lunes = 0 ... domingo = 6
ABRE_SEMANA = time(8, 0)
CIERRA_SEMANA = time(16, 0)
ABRE_SABADO = time(9, 0)
CIERRA_SABADO = time(15, 0)

DOMINGO = 6


def rango_atencion(fecha):
    """Devuelve (hora_apertura, hora_cierre) de una fecha, o None si cerrado."""
    if fecha.weekday() == DOMINGO:
        return None
    if fecha.weekday() == 5:  # sabado
        return ABRE_SABADO, CIERRA_SABADO
    return ABRE_SEMANA, CIERRA_SEMANA


def bloques_del_dia(fecha):
    """Bloques de 1 hora (inicio, fin) en que el restaurante atiende esa fecha.

    Una lista vacia significa que el restaurante esta cerrado.
    """
    rango = rango_atencion(fecha)
    if rango is None:
        return []

    apertura, cierre = rango
    bloques = []
    inicio = datetime.combine(fecha, apertura)
    cierre_dt = datetime.combine(fecha, cierre)

    while inicio + DURACION_BLOQUE <= cierre_dt:
        bloques.append((inicio.time(), (inicio + DURACION_BLOQUE).time()))
        inicio += DURACION_BLOQUE

    return bloques


def bloque_en_curso(fecha, momento):
    """El bloque que contiene ese instante en esa fecha, o None si no hay.

    Es el bloque del invitado: a las 13:20 el bloque en curso es 13:00-14:00,
    y la reserva se crea empezando ahi. Si solo se ofrecieran bloques
    futuros, el mesero no podria abrir la cuenta hasta la hora siguiente,
    porque Orden.tomar() exige que la reserva cubra el instante actual.
    """
    for inicio, fin in bloques_del_dia(fecha):
        if inicio <= momento.time() < fin:
            return inicio, fin
    return None


def rango_de_bloques(fecha, hora_inicio, hora_fin):
    """Si el rango empieza donde empieza un bloque y termina donde termina otro.

    Un rango valido cubre bloques completos: (10:00-12:00) cubre dos;
    (10:00-11:00) cubre uno. Como el horario es continuo (sin recesos),
    alinear ambos extremos a los bloques del dia garantiza que no hay
    huecos internos. hora_fin > hora_inicio lo valida el clean() del modelo.

    Vive aqui, y no en el formulario, porque el alta del cliente y la del
    invitado del mesero tienen que responder a la misma regla.
    """
    bloques = bloques_del_dia(fecha)
    inicios = {inicio for inicio, _ in bloques}
    fines = {fin for _, fin in bloques}
    return hora_inicio in inicios and hora_fin in fines


def opciones_de_invitado(momento, tope):
    """El rango de bloques que un invitado puede ocupar hoy en una mesa.

    `momento` es el instante en que el mesero quiere sentarlo y `tope` la
    hora en que empieza el proximo compromiso de la mesa (o None si no hay
    ninguno mas hoy): ese tope es el invariante duro, el invitado nunca lo
    cruza.

    Devuelve:
        {'cerrado': bool,        el restaurante no tiene servicio delante
         'inicio': time|None,    bloque en curso, o el proximo si aun no abre
         'fines': [time, ...],   fines de bloque alcanzables antes del tope
         'hueco': timedelta|None, servicio que queda por delante
         'suficiente': bool}     el hueco llega a MINUTOS_MINIMOS_INVITADO
    """
    fecha = momento.date()
    bloques = bloques_del_dia(fecha)
    en_curso = bloque_en_curso(fecha, momento)

    if en_curso is not None:
        inicio = en_curso[0]
    else:
        # Fuera de bloque: si el servicio aun no abre, el proximo bloque;
        # si ya cerro, no queda nada por delante.
        proximos = [bloque_inicio for bloque_inicio, _ in bloques if bloque_inicio > momento.time()]
        inicio = proximos[0] if proximos else None

    if inicio is None:
        return {'cerrado': True, 'inicio': None, 'fines': [], 'hueco': None, 'suficiente': False}

    fines = [fin for _, fin in bloques if fin > inicio]
    if tope is not None:
        fines = [fin for fin in fines if fin <= tope]

    if not fines:
        return {'cerrado': True, 'inicio': None, 'fines': [], 'hueco': None, 'suficiente': False}

    # El hueco se mide desde ahora, no desde el inicio del bloque: a las
    # 13:50, con un compromiso a las 14:00, quedan una hora de rango
    # declarado pero diez minutos reales, y esos diez minutos no alcanzan.
    hueco = datetime.combine(fecha, fines[-1]) - datetime.combine(fecha, momento.time())
    return {
        'cerrado': False,
        'inicio': inicio,
        'fines': fines,
        'hueco': hueco,
        'suficiente': hueco >= MINIMO_INVITADO,
    }


def motivo_de_invitado(opciones, tope):
    """Por que no se puede sentar un invitado, o None si si se puede.

    El texto lo comparten el modelo (que lo lanza como ValueError) y la
    vista (que lo manda al drawer del mesero): el mesero lee lo mismo sin
    importar por donde entro la negativa.

    `tope` es la hora del proximo compromiso de la mesa, o None si no hay
    ninguno mas hoy: en ese caso el limite es el cierre del local.
    """
    if opciones['cerrado']:
        return 'El restaurante no tiene servicio en este momento.'

    if not opciones['suficiente']:
        if tope is None:
            return 'Queda menos de una hora para el cierre: no alcanza para sentar a nadie.'
        return (
            f'Esta mesa tiene una reserva a las {tope:%H:%M}: '
            'queda menos de una hora de servicio.'
        )

    return None
