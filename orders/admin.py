from django.contrib import admin
from .models import LineaOrden, Orden


class LineaOrdenInline(admin.TabularInline):
    """Las lineas de la cuenta se editan dentro de la orden, no aparte."""

    model = LineaOrden
    extra = 0
    readonly_fields = ['precio_unitario', 'agregada_en']


@admin.action(description='Cerrar cuentas seleccionadas')
def cerrar_ordenes(modeladmin, request, queryset):
    for orden in queryset:
        if orden.esta_abierta:
            orden.cerrar()


@admin.register(Orden)
class OrdenAdmin(admin.ModelAdmin):
    list_display = ['mesero', 'mesa', 'estado', 'abierta_en', 'cerrada_en']
    list_filter = ['estado']
    date_hierarchy = 'abierta_en'
    readonly_fields = ['abierta_en', 'cerrada_en']
    inlines = [LineaOrdenInline]
    actions = [cerrar_ordenes]

    @admin.display(description='Mesa')
    def mesa(self, orden):
        return orden.reserva.mesa.numero


@admin.register(LineaOrden)
class LineaOrdenAdmin(admin.ModelAdmin):
    list_display = ['orden', 'item', 'cantidad', 'precio_unitario', 'subtotal']

    @admin.display(description='Subtotal')
    def subtotal(self, linea):
        return linea.subtotal
