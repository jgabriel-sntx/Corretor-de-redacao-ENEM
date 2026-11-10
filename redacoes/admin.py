from django import forms
from django.contrib import admin
from django.shortcuts import redirect
from django.urls import reverse

from .models import ConfiguracaoAPI, Redacao


class ConfiguracaoAPIForm(forms.ModelForm):
    gemini_api_key = forms.CharField(
        label="Chave da API do Gemini",
        required=False,
        widget=forms.PasswordInput(render_value=False),
        help_text="Deixe em branco para manter a chave atual.",
    )
    ocr_api_key = forms.CharField(
        label="Chave da API do OCR.space",
        required=False,
        widget=forms.PasswordInput(render_value=False),
        help_text="Deixe em branco para manter a chave atual.",
    )
    remover_gemini_api_key = forms.BooleanField(
        label="Remover a chave do Gemini",
        required=False,
    )
    remover_ocr_api_key = forms.BooleanField(
        label="Remover a chave do OCR",
        required=False,
    )

    class Meta:
        model = ConfiguracaoAPI
        fields = "__all__"

    def _manter_ou_remover(self, campo):
        if self.cleaned_data.get(f"remover_{campo}"):
            return ""
        return self.cleaned_data.get(campo) or getattr(self.instance, campo, "")

    def clean(self):
        dados = super().clean()
        for campo in ("gemini_api_key", "ocr_api_key"):
            dados[campo] = self._manter_ou_remover(campo)
        return dados


@admin.register(ConfiguracaoAPI)
class ConfiguracaoAPIAdmin(admin.ModelAdmin):
    form = ConfiguracaoAPIForm
    readonly_fields = ("situacao_gemini", "situacao_ocr")
    fieldsets = (
        (
            "IA de correção (Gemini)",
            {
                "fields": (
                    "situacao_gemini",
                    "gemini_api_key",
                    "remover_gemini_api_key",
                ),
            },
        ),
        (
            "OCR (OCR.space)",
            {
                "fields": (
                    "situacao_ocr",
                    "ocr_api_key",
                    "remover_ocr_api_key",
                ),
            },
        ),
    )

    @staticmethod
    def _mascarar(chave):
        return f"configurada (termina em …{chave[-4:]})" if chave else "não configurada"

    @admin.display(description="Chave atual")
    def situacao_gemini(self, obj):
        return self._mascarar(obj.gemini_api_key if obj else "")

    @admin.display(description="Chave atual")
    def situacao_ocr(self, obj):
        return self._mascarar(obj.ocr_api_key if obj else "")

    def has_add_permission(self, request):
        return not ConfiguracaoAPI.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        configuracao = ConfiguracaoAPI.objects.first() or ConfiguracaoAPI.objects.create()
        return redirect(
            reverse("admin:redacoes_configuracaoapi_change", args=[configuracao.pk])
        )


@admin.register(Redacao)
class RedacaoAdmin(admin.ModelAdmin):
    list_display = ("tema", "aluno", "status", "corrigido_por", "criada_em", "atualizada_em")
    list_filter = ("status", "criada_em")
    search_fields = ("tema", "texto_original", "texto_transcrito", "aluno__email")
    readonly_fields = ("criada_em", "atualizada_em", "corrigido_em")
    date_hierarchy = "criada_em"
    ordering = ("-criada_em",)

    fieldsets = (
        ("Entrada", {"fields": ("aluno", "tema", "imagem", "texto_original")}),
        (
            "Processamento",
            {
                "fields": (
                    "status",
                    "texto_transcrito",
                    "texto_revisado",
                    "resultado_json",
                    "resultado_professor",
                )
            },
        ),
        (
            "Correção do professor",
            {"fields": ("comentario_professor", "corrigido_por", "corrigido_em")},
        ),
        ("Datas", {"fields": ("criada_em", "atualizada_em")}),
    )
