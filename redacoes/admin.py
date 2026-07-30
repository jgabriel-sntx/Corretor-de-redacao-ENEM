from django.contrib import admin

from .models import Redacao


@admin.register(Redacao)
class RedacaoAdmin(admin.ModelAdmin):
    list_display = ("tema", "status", "criada_em", "atualizada_em")
    list_filter = ("status", "criada_em")
    search_fields = ("tema", "texto_original", "texto_transcrito")
    readonly_fields = ("criada_em", "atualizada_em")
    date_hierarchy = "criada_em"
    ordering = ("-criada_em",)

    fieldsets = (
        ("Entrada", {"fields": ("tema", "imagem", "texto_original")}),
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
        ("Datas", {"fields": ("criada_em", "atualizada_em")}),
    )
