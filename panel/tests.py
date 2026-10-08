"""Pruebas del panel de administracion.

La lista de reservas tiene que distinguir a un cliente con cuenta de un
invitado que sento el mesero: si los confunde, el administrador no sabe a
quien esta cancelando.
"""

from datetime import datetime, time

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from booking.models import Mesa, Reserva

from .models import User

# El 15/09/2026 es martes: el mismo dia fijo que usan las pruebas de booking.
MARTES = datetime(2026, 9, 15)


class AdminReservasTest(TestCase):
    def setUp(self):
        # Credenciales unicas por prueba: la base de test puede arrastrar
        # documentos de una corrida anterior.
        self.mesa = Mesa.crear_mesa(
            numero=Mesa.siguiente_numero(), capacidad=4, ubicacion='Ventana',
        )
        self.admin = User.crear_admin(
            username=f'admin-{self._testMethodName}@abaroa.cl',
            email=f'admin-{self._testMethodName}@abaroa.cl',
            password='1234', first_name='Administradora',
        )
        self.mesero = User.crear_mesero(
            username=f'mesero-{self._testMethodName}@abaroa.com',
            email=f'mesero-{self._testMethodName}@abaroa.com',
            password='1234', first_name='Ana',
        )
        self.cliente = User.objects.create_user(
            username=f'cliente-{self._testMethodName}@gmail.com',
            password='1234', first_name='Kevin',
        )
        self.client.force_login(self.admin)

    def test_la_reserva_de_invitado_se_nombra_y_se_atribuye(self):
        Reserva.sentar_invitado(
            self.mesa, self.mesero,
            timezone.make_aware(MARTES.replace(hour=13, minute=20)),
            time(15, 0),
        )

        respuesta = self.client.get(reverse('admin_reservas'))

        self.assertContains(respuesta, f'Mesa {self.mesa.numero} · Invitado')
        self.assertContains(respuesta, 'sentado por Ana')

    def test_la_reserva_de_cliente_muestra_su_nombre(self):
        Reserva.objects.create(
            cliente=self.cliente, mesa=self.mesa, fecha=MARTES.date(),
            hora_inicio=time(13, 0), hora_fin=time(14, 0),
        )

        respuesta = self.client.get(reverse('admin_reservas'))

        self.assertContains(respuesta, f'Mesa {self.mesa.numero} · Kevin')
