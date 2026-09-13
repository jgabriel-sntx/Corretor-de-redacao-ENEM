from django.contrib import admin

from .models import Redacao


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
                )
            },
        ),
        (
            "Correção do professor",
            {"fields": ("comentario_professor", "corrigido_por", "corrigido_em")},
        ),
        ("Datas", {"fields": ("criada_em", "atualizada_em")}),
    )
