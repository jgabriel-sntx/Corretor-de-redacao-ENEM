import logging
import os
import re
from typing import Any

from google import genai
from google.genai import errors, types

from .prompt_builder import (
    PromptInputError,
    PromptResponseValidationError,
    construir_prompt_correcao,
    validar_resposta_correcao,
)


logger = logging.getLogger(__name__)

MODELO_PADRAO = "gemini-3.6-flash"
TIMEOUT_MS = 60_000
MAX_OUTPUT_TOKENS = 16_384
PADRAO_MODELO = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,199}$")


class GeminiServiceError(Exception):
    """Erro esperado e seguro na integração com o Gemini."""


class GeminiConfigurationError(GeminiServiceError):
    """Configuração local ausente ou inválida."""


class GeminiInputError(GeminiServiceError):
    """Tema ou redação inadequados para a avaliação."""


class GeminiAPIError(GeminiServiceError):
    """Falha de comunicação ou rejeição pela API."""

    def __init__(self, mensagem: str, *, codigo: str, status_http: int | None) -> None:
        super().__init__(mensagem)
        self.codigo = codigo
        self.status_http = status_http


class GeminiResponseError(GeminiServiceError):
    """Resposta vazia, inválida ou fora do contrato JSON."""

    def __init__(self, mensagem: str, *, codigo: str = "resposta_invalida") -> None:
        super().__init__(mensagem)
        self.codigo = codigo


def avaliar_redacao_com_gemini(tema: str, redacao: str) -> dict[str, Any]:
    """Envia o prompt ao Gemini e devolve somente JSON localmente validado."""
    chave_api, modelo = _ler_configuracao()

    try:
        prompt = construir_prompt_correcao(tema, redacao)
    except PromptInputError as erro:
        raise GeminiInputError(
            "Tema ou redação inválidos para construir a avaliação."
        ) from erro

    try:
        with genai.Client(
            api_key=chave_api,
            http_options=types.HttpOptions(timeout=TIMEOUT_MS),
        ) as cliente:
            resposta = cliente.models.generate_content(
                model=modelo,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0,
                    candidate_count=1,
                    max_output_tokens=MAX_OUTPUT_TOKENS,
                ),
            )
    except errors.APIError as erro:
        codigo = getattr(erro, "code", None)
        logger.warning("Gemini API falhou com código %s.", codigo)
        categoria, mensagem = _classificar_erro_api(codigo)
        raise GeminiAPIError(
            mensagem, codigo=categoria, status_http=codigo
        ) from erro

    try:
        texto_resposta = resposta.text
    except (AttributeError, ValueError) as erro:
        raise GeminiResponseError(
            "O Gemini não retornou uma resposta textual utilizável."
        ) from erro

    if not isinstance(texto_resposta, str) or not texto_resposta.strip():
        raise GeminiResponseError("O Gemini retornou uma resposta vazia.")

    try:
        return validar_resposta_correcao(texto_resposta, redacao)
    except PromptResponseValidationError as erro:
        logger.warning("Resposta do Gemini rejeitada pelo contrato local.")
        raise GeminiResponseError(
            "A resposta do Gemini não corresponde ao formato esperado.",
            codigo=erro.codigo,
        ) from erro


def _ler_configuracao() -> tuple[str, str]:
    chave_api = os.getenv("GEMINI_API_KEY", "").strip()
    modelo = os.getenv("GEMINI_MODEL", MODELO_PADRAO).strip()

    if not chave_api or chave_api == "troque-pela-chave-do-gemini":
        raise GeminiConfigurationError(
            "GEMINI_API_KEY não está configurada no ambiente."
        )
    if not modelo or not PADRAO_MODELO.fullmatch(modelo):
        raise GeminiConfigurationError("GEMINI_MODEL possui um valor inválido.")

    return chave_api, modelo


def _classificar_erro_api(codigo: int | None) -> tuple[str, str]:
    if codigo in {401, 403}:
        return "autenticacao", "A chave do Gemini foi recusada ou não possui permissão."
    if codigo == 404:
        return "modelo_indisponivel", "O modelo Gemini configurado não foi encontrado."
    if codigo == 429:
        return "limite_api", "A cota do Gemini foi atingida. Tente novamente mais tarde."
    return "erro_api", "Não foi possível acessar o Gemini. Tente novamente mais tarde."
