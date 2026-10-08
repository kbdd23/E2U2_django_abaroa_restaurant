from django.views.generic import TemplateView

from .models import Alergeno, Item


class MenuPageView(TemplateView):
    template_name = 'menu.html'

    def get_context_data(self, **kwargs):
        """La carta viva: los platos, las categorias y los alergenos salen
        de la base de datos, no del HTML.

        Sin prefetch_related: el backend de MongoDB no lo soporta y lanza
        NotSupportedError. Cada plato consulta sus alergenos por separado,
        asi que una carta larga pagaria una consulta por plato.
        """
        contexto = super().get_context_data(**kwargs)
        contexto['items'] = Item.objects.filter(disponible=True)
        contexto['categorias'] = Item.Categoria.choices
        contexto['alergenos'] = Alergeno.objects.all()
        return contexto
