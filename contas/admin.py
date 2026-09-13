from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Turma, Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    ordering = ("email",)
    list_display = ("email", "first_name", "tipo", "turma", "is_staff", "is_active")
    list_filter = ("tipo", "is_staff", "is_active")
    search_fields = ("email", "first_name")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Dados pessoais", {"fields": ("first_name", "tipo", "turma")}),
        (
            "Permissões",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Datas importantes", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "first_name",
                    "tipo",
                    "turma",
                    "password1",
                    "password2",
                ),
            },
        ),
    )


@admin.register(Turma)
class TurmaAdmin(admin.ModelAdmin):
    list_display = ("nome", "codigo", "professor", "criada_em")
    search_fields = ("nome", "codigo", "professor__email")
    readonly_fields = ("codigo", "criada_em")
