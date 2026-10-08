from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('django-admin/', admin.site.urls),  # admin nativo, solo para devs
    path('', include('home.urls')),
    path('', include('panel.urls')),
    path('', include('menu.urls')),
    path('', include('booking.urls')),
    path('', include('orders.urls')),
]
