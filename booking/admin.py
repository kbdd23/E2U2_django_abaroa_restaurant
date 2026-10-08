from django.contrib import admin
from .models import Mesa, Reserva, SalonConfig


@admin.action(description='Retirar del salon (soft delete)')
def retirar_mesas(modeladmin, request, queryset):
    for mesa in queryset:
        mesa.retirar()


@admin.register(Mesa)
class MesaAdmin(admin.ModelAdmin):
    list_display = ['numero', 'capacidad', 'ubicacion', 'es_grande', 'activa']
    list_filter = ['activa', 'ubicacion']
    actions = [retirar_mesas]


@admin.register(Reserva)
class ReservaAdmin(admin.ModelAdmin):
    list_display = ['cliente', 'mesa', 'fecha', 'hora_inicio', 'hora_fin', 'estado']
    list_filter = ['estado', 'fecha']
    date_hierarchy = 'fecha'


@admin.register(SalonConfig)
class SalonConfigAdmin(admin.ModelAdmin):
    """Registro unico: el salon se redimensiona, no se duplica ni se borra."""

    list_display = ['capacidad']

    def has_add_permission(self, request):
        # SalonConfig.actual() crea el registro si no existe; el admin no
        # debe poder dejar un segundo, o el contador del salon se duplica.
        return not SalonConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
