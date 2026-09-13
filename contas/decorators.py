from django.contrib.auth.decorators import user_passes_test

from .models import Usuario


def aluno_required(view):
    teste = user_passes_test(
        lambda usuario: usuario.is_authenticated and usuario.tipo == Usuario.Tipo.ALUNO,
        login_url="account_login",
    )
    return teste(view)


def professor_required(view):
    teste = user_passes_test(
        lambda usuario: usuario.is_authenticated and usuario.tipo == Usuario.Tipo.PROFESSOR,
        login_url="account_login",
    )
    return teste(view)
