from django.urls import path

from .views import MenuPageView

urlpatterns = [
    path('menu/', MenuPageView.as_view(), name='menu'),
]
