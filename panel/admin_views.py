from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from booking.models import Mesa, Reserva, SalonConfig
from menu.models import Alergeno, Item

from .decorators import admin_required
from .forms import AdminForm, AlergenoForm, ClienteForm, ItemForm, MesaForm, MeseroForm
from .models import User


@admin_required
def admin_view(request):
    """Portada del panel de administracion: resumen de cada area."""
    contexto = {
        'total_platos': Item.objects.count(),
        'platos_activos': Item.objects.filter(disponible=True).count(),
        'total_alergenos': Alergeno.objects.count(),
        'capacidad_salon': SalonConfig.actual().capacidad,
        'mesas_activas': Mesa.objects.filter(activa=True).count(),
        'total_meseros': User.objects.filter(rol=User.Rol.MESERO).count(),
        'total_admins': User.objects.filter(rol=User.Rol.ADMIN).count(),
        'total_reservas': Reserva.objects.count(),
        'reservas_confirmadas': Reserva.objects.filter(estado=Reserva.ESTADO_CONFIRMADO).count(),
    }
    return render(request, 'dashboard_admin.html', {'seccion': 'inicio', **contexto})


# ---- Platos ----

@admin_required
def admin_platos(request):
    """La carta completa: activos y retirados."""
    platos = Item.objects.all()
    return render(request, 'dashboard_admin.html', {'seccion': 'platos', 'platos': platos})


@admin_required
def admin_plato_crear(request):
    form = ItemForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Plato creado.')
        return redirect('admin_platos')
    return render(request, 'dashboard_admin.html', {
        'seccion': 'platos', 'form': form, 'modo': 'crear',
    })


@admin_required
def admin_plato_editar(request, pk):
    plato = get_object_or_404(Item, pk=pk)
    form = ItemForm(request.POST or None, instance=plato)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Plato actualizado.')
        return redirect('admin_platos')
    return render(request, 'dashboard_admin.html', {
        'seccion': 'platos', 'form': form, 'modo': 'editar', 'plato': plato,
    })


@admin_required
@require_POST
def admin_plato_retirar(request, pk):
    plato = get_object_or_404(Item, pk=pk)
    plato.retirar()
    messages.success(request, f'Plato "{plato.nombre}" retirado.')
    return redirect('admin_platos')


@admin_required
@require_POST
def admin_plato_reactivar(request, pk):
    plato = get_object_or_404(Item, pk=pk)
    plato.reactivar()
    messages.success(request, f'Plato "{plato.nombre}" reactivado.')
    return redirect('admin_platos')


# ---- Alergenos ----

@admin_required
def admin_alergenos(request):
    """Catalogo de alergenos: alta y listado en el mismo lugar.

    El slug se deriva del nombre (ver AlergenoForm) y no se expone ni se
    edita: es el valor que el frontend usa en data-alergeno.

    El form de alta arranca oculto (lo revela el boton en el template). Tras
    un POST, un flag de sesion mantiene el form abierto en el redirect; solo
    un refresco manual (F5) lo vuelve a ocultar.
    """
    form = AlergenoForm(request.POST or None)
    form_abierto = request.session.pop('alergeno_form_abierto', False)

    if request.method == 'POST':
        form_abierto = True
        if form.is_valid():
            form.save()
            messages.success(request, 'Alérgeno creado.')
            request.session['alergeno_form_abierto'] = True
            return redirect('admin_alergenos')

    return render(request, 'dashboard_admin.html', {
        'seccion': 'alergenos',
        'form': form,
        'alergenos': Alergeno.objects.all(),
        'form_abierto': form_abierto,
    })


@admin_required
@require_POST
def admin_alergeno_eliminar(request, pk):
    alergeno = get_object_or_404(Alergeno, pk=pk)
    nombre = alergeno.nombre
    alergeno.delete()
    messages.success(request, f'Alérgeno "{nombre}" eliminado.')
    return redirect('admin_alergenos')


# ---- Mesas ----

@admin_required
def admin_mesas(request):
    """Gestion del salon: grilla de mesas activas."""
    return _render_mesas(request, Mesa.objects.filter(activa=True), vista_retiradas=False)


@admin_required
def admin_mesas_retiradas(request):
    """Mesas retiradas del salon (soft delete, historia intacta)."""
    return _render_mesas(request, Mesa.objects.filter(activa=False), vista_retiradas=True)


def _render_mesas(request, mesas, vista_retiradas):
    """Arma la grilla con el conteo de reservas por mesa.

    El conteo se cierra en Python (una consulta por mesa) como en salon.py:
    Mongo no soporta los joins de annotate/prefetch de forma fiable.
    """
    entradas = [
        {
            'mesa': mesa,
            'total_reservas': mesa.reservas.count(),
            'reservas_pendientes': mesa.reservas_pendientes(),
        }
        for mesa in mesas.order_by('numero')
    ]
    return render(request, 'dashboard_admin.html', {
        'seccion': 'mesas',
        'entradas': entradas,
        'vista_retiradas': vista_retiradas,
        'capacidad_salon': SalonConfig.actual().capacidad,
        'mesas_activas': Mesa.objects.filter(activa=True).count(),
        'total_retiradas': Mesa.objects.filter(activa=False).count(),
    })


@admin_required
def admin_mesa_crear(request):
    form = MesaForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        config = SalonConfig.actual()
        if Mesa.objects.filter(activa=True).count() >= config.capacidad:
            messages.error(request, 'No puedes añadir más mesas de las definidas, redimensiona el salón.')
            return redirect('admin_mesas')
        mesa = form.save()
        messages.success(request, f'Mesa {mesa.numero} creada.')
        return redirect('admin_mesas')
    return render(request, 'dashboard_admin.html', {
        'seccion': 'mesas', 'form': form, 'modo': 'crear',
    })


@admin_required
@require_POST
def admin_mesas_redimensionar(request):
    try:
        nueva = int(request.POST.get('capacidad', ''))
    except (TypeError, ValueError):
        messages.error(request, 'Capacidad inválida.')
        return redirect('admin_mesas')

    if nueva < 1:
        messages.error(request, 'La capacidad debe ser al menos 1.')
        return redirect('admin_mesas')

    # Bajar el salon retira las mesas que sobran (las de mayor numero), pero
    # ninguna con reservas pendientes: esas reservas quedarian apuntando a
    # una mesa que ya no esta en el salon.
    activas = list(Mesa.objects.filter(activa=True).order_by('-numero'))
    if nueva < len(activas):
        sobrantes = activas[:len(activas) - nueva]
        bloqueadas = [mesa for mesa in sobrantes if mesa.reservas_pendientes()]
        if bloqueadas:
            numeros = ', '.join(str(mesa.numero) for mesa in bloqueadas)
            messages.error(
                request,
                f'No puedes redimensionar a {nueva}: las mesas {numeros} tienen reservas pendientes.',
            )
            return redirect('admin_mesas')
        for mesa in sobrantes:
            mesa.retirar()

    config = SalonConfig.actual()
    config.capacidad = nueva
    config.save(update_fields=['capacidad'])
    messages.success(request, f'Salón redimensionado a {nueva} mesas.')
    return redirect('admin_mesas')


@admin_required
@require_POST
def admin_mesa_retirar(request, pk):
    mesa = get_object_or_404(Mesa, pk=pk)
    try:
        mesa.retirar()
    except ValueError as error:
        messages.error(request, str(error))
    else:
        messages.success(request, f'Mesa {mesa.numero} retirada.')
    return redirect('admin_mesas')


@admin_required
@require_POST
def admin_mesa_reactivar(request, pk):
    mesa = get_object_or_404(Mesa, pk=pk)
    config = SalonConfig.actual()
    if Mesa.objects.filter(activa=True).count() >= config.capacidad:
        messages.error(request, 'No puedes añadir más mesas de las definidas, redimensiona el salón.')
        return redirect('admin_mesas_retiradas')
    mesa.reactivar()
    messages.success(request, f'Mesa {mesa.numero} reactivada.')
    return redirect('admin_mesas_retiradas')


@admin_required
@require_POST
def admin_mesa_borrar(request, pk):
    mesa = get_object_or_404(Mesa, pk=pk)
    try:
        mesa.borrar()
    except ValueError as error:
        messages.error(request, str(error))
    else:
        messages.success(request, f'Mesa {mesa.numero} borrada.')
    return redirect('admin_mesas')


@admin_required
@require_POST
def admin_mesa_mover(request, pk):
    mesa = get_object_or_404(Mesa, pk=pk)
    nueva_ubicacion = request.POST.get('ubicacion', '').strip()
    if not nueva_ubicacion:
        messages.error(request, 'La ubicación no puede quedar vacía.')
    else:
        mesa.editar_ubicacion(nueva_ubicacion)
        messages.success(request, f'Mesa {mesa.numero} movida a "{nueva_ubicacion}".')
    return redirect('admin_mesas')


# ---- Meseros ----

@admin_required
def admin_meseros(request):
    """Listado de meseros."""
    meseros = User.objects.filter(rol=User.Rol.MESERO).order_by('first_name', 'username')
    return render(request, 'dashboard_admin.html', {'seccion': 'meseros', 'meseros': meseros})


@admin_required
def admin_mesero_crear(request):
    """Alta de un mesero por la via controlada (User.crear_mesero)."""
    form = MeseroForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        mesero = form.crear_mesero()
        messages.success(request, f'Mesero "{mesero.email}" creado.')
        return redirect('admin_meseros')
    return render(request, 'dashboard_admin.html', {
        'seccion': 'meseros', 'form': form, 'modo': 'crear',
    })


# ---- Administradores ----

@admin_required
def admin_admins(request):
    """Listado de administradores."""
    admins = User.objects.filter(rol=User.Rol.ADMIN).order_by('first_name', 'username')
    return render(request, 'dashboard_admin.html', {'seccion': 'admins', 'admins': admins})


@admin_required
def admin_admin_crear(request):
    """Alta de un administrador por la via controlada (User.crear_admin)."""
    form = AdminForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        admin = form.crear_admin()
        messages.success(request, f'Administrador "{admin.email}" creado.')
        return redirect('admin_admins')
    return render(request, 'dashboard_admin.html', {
        'seccion': 'admins', 'form': form, 'modo': 'crear',
    })


# ---- Reservas ----

@admin_required
def admin_reservas(request):
    """Trazabilidad: todas las reservas, las mas recientes primero."""
    reservas = Reserva.objects.select_related('mesa', 'cliente', 'creada_por').order_by('-fecha', '-hora_inicio')
    return render(request, 'dashboard_admin.html', {'seccion': 'reservas', 'reservas': reservas})


@admin_required
@require_POST
def admin_reserva_cancelar(request, pk):
    reserva = get_object_or_404(Reserva, pk=pk)
    try:
        reserva.cancelar()
    except ValueError as error:
        messages.error(request, str(error))
    else:
        messages.success(request, f'Reserva de {reserva.nombre_cliente} cancelada.')
    return redirect('admin_reservas')


# ---- Clientes ----

@admin_required
def admin_clientes(request):
    """Clientes activos, con su historial de reservas."""
    return _render_clientes(
        request,
        User.objects.filter(rol=User.Rol.CLIENTE, is_active=True),
        vista_desactivados=False,
    )


@admin_required
def admin_clientes_desactivados(request):
    """Usuarios desactivados (soft delete, historia intacta)."""
    return _render_clientes(
        request,
        User.objects.filter(rol=User.Rol.CLIENTE, is_active=False),
        vista_desactivados=True,
    )


def _render_clientes(request, clientes, vista_desactivados):
    """Arma el listado con el conteo de reservas por cliente.

    El conteo se cierra en Python (una consulta por cliente) como en mesas:
    Mongo no soporta los joins de annotate/prefetch de forma fiable.
    """
    entradas = [
        {
            'cliente': cliente,
            'total_reservas': cliente.reservas.count(),
            'reservas_pendientes': cliente.reservas_pendientes().count(),
        }
        for cliente in clientes.order_by('first_name', 'username')
    ]
    return render(request, 'dashboard_admin.html', {
        'seccion': 'clientes',
        'clientes': entradas,
        'vista_desactivados': vista_desactivados,
        'total_activos': User.objects.filter(rol=User.Rol.CLIENTE, is_active=True).count(),
        'total_desactivados': User.objects.filter(rol=User.Rol.CLIENTE, is_active=False).count(),
    })


@admin_required
@require_POST
def admin_cliente_editar(request, pk):
    cliente = get_object_or_404(User, pk=pk, rol=User.Rol.CLIENTE)
    form = ClienteForm(request.POST, instance=cliente)
    if form.is_valid():
        form.save()
        messages.success(request, f'Cliente "{cliente.email}" actualizado.')
    else:
        messages.error(request, 'No se pudo actualizar el cliente.')
    return redirect('admin_clientes')


@admin_required
@require_POST
def admin_cliente_desactivar(request, pk):
    cliente = get_object_or_404(User, pk=pk, rol=User.Rol.CLIENTE)
    canceladas = cliente.desactivar()
    if canceladas:
        messages.success(
            request,
            f'Cliente "{cliente.email}" desactivado y {canceladas} reservas pendientes canceladas.',
        )
    else:
        messages.success(request, f'Cliente "{cliente.email}" desactivado.')
    return redirect('admin_clientes')


@admin_required
@require_POST
def admin_cliente_activar(request, pk):
    cliente = get_object_or_404(User, pk=pk, rol=User.Rol.CLIENTE)
    cliente.activar()
    messages.success(request, f'Cliente "{cliente.email}" reactivado.')
    return redirect('admin_clientes_desactivados')
