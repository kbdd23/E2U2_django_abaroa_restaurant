"""Porteros de acceso por rol.

El modelo User ya distingue roles, pero un rol sin portero es decorativo:
cualquiera con sesion abierta entra escribiendo la URL a mano.
"""

from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied

from .models import User


def mesero_required(vista):
    """Deja pasar solo a meseros.

    Anonimo -> al login, guardando a donde iba. Autenticado con otro rol
    -> 403, no un redirect silencioso: un cliente que llega aca no se
    perdio, intento entrar, y merece saber que no puede.
    """
    @wraps(vista)
    def envoltorio(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if request.user.rol != User.Rol.MESERO:
            raise PermissionDenied
        return vista(request, *args, **kwargs)

    return envoltorio


def admin_required(vista):
    """Deja pasar solo a administradores.

    Anonimo -> al login. Autenticado con otro rol -> 403: un cliente o un
    mesero que llega al panel de administracion no se perdio, intento
    entrar donde no debe.
    """
    @wraps(vista)
    def envoltorio(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if request.user.rol != User.Rol.ADMIN:
            raise PermissionDenied
        return vista(request, *args, **kwargs)

    return envoltorio


def cliente_required(vista):
    """Deja pasar solo a clientes.

    Anonimo -> al login, guardando a donde iba. Autenticado con otro rol
    -> 403: un mesero que llega al alta de reservas no se perdio, intento
    reservar como cliente, y la reserva de cliente es del cliente. Ocultar
    el boton del inicio no alcanza: la URL queda en el historial.

    El mesero no se queda sin puerta: para ocupar una mesa tiene la suya,
    sentar_invitado, donde el invitado no lleva cuenta.
    """
    @wraps(vista)
    def envoltorio(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if request.user.rol != User.Rol.CLIENTE:
            raise PermissionDenied
        return vista(request, *args, **kwargs)

    return envoltorio
