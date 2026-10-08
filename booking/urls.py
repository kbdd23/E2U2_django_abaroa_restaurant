from django.urls import path

from .views import bloques_disponibles, cancelar_reserva, crear_reserva

app_name = 'booking'

urlpatterns = [
    path('reservar/', crear_reserva, name='crear_reserva'),
    path('reservar/bloques/', bloques_disponibles, name='bloques'),
    path('reservas/<str:pk>/cancelar/', cancelar_reserva, name='cancelar_reserva'),
]
