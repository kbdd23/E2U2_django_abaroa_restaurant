"""Pruebas del inicio.

El inicio es la misma URL para los tres roles: lo unico que cambia es lo que
se le ofrece a cada uno. Un mesero no reserva como cliente, asi que el boton
no puede aparecer donde la vista lo va a rechazar.
"""

from django.test import TestCase
from django.urls import reverse

from panel.models import User


class InicioPorRolTest(TestCase):
    def setUp(self):
        # Credenciales unicas por prueba: la base de test de Mongo puede
        # arrastrar documentos de una corrida anterior.
        self.mesero = User.crear_mesero(
            username=f'mesero-{self._testMethodName}@abaroa.com',
            email=f'mesero-{self._testMethodName}@abaroa.com',
            password='1234', first_name='Ana',
        )
        self.admin = User.crear_admin(
            username=f'admin-{self._testMethodName}@abaroa.cl',
            email=f'admin-{self._testMethodName}@abaroa.cl',
            password='1234', first_name='Administradora',
        )
        self.cliente = User.objects.create_user(
            username=f'cliente-{self._testMethodName}@gmail.com',
            password='1234', first_name='Kevin',
        )

    def inicio(self, usuario):
        self.client.force_login(usuario)
        return self.client.get(reverse('home'))

    def test_el_inicio_del_mesero_cambia_reservar_por_salon(self):
        respuesta = self.inicio(self.mesero)

        self.assertNotContains(respuesta, reverse('booking:crear_reserva'))
        # El texto tampoco puede prometerle una reserva que no puede hacer.
        self.assertNotContains(respuesta, 'hacer reservas')
        # El boton grande sigue en el hero, pero lleva al salon del mesero.
        self.assertContains(
            respuesta,
            f'<a class="btn-reservar-gigante" href="{reverse("mesero")}">Salón</a>',
        )
        self.assertContains(respuesta, reverse('menu'))
        self.assertContains(respuesta, reverse('logout'))

    def test_el_inicio_del_admin_tampoco_ofrece_reservar(self):
        respuesta = self.inicio(self.admin)

        self.assertNotContains(respuesta, reverse('booking:crear_reserva'))

    def test_el_inicio_del_cliente_ofrece_reservar(self):
        respuesta = self.inicio(self.cliente)

        self.assertContains(respuesta, reverse('booking:crear_reserva'))

    def test_el_inicio_anonimo_ofrece_el_login_para_reservar(self):
        respuesta = self.client.get(reverse('home'))

        self.assertContains(respuesta, reverse('login'))


class BotonDeTemaTest(TestCase):
    """El boton de accesibilidad vive en el header de todas las paginas.

    El estado del tema es el atributo data-tema del <html>, y el CSS reacciona
    a el. Lo que se prueba aca es ese contrato: el atributo arranca en claro y
    el boton existe siempre, con sesion o sin ella.
    """

    def setUp(self):
        self.cliente = User.objects.create_user(
            username=f'cliente-{self._testMethodName}@gmail.com',
            password='1234', first_name='Kevin',
        )

    def test_el_header_trae_el_boton_de_tema(self):
        respuesta = self.client.get(reverse('home'))

        self.assertContains(respuesta, 'data-tema="claro"')
        self.assertContains(respuesta, 'id="btn-tema"')
        self.assertContains(respuesta, 'aria-pressed="false"')
        self.assertContains(respuesta, 'aria-label="Modo oscuro"')

    def test_el_boton_de_tema_no_depende_de_la_sesion(self):
        # Un invitado tambien tiene derecho a leer la carta en oscuro.
        anonima = self.client.get(reverse('home'))
        self.client.force_login(self.cliente)
        logueada = self.client.get(reverse('home'))

        self.assertContains(anonima, 'id="btn-tema"')
        self.assertContains(logueada, 'id="btn-tema"')

    def test_el_tema_se_aplica_antes_de_pintar_la_pagina(self):
        respuesta = self.client.get(reverse('home'))
        pagina = respuesta.content.decode()

        # El script tiene que ir en el <head>. Si bajara al final del body, la
        # pagina se pintaria en claro antes de saltar a oscuro.
        self.assertLess(
            pagina.index("localStorage.getItem('tema')"),
            pagina.index('<body>'),
        )
