import random
import string

from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.db import models


class UsuarioManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("O e-mail é obrigatório.")
        email = self.normalize_email(email)
        usuario = self.model(email=email, **extra_fields)
        usuario.set_password(password)
        usuario.save(using=self._db)
        return usuario

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        extra_fields.setdefault("tipo", Usuario.Tipo.ALUNO)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("tipo", Usuario.Tipo.PROFESSOR)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superusuário precisa de is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superusuário precisa de is_superuser=True.")

        return self._create_user(email, password, **extra_fields)


class Usuario(AbstractUser):
    class Tipo(models.TextChoices):
        ALUNO = "aluno", "Aluno"
        PROFESSOR = "professor", "Professor"

    username = None
    email = models.EmailField("e-mail", unique=True)
    tipo = models.CharField("tipo de usuário", max_length=10, choices=Tipo.choices)
    turma = models.ForeignKey(
        "Turma",
        verbose_name="turma",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="alunos",
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UsuarioManager()

    class Meta:
        verbose_name = "usuário"
        verbose_name_plural = "usuários"

    def __str__(self):
        return self.get_full_name() or self.email

    @property
    def is_aluno(self):
        return self.tipo == self.Tipo.ALUNO

    @property
    def is_professor(self):
        return self.tipo == self.Tipo.PROFESSOR


class Turma(models.Model):
    professor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="professor",
        on_delete=models.CASCADE,
        related_name="turmas",
        limit_choices_to={"tipo": Usuario.Tipo.PROFESSOR},
    )
    nome = models.CharField("nome", max_length=100)
    codigo = models.CharField("código", max_length=8, unique=True, editable=False)
    criada_em = models.DateTimeField("criada em", auto_now_add=True)

    class Meta:
        ordering = ["-criada_em"]
        verbose_name = "turma"
        verbose_name_plural = "turmas"

    def __str__(self):
        return self.nome

    def save(self, *args, **kwargs):
        if not self.codigo:
            self.codigo = self._gerar_codigo_unico()
        super().save(*args, **kwargs)

    @staticmethod
    def _gerar_codigo_unico():
        alfabeto = string.ascii_uppercase + string.digits
        while True:
            codigo = "".join(random.choices(alfabeto, k=6))
            if not Turma.objects.filter(codigo=codigo).exists():
                return codigo
