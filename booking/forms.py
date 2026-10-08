from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from .horario import bloques_del_dia, rango_de_bloques
from .models import Mesa, Reserva


class ReservaForm(forms.ModelForm):
    """Formulario de reserva: el cliente elige mesa, fecha y bloque horario.

    El cliente (usuario autenticado) no aparece en el form: la vista se lo
    pasa al constructor, y el form lo deja puesto en la instancia antes de
    que el modelo valide. Sin eso, el modelo veria una reserva sin cliente
    (un invitado) y le exigiria quien la sento. El estado nace siempre
    'confirmado'.
    """

    class Meta:
        model = Reserva
        fields = ['mesa', 'fecha', 'hora_inicio', 'hora_fin']
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date'}),
            'hora_inicio': forms.TimeInput(attrs={'type': 'time'}),
            'hora_fin': forms.TimeInput(attrs={'type': 'time'}),
        }

    def __init__(self, *args, cliente=None, **kwargs):
        self.cliente = cliente
        super().__init__(*args, **kwargs)
        # El cliente solo ve mesas en servicio; la disponibilidad real la
        # decide la BD en clean(), contra las reservas confirmadas.
        self.fields['mesa'].queryset = Mesa.objects.filter(activa=True)

    def clean(self):
        # Se ejecuta automaticamente cuando la vista llama a is_valid(), y
        # antes de la validacion del modelo (_post_clean).
        if self.cliente is not None:
            self.instance.cliente = self.cliente

        # super().clean() corre primero el clean() del modelo (hora_fin > hora_inicio).
        datos = super().clean()
        mesa = datos.get('mesa')
        fecha = datos.get('fecha')
        hora_inicio = datos.get('hora_inicio')
        hora_fin = datos.get('hora_fin')

        if fecha:
            self._validar_fecha(fecha, hora_inicio)

        if mesa and fecha and hora_inicio and hora_fin:
            # El rango debe cubrir bloques completos: la misma regla que usa
            # el invitado que sienta el mesero (booking.horario.rango_de_bloques).
            if not rango_de_bloques(fecha, hora_inicio, hora_fin):
                raise ValidationError('Elige un rango completo de bloques dentro del horario de atencion.')
            if Reserva.solapamiento(mesa, fecha, hora_inicio, hora_fin).exists():
                raise ValidationError('Esa mesa ya esta reservada en ese horario.')
        return datos

    def _validar_fecha(self, fecha, hora_inicio):
        """Reglas de dominio sobre la fecha: pasado, cerrado y bloques vencidos."""
        hoy = timezone.localdate()
        if fecha < hoy:
            raise ValidationError('No puedes reservar para una fecha pasada.')

        if not bloques_del_dia(fecha):
            raise ValidationError('El restaurante esta cerrado ese dia.')

        # El bloque que ya empezo hoy no se puede reservar.
        if fecha == hoy and hora_inicio and hora_inicio <= timezone.localtime().time():
            raise ValidationError('Ese bloque ya comenzo, elige una hora futura.')
