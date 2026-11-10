from typing import Any

# Nome da configuração -> campo de ConfiguracaoAPI (editável no admin).
CAMPOS = {
    "GEMINI_API_KEY": "gemini_api_key",
    "OCR_SPACE_API_KEY": "ocr_api_key",
}


def valor(nome: str, padrao: Any = "") -> Any:
    """Chave definida no admin (Configuração das APIs); vazia usa o padrão."""
    from django.db import DatabaseError

    from redacoes.models import ConfiguracaoAPI

    try:
        configuracao = ConfiguracaoAPI.objects.first()
    except DatabaseError:  # migração ainda não aplicada
        configuracao = None

    do_admin = getattr(configuracao, CAMPOS[nome], None) if configuracao else None
    if do_admin not in (None, ""):
        return str(do_admin).strip()
    return padrao
