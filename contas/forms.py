from allauth.account.forms import ChangePasswordForm as AllauthChangePasswordForm
from allauth.account.forms import LoginForm as AllauthLoginForm
from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .models import Turma, Usuario


def _aplicar_classes_bootstrap(form):
    for campo in form.fields.values():
        if isinstance(campo.widget, forms.CheckboxInput):
            campo.widget.attrs["class"] = "form-check-input"
        else:
            campo.widget.attrs["class"] = "form-control form-control-lg"


class LoginForm(AllauthLoginForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _aplicar_classes_bootstrap(self)


class ChangePasswordForm(AllauthChangePasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _aplicar_classes_bootstrap(self)


class _CadastroBaseForm(forms.Form):
    nome = forms.CharField(
        label="Nome",
        max_length=150,
        widget=forms.TextInput(
            attrs={"class": "form-control form-control-lg", "autocomplete": "name"}
        ),
    )
    email = forms.EmailField(
        label="E-mail",
        widget=forms.EmailInput(
            attrs={"class": "form-control form-control-lg", "autocomplete": "email"}
        ),
    )
    senha = forms.CharField(
        label="Senha",
        widget=forms.PasswordInput(
            attrs={"class": "form-control form-control-lg", "autocomplete": "new-password"}
        ),
    )
    confirmar_senha = forms.CharField(
        label="Confirmação da senha",
        widget=forms.PasswordInput(
            attrs={"class": "form-control form-control-lg", "autocomplete": "new-password"}
        ),
    )

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if Usuario.objects.filter(email__iexact=email).exists():
            raise ValidationError("Já existe uma conta com este e-mail.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        senha = cleaned_data.get("senha")
        confirmar_senha = cleaned_data.get("confirmar_senha")

        if senha and confirmar_senha and senha != confirmar_senha:
            self.add_error("confirmar_senha", "As senhas não coincidem.")

        if senha:
            try:
                validate_password(senha)
            except ValidationError as erro:
                self.add_error("senha", erro)

        return cleaned_data


class CadastroAlunoForm(_CadastroBaseForm):
    codigo_turma = forms.CharField(
        label="Código da turma",
        max_length=8,
        widget=forms.TextInput(
            attrs={
                "class": "form-control form-control-lg text-uppercase",
                "autocomplete": "off",
                "placeholder": "Ex.: A1B2C3",
            }
        ),
    )

    def clean_codigo_turma(self):
        codigo = self.cleaned_data["codigo_turma"].strip().upper()
        try:
            turma = Turma.objects.get(codigo=codigo)
        except Turma.DoesNotExist as erro:
            raise ValidationError(
                "Não encontramos nenhuma turma com esse código. Confira com o professor."
            ) from erro
        self.cleaned_data["turma"] = turma
        return codigo


class CadastroProfessorForm(_CadastroBaseForm):
    pass


class EditarNomeForm(forms.ModelForm):
    class Meta:
        model = Usuario
        fields = ["first_name"]
        labels = {"first_name": "Nome"}
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "form-control form-control-lg"}),
        }

    def clean_first_name(self):
        nome = self.cleaned_data["first_name"].strip()
        if not nome:
            raise ValidationError("Informe um nome.")
        return nome


class EditarEmailForm(forms.Form):
    email = forms.EmailField(
        label="Novo e-mail",
        widget=forms.EmailInput(attrs={"class": "form-control form-control-lg"}),
    )

    def __init__(self, *args, usuario=None, **kwargs):
        self._usuario = usuario
        super().__init__(*args, **kwargs)

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if Usuario.objects.filter(email__iexact=email).exclude(pk=self._usuario.pk).exists():
            raise ValidationError("Já existe uma conta com este e-mail.")
        return email


class TurmaForm(forms.ModelForm):
    class Meta:
        model = Turma
        fields = ["nome"]
        labels = {"nome": "Nome da turma"}
        widgets = {
            "nome": forms.TextInput(
                attrs={
                    "class": "form-control form-control-lg",
                    "placeholder": "Ex.: 3º ano B — manhã",
                }
            ),
        }
