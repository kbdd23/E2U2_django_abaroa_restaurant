"""Pruebas del invitado que sienta el mesero.

booking/horario.py es puro, asi que su parte se prueba sin base de datos: ahi
vive el calculo del bloque en curso y del rango que puede ocupar un invitado.
Lo demas necesita el ORM, porque las reglas del modelo son las que no se
pueden saltar desde ninguna vista.

El instante nunca se toma del reloj real: se pasa como parametro, igual que
en Orden.tomar(). Por eso las pruebas usan un martes fijo y no dependen del
dia en que se corran.

La base de test de Mongo puede arrastrar documentos de una corrida anterior,
asi que cada prueba se fabrica su propio numero de mesa y sus propias
credenciales, y busca su mesa dentro del mapa en vez de tomar la primera.
"""

from datetime import datetime, time, timedelta
from unittest import mock

from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from panel.models import User

from .forms import ReservaForm
from .horario import (
    MINUTOS_MINIMOS_INVITADO,
    bloque_en_curso,
    motivo_de_invitado,
    opciones_de_invitado,
    rango_de_bloques,
)
from .models import Mesa, Reserva

# El 15/09/2026 es martes (08:00-16:00) y el 13/09/2026 es domingo (cerrado).
MARTES = datetime(2026, 9, 15)
DOMINGO = datetime(2026, 9, 13)


class BloqueEnCursoTest(SimpleTestCase):
    def test_el_bloque_en_curso_contiene_el_instante(self):
        self.assertEqual(
            bloque_en_curso(MARTES.date(), MARTES.replace(hour=13, minute=20)),
            (time(13, 0), time(14, 0)),
        )

    def test_fuera_del_horario_no_hay_bloque_en_curso(self):
        self.assertIsNone(bloque_en_curso(MARTES.date(), MARTES.replace(hour=17, minute=0)))


class RangoDeBloquesTest(SimpleTestCase):
    def test_un_rango_alineado_a_los_bloques_es_valido(self):
        self.assertTrue(rango_de_bloques(MARTES.date(), time(13, 0), time(15, 0)))

    def test_un_rango_desalineado_no_es_valido(self):
        self.assertFalse(rango_de_bloques(MARTES.date(), time(13, 30), time(15, 0)))


class OpcionesDeInvitadoTest(SimpleTestCase):
    def test_el_rango_termina_en_el_proximo_compromiso(self):
        opciones = opciones_de_invitado(MARTES.replace(hour=13, minute=20), tope=time(15, 0))

        self.assertFalse(opciones['cerrado'])
        self.assertEqual(opciones['inicio'], time(13, 0))
        self.assertEqual(opciones['fines'], [time(14, 0), time(15, 0)])
        self.assertTrue(opciones['suficiente'])

    def test_sin_compromiso_el_rango_llega_al_cierre(self):
        opciones = opciones_de_invitado(MARTES.replace(hour=13, minute=20), tope=None)

        self.assertEqual(opciones['fines'][-1], time(16, 0))

    def test_menos_de_una_hora_real_no_alcanza(self):
        # 15:20 con cierre a las 16:00: hay bloque, pero solo 40 minutos.
        opciones = opciones_de_invitado(MARTES.replace(hour=15, minute=20), tope=None)

        self.assertFalse(opciones['suficiente'])
        self.assertLess(opciones['hueco'], timedelta(minutes=MINUTOS_MINIMOS_INVITADO))

    def test_una_hora_de_rango_declarado_con_poco_tiempo_real_no_alcanza(self):
        # 13:50 con un compromiso a las 14:00: el bloque en curso dura una
        # hora, pero al invitado le quedan diez minutos.
        opciones = opciones_de_invitado(MARTES.replace(hour=13, minute=50), tope=time(14, 0))

        self.assertFalse(opciones['suficiente'])

    def test_cerrado_cuando_ya_no_queda_servicio(self):
        opciones = opciones_de_invitado(MARTES.replace(hour=16, minute=30), tope=None)

        self.assertTrue(opciones['cerrado'])
        self.assertEqual(opciones['fines'], [])

    def test_domingo_esta_cerrado(self):
        opciones = opciones_de_invitado(DOMINGO.replace(hour=13, minute=0), tope=None)

        self.assertTrue(opciones['cerrado'])

    def test_antes_de_abrir_el_rango_empieza_en_el_primer_bloque(self):
        opciones = opciones_de_invitado(MARTES.replace(hour=7, minute=30), tope=None)

        self.assertEqual(opciones['inicio'], time(8, 0))


class MotivoDeInvitadoTest(SimpleTestCase):
    def test_sin_motivo_cuando_se_puede_sentar(self):
        opciones = opciones_de_invitado(MARTES.replace(hour=13, minute=20), tope=None)

        self.assertIsNone(motivo_de_invitado(opciones, None))

    def test_nombra_la_hora_del_compromiso_que_estorba(self):
        momento = MARTES.replace(hour=13, minute=50)
        opciones = opciones_de_invitado(momento, tope=time(14, 0))

        self.assertIn('14:00', motivo_de_invitado(opciones, time(14, 0)))

    def test_sin_compromiso_habla_del_cierre(self):
        opciones = opciones_de_invitado(MARTES.replace(hour=15, minute=30), tope=None)

        self.assertIn('cierre', motivo_de_invitado(opciones, None))


class BaseConMesaYMesero(TestCase):
    def setUp(self):
        # Numero y credenciales unicos por prueba: la base de test de Mongo
        # puede arrastrar documentos de una corrida anterior, y una prueba no
        # deberia depender de que la base este vacia.
        self.mesa = Mesa.crear_mesa(
            numero=Mesa.siguiente_numero(), capacidad=4, ubicacion='Ventana',
        )
        self.mesero = User.crear_mesero(
            username=f'mesero-{self._testMethodName}@abaroa.com',
            email=f'mesero-{self._testMethodName}@abaroa.com',
            password='1234', first_name='Ana',
        )

    def momento(self, hora, minuto):
        """El martes fijo, con hora local: la misma que ve el mesero."""
        return timezone.make_aware(MARTES.replace(hour=hora, minute=minuto))

    def reserva_de_cliente(self, hora_inicio, hora_fin):
        cliente = User.objects.create_user(
            username=f'cliente-{self._testMethodName}-{hora_inicio.hour}@gmail.com',
            password='1234',
        )
        return Reserva.objects.create(
            cliente=cliente, mesa=self.mesa, fecha=MARTES.date(),
            hora_inicio=hora_inicio, hora_fin=hora_fin,
        )

    def mesa_en_mapa(self, respuesta):
        """La entrada del mapa de la mesa de esta prueba, no la primera del salon."""
        mesas = respuesta.json()['mesas']
        return next(mesa for mesa in mesas if mesa['numero'] == self.mesa.numero)


class SentarInvitadoTest(BaseConMesaYMesero):
    def test_la_reserva_nace_sin_cliente_y_con_quien_la_sento(self):
        reserva = Reserva.sentar_invitado(self.mesa, self.mesero, self.momento(13, 20), time(15, 0))

        self.assertTrue(reserva.es_invitado)
        self.assertIsNone(reserva.cliente)
        self.assertEqual(reserva.creada_por, self.mesero)
        self.assertEqual(reserva.nombre_cliente, 'Invitado')

    def test_el_invitado_arranca_en_el_bloque_en_curso(self):
        reserva = Reserva.sentar_invitado(self.mesa, self.mesero, self.momento(13, 20), time(14, 0))

        self.assertEqual(reserva.hora_inicio, time(13, 0))
        self.assertEqual(reserva.fecha, MARTES.date())

    def test_el_rango_no_puede_cruzar_el_proximo_compromiso(self):
        self.reserva_de_cliente(time(14, 0), time(15, 0))

        # Cabe de 13:00 a 14:00, no hasta las 15:00.
        with self.assertRaises(ValueError):
            Reserva.sentar_invitado(self.mesa, self.mesero, self.momento(13, 20), time(15, 0))

    def test_con_menos_de_una_hora_por_delante_no_se_sienta_a_nadie(self):
        self.reserva_de_cliente(time(14, 0), time(15, 0))

        with self.assertRaisesMessage(ValueError, '14:00'):
            Reserva.sentar_invitado(self.mesa, self.mesero, self.momento(13, 50), time(14, 0))

    def test_una_mesa_ocupada_no_recibe_invitados(self):
        self.reserva_de_cliente(time(13, 0), time(14, 0))

        with self.assertRaises(ValueError):
            Reserva.sentar_invitado(self.mesa, self.mesero, self.momento(13, 20), time(14, 0))

    def test_el_invitado_es_el_unico_que_puede_quedar_sin_cliente(self):
        reserva = Reserva(cliente=None, mesa=self.mesa, fecha=MARTES.date(),
                          hora_inicio=time(13, 0), hora_fin=time(14, 0))

        with self.assertRaisesMessage(Exception, 'quien la sento'):
            reserva.full_clean()


class SentarInvitadoVistaTest(BaseConMesaYMesero):
    def test_el_post_crea_la_reserva_y_abre_la_cuenta(self):
        self.client.force_login(self.mesero)

        with mock.patch('panel.views.timezone.localtime', return_value=self.momento(13, 20)):
            respuesta = self.client.post(
                reverse('sentar_invitado'),
                {'mesa': self.mesa.numero, 'hora_fin': '15:00'},
            )

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()['mesa'], self.mesa.numero)
        self.assertTrue(respuesta.json()['abierta'])
        self.assertTrue(Reserva.objects.get(mesa=self.mesa).es_invitado)

    def test_el_mapa_trae_las_opciones_de_invitado(self):
        self.client.force_login(self.mesero)

        with mock.patch('panel.views.timezone.localtime', return_value=self.momento(13, 20)):
            respuesta = self.client.get(reverse('mesas_estado'))

        invitado = self.mesa_en_mapa(respuesta)['invitado']
        self.assertEqual(invitado['inicio'], '13:00')
        self.assertEqual(invitado['fines'][-1], '16:00')
        self.assertIsNone(invitado['motivo'])

    def test_el_mapa_avisa_cuando_el_compromiso_esta_encima(self):
        self.reserva_de_cliente(time(14, 0), time(15, 0))
        self.client.force_login(self.mesero)

        with mock.patch('panel.views.timezone.localtime', return_value=self.momento(13, 50)):
            respuesta = self.client.get(reverse('mesas_estado'))

        mesa = self.mesa_en_mapa(respuesta)
        self.assertEqual(mesa['proxima_reserva']['hora_inicio'], '14:00')
        self.assertIn('14:00', mesa['invitado']['motivo'])
        # El rango declarado llega hasta el compromiso, pero quien frena al
        # mesero es el motivo: al invitado le quedan diez minutos reales.
        self.assertEqual(mesa['invitado']['fines'], ['14:00'])

    def test_un_cliente_no_puede_sentar_invitados(self):
        cliente = User.objects.create_user(
            username=f'cliente-{self._testMethodName}@gmail.com', password='1234',
        )
        self.client.force_login(cliente)

        respuesta = self.client.post(
            reverse('sentar_invitado'),
            {'mesa': self.mesa.numero, 'hora_fin': '15:00'},
        )

        self.assertEqual(respuesta.status_code, 403)


class ReservaDeClienteFormTest(BaseConMesaYMesero):
    """El formulario del cliente no se confunde con una reserva de invitado."""

    def datos(self, hora_inicio='13:00', hora_fin='15:00'):
        return {
            'mesa': str(self.mesa.pk),
            'fecha': MARTES.date().isoformat(),
            'hora_inicio': hora_inicio,
            'hora_fin': hora_fin,
        }

    def test_el_formulario_del_cliente_sigue_siendo_valido(self):
        form = ReservaForm(data=self.datos(), cliente=self.mesero)

        self.assertTrue(form.is_valid(), form.errors.as_json())

    def test_el_formulario_sin_cliente_no_inventa_un_invitado(self):
        # Sin cliente la reserva seria de invitado y nadie la sento: el
        # modelo la rechaza en vez de guardar una fila huerfana.
        form = ReservaForm(data=self.datos())

        self.assertFalse(form.is_valid())


class CancelarInvitadoTest(BaseConMesaYMesero):
    """El mesero libera la mesa de un invitado que nadie llego a atender."""

    def sentar(self):
        return Reserva.sentar_invitado(self.mesa, self.mesero, self.momento(13, 20), time(15, 0))

    def test_el_post_cancela_la_reserva_del_invitado(self):
        self.sentar()
        self.client.force_login(self.mesero)

        with mock.patch('panel.views.timezone.localtime', return_value=self.momento(13, 40)):
            respuesta = self.client.post(reverse('cancelar_invitado'), {'mesa': self.mesa.numero})

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(Reserva.objects.get(mesa=self.mesa).estado, Reserva.ESTADO_CANCELADO)

    def test_el_mapa_marca_la_reserva_como_de_invitado(self):
        self.sentar()
        self.client.force_login(self.mesero)

        with mock.patch('panel.views.timezone.localtime', return_value=self.momento(13, 40)):
            respuesta = self.client.get(reverse('mesas_estado'))

        mesa = self.mesa_en_mapa(respuesta)
        self.assertEqual(mesa['estado'], 'por_atender')
        self.assertTrue(mesa['reserva']['es_invitado'])

    def test_no_se_cancela_la_reserva_de_un_cliente(self):
        self.reserva_de_cliente(time(13, 0), time(14, 0))
        self.client.force_login(self.mesero)

        with mock.patch('panel.views.timezone.localtime', return_value=self.momento(13, 20)):
            respuesta = self.client.post(reverse('cancelar_invitado'), {'mesa': self.mesa.numero})

        self.assertEqual(respuesta.status_code, 409)
        self.assertEqual(Reserva.objects.get(mesa=self.mesa).estado, Reserva.ESTADO_CONFIRMADO)


class ReservaDeClientePorRolTest(TestCase):
    """El alta de reserva es del cliente: un mesero no reserva como cliente.

    Ocultar el boton del inicio es la mitad del trabajo. La otra mitad es el
    portero: la URL del formulario queda en el historial del navegador, y
    quien la escriba a mano tiene que encontrarse con el 403.
    """

    def setUp(self):
        self.mesa = Mesa.crear_mesa(
            numero=Mesa.siguiente_numero(), capacidad=4, ubicacion='Ventana',
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

    def datos_de_reserva(self):
        return {
            'mesa': str(self.mesa.pk),
            'fecha': MARTES.date().isoformat(),
            'hora_inicio': '13:00',
            'hora_fin': '14:00',
        }

    def test_el_mesero_no_abre_el_formulario_de_reserva(self):
        self.client.force_login(self.mesero)

        respuesta = self.client.get(reverse('booking:crear_reserva'))

        self.assertEqual(respuesta.status_code, 403)

    def test_el_mesero_no_consulta_la_disponibilidad_de_una_mesa(self):
        self.client.force_login(self.mesero)

        respuesta = self.client.get(
            reverse('booking:bloques'),
            {'mesa': self.mesa.pk, 'fecha': MARTES.date().isoformat()},
        )

        self.assertEqual(respuesta.status_code, 403)

    def test_el_mesero_no_crea_la_reserva_por_post(self):
        self.client.force_login(self.mesero)

        respuesta = self.client.post(reverse('booking:crear_reserva'), self.datos_de_reserva())

        self.assertEqual(respuesta.status_code, 403)
        self.assertFalse(Reserva.objects.filter(mesa=self.mesa).exists())

    def test_el_cliente_si_abre_el_formulario(self):
        self.client.force_login(self.cliente)

        respuesta = self.client.get(reverse('booking:crear_reserva'))

        self.assertEqual(respuesta.status_code, 200)

    def test_un_anonimo_va_al_login_antes_de_reservar(self):
        respuesta = self.client.get(reverse('booking:crear_reserva'))

        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(reverse('login'), respuesta.url)
