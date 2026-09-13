from django.urls import path

from . import views


app_name = "contas"

urlpatterns = [
    path("cadastro/", views.escolha_cadastro, name="escolha_cadastro"),
    path("cadastro/aluno/", views.cadastro_aluno, name="cadastro_aluno"),
    path("cadastro/professor/", views.cadastro_professor, name="cadastro_professor"),
    path("pos-login/", views.pos_login, name="pos_login"),
    path("conta/", views.conta, name="conta"),
    path("conta/nome/", views.conta_editar_nome, name="conta_editar_nome"),
    path("conta/email/", views.conta_editar_email, name="conta_editar_email"),
    path("professor/", views.professor_home, name="professor_home"),
    path("professor/turmas/nova/", views.turma_criar, name="turma_criar"),
    path("professor/turmas/<int:pk>/", views.turma_detalhe, name="turma_detalhe"),
    path("professor/turmas/<int:pk>/editar/", views.turma_editar, name="turma_editar"),
    path("professor/alunos/<int:pk>/", views.aluno_historico, name="aluno_historico"),
]
