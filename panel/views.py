from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from booking.models import Mesa, Reserva
from booking.salon import ATENDIDA, mapa_del_salon, opciones_del_invitado, reserva_en_curso
from menu.models import Item
from orders.models import Orden

from .decorators import mesero_required

# Clase visual que no es un estado del salon: una cuenta abierta por otro
# mesero. Vive aqui y no en salon.py porque depende de quien mira, y el
# salon no sabe quien mira.
AJENA = 'ajena'


TABS_DEL_PANEL = ('inicio', 'reservar', 'historial', 'perfil')


@login_required
def perfil_view(request):
    """Panel del cliente: una sola URL y el tab viaja como parametro.

    ?tab=inicio|reservar|historial|perfil. En vez de una URL por seccion,
    el servidor entrega unicamente los datos de la seccion pedida: el
    template decide que mostrar, la vista decide que consultar.
    """
    tab = request.GET.get('tab', 'inicio')
    if tab not in TABS_DEL_PANEL:
        tab = 'inicio'

    if request.method == 'POST' and tab == 'perfil':
        nombre = request.POST.get('nombre', '').strip()
        telefono = request.POST.get('telefono', '').strip()
        # El correo no se toca: es el username con el que se hace login.
        request.user.first_name = nombre
        request.user.telefono = telefono
        request.user.save(update_fields=['first_name', 'telefono'])
        messages.success(request, 'Datos actualizados.')
        return redirect(f"{reverse('perfil')}?tab=perfil")

    hoy = timezone.localdate()
    contexto = {'tab': tab}

    if tab == 'inicio':
        contexto['proximas_reservas'] = (
            request.user.reservas
            .filter(estado=Reserva.ESTADO_CONFIRMADO, fecha__gte=hoy)
            .select_related('mesa')
            .order_by('fecha', 'hora_inicio')
        )
    elif tab == 'reservar':
        contexto['mesas'] = Mesa.objects.filter(activa=True).order_by('numero')
    elif tab == 'historial':
        contexto['historial'] = (
            request.user.reservas
            .filter(
                Q(estado=Reserva.ESTADO_CANCELADO)
                | Q(estado=Reserva.ESTADO_CONFIRMADO, fecha__lt=hoy)
            )
            .select_related('mesa')
            .order_by('-fecha', '-hora_inicio')
        )

    return render(request, 'dashboard_cliente.html', contexto)


# ==================== PANEL DEL MESERO ====================
# El estado de una mesa nunca se guarda: lo calcula booking/salon.py a
# partir del reloj, la reserva del dia y la orden abierta. Estas vistas
# solo pintan ese calculo o disparan las acciones que lo cambian.


def _mapa_del_mesero(usuario, momento):
    """El mapa del salon con la clase visual ya resuelta para este mesero.

    El estado que devuelve salon.py dice 'atendida' para cualquier cuenta
    abierta. Lo que cambia segun quien mira es si esa cuenta se puede
    operar o solo mirar, y eso es lo que decide la clase de la tarjeta.

    Cada entrada viaja ademas con sus opciones de invitado: el mesero las
    necesita para el drawer de una mesa libre, y se calculan aqui una sola
    vez para todo el salon en vez de una consulta por mesa.
    """
    mapa = mapa_del_salon(momento)
    for entrada in mapa:
        entrada['clase'] = _clase_visual(entrada, usuario)
        entrada['invitado'] = opciones_del_invitado(entrada, momento)
    return mapa


def _clase_visual(entrada, usuario):
    """Clase CSS de la tarjeta: el estado, salvo la cuenta ajena.

    Una mesa atendida por otro mesero comparte el estado 'atendida' con la
    propia, pero el mesero necesita distinguirlas de un vistazo: sobre una
    puede operar y sobre la otra no.
    """
    if entrada['estado'] != ATENDIDA:
        return entrada['estado']
    if entrada['orden'].mesero_id == usuario.pk:
        return ATENDIDA
    return AJENA


@mesero_required
def mesero_view(request):
    """Panel del mesero: el salon en vivo.

    La carta viaja embebida en la pagina porque no cambia durante el
    turno: el mesero no necesita pedirla en cada ciclo de polling.
    """
    momento = timezone.localtime()
    return render(request, 'dashboard_mesero.html', {
        'mapa': _mapa_del_mesero(request.user, momento),
        'momento': momento,
        'items': [
            {
                'id': str(item.pk),
                'nombre': item.nombre,
                'precio': item.precio,
                'categoria': item.get_categoria_display(),
            }
            for item in Item.objects.filter(disponible=True).order_by('categoria', 'nombre')
        ],
    })


@mesero_required
@require_GET
def mesas_estado(request):
    """El salon en vivo en JSON, para el polling del mapa.

    El mesero deja la pagina abierta todo el turno: el reloj avanza y las
    reservas entran y salen sin que el navegador se entere. Este endpoint
    es lo que mantiene el mapa honesto.
    """
    momento = timezone.localtime()
    return JsonResponse({
        'momento': momento.strftime('%H:%M'),
        'mesas': [
            _mesa_a_json(entrada, request.user)
            for entrada in _mapa_del_mesero(request.user, momento)
        ],
    })


@mesero_required
@require_POST
def tomar_mesa(request):
    """El mesero abre la cuenta de una mesa que tiene clientes ahora.

    La mesa no se marca en ninguna parte: la orden es la marca. Si dos
    meseros pulsan al mismo tiempo, el segundo choca contra la validacion
    de Orden.tomar() y el polling le corrige el mapa en el proximo ciclo.
    """
    try:
        mesa = Mesa.objects.get(numero=request.POST.get('mesa'), activa=True)
    except (Mesa.DoesNotExist, ValidationError, ValueError, TypeError):
        return JsonResponse({'error': 'Esa mesa no existe.'}, status=400)

    momento = timezone.localtime()
    reserva = reserva_en_curso(mesa, momento)
    if reserva is None:
        return JsonResponse({'error': 'Esa mesa no tiene clientes en este momento.'}, status=409)

    try:
        orden = Orden.tomar(reserva, request.user, momento)
    except ValueError as error:
        return JsonResponse({'error': str(error)}, status=409)

    return _json_orden(orden)


@mesero_required
@require_POST
def sentar_invitado(request):
    """El mesero sienta a un invitado: reserva sin cliente y cuenta abierta.

    Un solo paso porque es un solo hecho: los invitados ya estan sentados y
    alguien tiene que atenderlos. El rango no lo decide el navegador: el
    modelo recalcula el bloque en curso y el tope contra la BD, porque el
    mapa que el mesero esta mirando puede tener hasta 10 segundos de atraso.

    Si la cuenta no se puede abrir despues de crear la reserva, la reserva
    se deshace: Mongo aqui no da transacciones, asi que la compensacion es
    explicita en vez de silenciosa.
    """
    try:
        mesa = Mesa.objects.get(numero=request.POST.get('mesa'), activa=True)
        hora_fin = datetime.strptime(request.POST.get('hora_fin', ''), '%H:%M').time()
    except (Mesa.DoesNotExist, ValidationError, ValueError, TypeError):
        return JsonResponse({'error': 'Esa mesa o ese horario no son validos.'}, status=400)

    momento = timezone.localtime()
    try:
        reserva = Reserva.sentar_invitado(mesa, request.user, momento, hora_fin)
    except ValueError as error:
        return JsonResponse({'error': str(error)}, status=409)

    try:
        orden = Orden.tomar(reserva, request.user, momento)
    except ValueError as error:
        reserva.cancelar()
        return JsonResponse({'error': str(error)}, status=409)

    return _json_orden(orden)


@mesero_required
@require_POST
def cancelar_invitado(request):
    """Libera una mesa de invitado que nadie llego a atender.

    Solo invitados: la reserva de un cliente se cancela desde su cuenta o
    desde administracion. La mesa es del salon, no del mesero que la sento,
    asi que cualquier mesero puede liberarla; lo que no puede es hacerlo con
    una cuenta abierta encima, y esa regla la impone Reserva.cancelar().
    """
    try:
        mesa = Mesa.objects.get(numero=request.POST.get('mesa'), activa=True)
    except (Mesa.DoesNotExist, ValidationError, ValueError, TypeError):
        return JsonResponse({'error': 'Esa mesa no existe.'}, status=400)

    momento = timezone.localtime()
    reserva = reserva_en_curso(mesa, momento)
    if reserva is None or not reserva.es_invitado:
        return JsonResponse({'error': 'Esa mesa no tiene una reserva de invitado en curso.'}, status=409)

    try:
        reserva.cancelar()
    except ValueError as error:
        return JsonResponse({'error': str(error)}, status=409)

    return JsonResponse({'mesa': mesa.numero, 'cancelada': str(reserva.pk)})


@mesero_required
@require_POST
def orden_agregar(request):
    """Suma un plato a una cuenta abierta del propio mesero."""
    orden, error = _cuenta_del_mesero(request)
    if error is not None:
        return error

    try:
        item = Item.objects.get(pk=request.POST.get('item'), disponible=True)
    except (Item.DoesNotExist, ValidationError, ValueError, TypeError):
        return JsonResponse({'error': 'Ese plato no esta en la carta.'}, status=400)

    try:
        orden.agregar_item(item, _cantidad_pedida(request))
    except ValueError as error_orden:
        return JsonResponse({'error': str(error_orden)}, status=409)

    return _json_orden(orden)


@mesero_required
@require_POST
def orden_quitar(request):
    """Baja la cantidad de un plato de una cuenta abierta del propio mesero."""
    orden, error = _cuenta_del_mesero(request)
    if error is not None:
        return error

    try:
        item = Item.objects.get(pk=request.POST.get('item'))
    except (Item.DoesNotExist, ValidationError, ValueError, TypeError):
        return JsonResponse({'error': 'Ese plato no existe.'}, status=400)

    try:
        orden.quitar_item(item, _cantidad_pedida(request))
    except ValueError as error_orden:
        return JsonResponse({'error': str(error_orden)}, status=409)

    return _json_orden(orden)


@mesero_required
@require_POST
def orden_cerrar(request):
    """Cierra la cuenta: la mesa deja de estar atendida y el mapa la apaga."""
    orden, error = _cuenta_del_mesero(request)
    if error is not None:
        return error

    try:
        orden.cerrar()
    except ValueError as error_orden:
        return JsonResponse({'error': str(error_orden)}, status=409)

    return _json_orden(orden)


def _cuenta_del_mesero(request):
    """La orden que el mesero quiere tocar, o la respuesta de error lista.

    Un mesero solo toca sus propias cuentas: si otro la tiene abierta, no
    es su mesa aunque la vea en el mapa.
    """
    try:
        orden = Orden.objects.get(pk=request.POST.get('orden'))
    except (Orden.DoesNotExist, ValidationError, ValueError, TypeError):
        return None, JsonResponse({'error': 'Esa cuenta no existe.'}, status=400)

    if orden.mesero_id != request.user.pk:
        return None, JsonResponse({'error': 'Esa cuenta la lleva otro mesero.'}, status=403)

    if not orden.esta_abierta:
        return None, JsonResponse({'error': 'Esa cuenta ya esta cerrada.'}, status=409)

    return orden, None


def _cantidad_pedida(request):
    """Cantidad del POST; 1 si viene vacia o no es un entero."""
    try:
        return max(1, int(request.POST.get('cantidad', 1)))
    except (TypeError, ValueError):
        return 1


def _lineas_a_json(orden):
    """Las lineas de una cuenta, listas para pintar el drawer."""
    return [
        {
            'item': str(linea.item_id),
            'nombre': linea.item.nombre,
            'cantidad': linea.cantidad,
            'precio_unitario': linea.precio_unitario,
            'subtotal': linea.subtotal,
        }
        for linea in orden.lineas.all()
    ]


def _json_orden(orden):
    """La cuenta completa, para que el drawer se repinte sin recargar."""
    return JsonResponse({
        'orden': str(orden.pk),
        'mesa': orden.reserva.mesa.numero,
        'total': orden.total,
        'abierta': orden.esta_abierta,
        'lineas': _lineas_a_json(orden),
    })


def _mesa_a_json(entrada, usuario):
    """Serializa una entrada del mapa para el navegador.

    No expone la reserva entera: el mesero necesita saber a que hora y de
    quien es la mesa, no el historial del cliente.

    Las lineas viajan tambien en las cuentas ajenas, para que el mesero
    vea que se pidio en la mesa. Ver no es tocar: agregar, quitar y cerrar
    sobre una cuenta ajena siguen rechazandose con 403 en el servidor, que
    es donde vive la proteccion de verdad.
    """
    mesa = entrada['mesa']
    reserva = entrada['reserva']
    orden = entrada['orden']
    proxima = entrada['proxima']
    invitado = entrada['invitado']
    es_mia = orden is not None and orden.mesero_id == usuario.pk

    return {
        'numero': mesa.numero,
        'capacidad': mesa.capacidad,
        'ubicacion': mesa.ubicacion,
        'es_grande': mesa.es_grande,
        'estado': entrada['estado'],
        'clase': entrada['clase'],
        'etiqueta': entrada['etiqueta'],
        'reserva': None if reserva is None else {
            'hora_inicio': reserva.hora_inicio.strftime('%H:%M'),
            'hora_fin': reserva.hora_fin.strftime('%H:%M'),
            'cliente': reserva.nombre_cliente,
            'es_invitado': reserva.es_invitado,
        },
        # El proximo compromiso de la mesa: el mesero lo necesita a la vista
        # para saber cuando tiene que rotar la mesa, aunque pueda sentar a
        # alguien ahora.
        'proxima_reserva': None if proxima is None else {
            'hora_inicio': proxima.hora_inicio.strftime('%H:%M'),
            'hora_fin': proxima.hora_fin.strftime('%H:%M'),
            'cliente': proxima.nombre_cliente,
        },
        # El mesero no calcula el rango: el servidor le dice desde cuando,
        # hasta que fines de bloque y, si no se puede, por que. El JS pinta.
        'invitado': {
            'inicio': None if invitado['inicio'] is None else invitado['inicio'].strftime('%H:%M'),
            'fines': [fin.strftime('%H:%M') for fin in invitado['fines']],
            'motivo': invitado['motivo'],
        },
        'orden': None if orden is None else {
            'id': str(orden.pk),
            'total': orden.total,
            'es_mia': es_mia,
            'mesero': orden.mesero.first_name or orden.mesero.username,
            'lineas': _lineas_a_json(orden),
        },
    }
