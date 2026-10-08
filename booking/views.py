from datetime import datetime

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from panel.decorators import cliente_required

from .forms import ReservaForm
from .horario import bloques_del_dia
from .models import Mesa, Reserva


@cliente_required
def crear_reserva(request):
    """Alta de reserva: reserva de cliente, la hace un cliente.

    El portero de rol frena al mesero antes de tocar el modelo: su via para
    ocupar una mesa es sentar_invitado, donde el invitado no lleva cuenta.

    El cliente nunca viene del navegador: el servidor se lo pasa al
    formulario, que lo deja puesto en la instancia antes de que el modelo
    valide. El formulario valida formato, rango y solapamiento.
    """
    if request.method == 'POST':
        form = ReservaForm(request.POST, cliente=request.user)
        if form.is_valid():
            reserva = form.save()
            messages.success(
                request,
                f'Reserva confirmada: Mesa {reserva.mesa.numero} el '
                f'{reserva.fecha} de {reserva.hora_inicio} a {reserva.hora_fin}.',
            )
            return redirect('booking:crear_reserva')
    else:
        form = ReservaForm()

    # El salon vivo: las mesas del modelo, no un HTML hardcodeado.
    mesas = Mesa.objects.filter(activa=True).order_by('numero')

    # related_name='reservas' del FK cliente -> request.user.reservas
    reservas_usuario = request.user.reservas.order_by('-fecha', '-hora_inicio')

    return render(
        request,
        'reserva_form.html',
        {'form': form, 'mesas': mesas, 'reservas_usuario': reservas_usuario},
    )


@cliente_required
@require_GET
def bloques_disponibles(request):
    """Disponibilidad de una mesa para una fecha, en bloques de 1 hora.

    Es la pregunta que el navegador hace ANTES de mostrar el formulario:
    GET /reservar/bloques/?mesa=<pk>&fecha=YYYY-MM-DD
    Devuelve cada bloque del horario con su estado libre/ocupado, calculado
    contra las reservas confirmadas en la BD (Reserva.solapamiento).
    """
    try:
        mesa = Mesa.objects.get(pk=request.GET.get('mesa'), activa=True)
        fecha = datetime.strptime(request.GET.get('fecha'), '%Y-%m-%d').date()
    except (Mesa.DoesNotExist, ValueError, TypeError):
        return JsonResponse({'error': 'Mesa o fecha invalidas.'}, status=400)

    hoy = timezone.localdate()
    if fecha < hoy:
        return JsonResponse({'error': 'La fecha ya paso.'}, status=400)

    bloques = bloques_del_dia(fecha)
    if not bloques:
        return JsonResponse({'error': 'El restaurante esta cerrado ese dia.'}, status=400)

    # De hoy en adelante solo se ofrecen bloques que aun no comienzan.
    if fecha == hoy:
        ahora = timezone.localtime().time()
        bloques = [(inicio, fin) for inicio, fin in bloques if inicio > ahora]

    respuesta = []
    for inicio, fin in bloques:
        ocupado = Reserva.solapamiento(mesa, fecha, inicio, fin).exists()
        respuesta.append({
            'inicio': inicio.strftime('%H:%M'),
            'fin': fin.strftime('%H:%M'),
            'libre': not ocupado,
        })

    return JsonResponse({
        'mesa': mesa.numero,
        'fecha': fecha.isoformat(),
        'bloques': respuesta,
    })


@cliente_required
@require_POST
def cancelar_reserva(request, pk):
    """Cancela una reserva propia del cliente.

    La regla de cuenta abierta vive en Reserva.cancelar(): si la mesa ya
    tiene una orden abierta, el cliente esta presente y no puede cancelar.
    """
    reserva = get_object_or_404(Reserva, pk=pk, cliente=request.user)
    try:
        reserva.cancelar()
    except ValueError as error:
        messages.error(request, str(error))
    else:
        messages.success(request, 'Reserva cancelada.')
    return redirect('perfil')
