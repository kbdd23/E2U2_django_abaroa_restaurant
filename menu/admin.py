from django.contrib import admin
from .models import Alergeno, Item


@admin.action(description='Retirar de la carta (soft delete)')
def retirar_items(modeladmin, request, queryset):
    for item in queryset:
        item.retirar()


@admin.action(description='Reactivar en la carta')
def reactivar_items(modeladmin, request, queryset):
    for item in queryset:
        item.reactivar()


@admin.register(Alergeno)
class AlergenoAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'slug']
    search_fields = ['nombre', 'slug']
    prepopulated_fields = {'slug': ('nombre',)}


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'categoria', 'precio', 'badge', 'disponible']
    list_filter = ['categoria', 'disponible']
    search_fields = ['nombre', 'descripcion']
    filter_horizontal = ['alergenos']
    actions = [retirar_items, reactivar_items]
