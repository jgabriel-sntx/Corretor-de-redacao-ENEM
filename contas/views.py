from allauth.account.models import EmailAddress
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .decorators import professor_required
from .forms import (
    CadastroAlunoForm,
    CadastroProfessorForm,
    EditarEmailForm,
    EditarNomeForm,
    TurmaForm,
)
from .models import Turma, Usuario


@require_http_methods(["GET"])
def escolha_cadastro(request):
    if request.user.is_authenticated:
        return redirect("contas:pos_login")
    return render(request, "contas/cadastro_escolha.html")


def _criar_usuario(form, tipo, request, *, turma=None):
    usuario = Usuario.objects.create_user(
        email=form.cleaned_data["email"],
        password=form.cleaned_data["senha"],
        first_name=form.cleaned_data["nome"].strip(),
        tipo=tipo,
        turma=turma,
    )
    EmailAddress.objects.create(
        user=usuario,
        email=usuario.email,
        primary=True,
        verified=True,
    )
    login(request, usuario, backend="django.contrib.auth.backends.ModelBackend")
    return usuario


@require_http_methods(["GET", "POST"])
def cadastro_aluno(request):
    if request.user.is_authenticated:
        return redirect("contas:pos_login")

    if request.method == "POST":
        form = CadastroAlunoForm(request.POST)
        if form.is_valid():
            _criar_usuario(
                form,
                Usuario.Tipo.ALUNO,
                request,
                turma=form.cleaned_data["turma"],
            )
            messages.success(request, "Cadastro realizado com sucesso. Bem-vindo(a)!")
            return redirect("contas:pos_login")
    else:
        form = CadastroAlunoForm()

    return render(request, "contas/cadastro_aluno.html", {"form": form})


@require_http_methods(["GET", "POST"])
def cadastro_professor(request):
    if request.user.is_authenticated:
        return redirect("contas:pos_login")

    if request.method == "POST":
        form = CadastroProfessorForm(request.POST)
        if form.is_valid():
            _criar_usuario(form, Usuario.Tipo.PROFESSOR, request)
            messages.success(request, "Cadastro realizado com sucesso. Bem-vindo(a)!")
            return redirect("contas:pos_login")
    else:
        form = CadastroProfessorForm()

    return render(request, "contas/cadastro_professor.html", {"form": form})


@login_required
def pos_login(request):
    if request.user.is_professor:
        return redirect("contas:professor_home")
    return redirect("redacoes:home")


@login_required
def conta(request):
    return render(request, "contas/conta.html")


@login_required
def conta_editar_nome(request):
    if request.method == "POST":
        form = EditarNomeForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Nome atualizado com sucesso.")
            return redirect("contas:conta")
    else:
        form = EditarNomeForm(instance=request.user)

    return render(request, "contas/conta_editar_nome.html", {"form": form})


@login_required
def conta_editar_email(request):
    if request.method == "POST":
        form = EditarEmailForm(request.POST, usuario=request.user)
        if form.is_valid():
            novo_email = form.cleaned_data["email"]
            request.user.email = novo_email
            request.user.save(update_fields=["email"])
            EmailAddress.objects.filter(user=request.user).delete()
            EmailAddress.objects.create(
                user=request.user,
                email=novo_email,
                primary=True,
                verified=True,
            )
            messages.success(request, "E-mail atualizado com sucesso.")
            return redirect("contas:conta")
    else:
        form = EditarEmailForm(usuario=request.user, initial={"email": request.user.email})

    return render(request, "contas/conta_editar_email.html", {"form": form})


@professor_required
def professor_home(request):
    turmas = request.user.turmas.all()
    return render(request, "contas/professor_home.html", {"turmas": turmas})


@professor_required
def turma_criar(request):
    if request.method == "POST":
        form = TurmaForm(request.POST)
        if form.is_valid():
            turma = form.save(commit=False)
            turma.professor = request.user
            turma.save()
            messages.success(request, "Turma criada com sucesso.")
            return redirect("contas:turma_detalhe", pk=turma.pk)
    else:
        form = TurmaForm()

    return render(request, "contas/turma_form.html", {"form": form, "modo": "criar"})


def _turma_do_professor(request, pk):
    return get_object_or_404(Turma, pk=pk, professor=request.user)


@professor_required
def turma_detalhe(request, pk):
    turma = _turma_do_professor(request, pk)
    alunos = turma.alunos.all()
    return render(request, "contas/turma_detalhe.html", {"turma": turma, "alunos": alunos})


@professor_required
def turma_editar(request, pk):
    turma = _turma_do_professor(request, pk)

    if request.method == "POST":
        form = TurmaForm(request.POST, instance=turma)
        if form.is_valid():
            form.save()
            messages.success(request, "Turma atualizada com sucesso.")
            return redirect("contas:turma_detalhe", pk=turma.pk)
    else:
        form = TurmaForm(instance=turma)

    return render(
        request, "contas/turma_form.html", {"form": form, "modo": "editar", "turma": turma}
    )


@professor_required
def aluno_historico(request, pk):
    aluno = get_object_or_404(
        Usuario, pk=pk, tipo=Usuario.Tipo.ALUNO, turma__professor=request.user
    )
    redacoes = aluno.redacoes.all()
    return render(
        request, "contas/aluno_historico.html", {"aluno": aluno, "redacoes": redacoes}
    )
