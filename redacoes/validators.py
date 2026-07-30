from django.core.exceptions import ValidationError


TAMANHO_MAXIMO_IMAGEM = 10 * 1024 * 1024


def validar_tamanho_imagem(arquivo):
    if arquivo.size > TAMANHO_MAXIMO_IMAGEM:
        raise ValidationError("A imagem deve ter no máximo 10 MB.")
