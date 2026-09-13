from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinLengthValidator
from django.db import models

from .validators import validar_tamanho_imagem


class Redacao(models.Model):
    class Status(models.TextChoices):
        ENVIADA = "enviada", "Enviada"
        PROCESSANDO = "processando", "Processando"
        CONCLUIDA = "concluida", "Concluída"
        ERRO = "erro", "Erro"

    aluno = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="aluno",
        on_delete=models.CASCADE,
        related_name="redacoes",
    )
    tema = models.CharField(
        "tema",
        max_length=255,
        validators=[MinLengthValidator(5)],
    )
    imagem = models.ImageField(
        "imagem da redação",
        upload_to="redacoes/%Y/%m/",
        blank=True,
        validators=[validar_tamanho_imagem],
    )
    texto_original = models.TextField("texto original", blank=True)
    texto_transcrito = models.TextField("texto transcrito", blank=True)
    texto_revisado = models.TextField("texto revisado", blank=True)
    resultado_json = models.JSONField("resultado estruturado", default=dict, blank=True)
    status = models.CharField(
        "status",
        max_length=20,
        choices=Status.choices,
        default=Status.ENVIADA,
        db_index=True,
    )
    comentario_professor = models.TextField("comentário do professor", blank=True)
    corrigido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="corrigido por",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="redacoes_corrigidas",
    )
    corrigido_em = models.DateTimeField("corrigido em", null=True, blank=True)
    criada_em = models.DateTimeField("criada em", auto_now_add=True)
    atualizada_em = models.DateTimeField("atualizada em", auto_now=True)

    class Meta:
        ordering = ["-criada_em"]
        verbose_name = "redação"
        verbose_name_plural = "redações"

    def clean(self):
        super().clean()

        if self.tema:
            self.tema = self.tema.strip()

        if self.texto_original:
            self.texto_original = self.texto_original.strip()

        if not self.imagem and not self.texto_original:
            raise ValidationError(
                "Informe uma imagem da redação ou o texto original."
            )

    def __str__(self):
        return self.tema
