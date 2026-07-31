from django.urls import path

from . import views


app_name = "redacoes"

urlpatterns = [
    path("", views.pagina_inicial, name="inicio"),
    path("redacoes/<int:pk>/revisao/", views.revisar_redacao, name="revisao"),
    path("redacoes/<int:pk>/resultado/", views.resultado_redacao, name="resultado"),
]
