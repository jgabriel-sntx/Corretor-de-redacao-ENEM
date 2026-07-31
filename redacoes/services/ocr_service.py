import logging
import os
from typing import Any

import httpx


logger = logging.getLogger(__name__)

URL_PADRAO = "https://api.ocr.space/Parse/Image"
ENGINE_PADRAO = "3"
IDIOMA_PADRAO = "auto"
TIMEOUT_PADRAO = 60.0


class OCRServiceError(Exception):
    """Erro esperado e seguro durante o reconhecimento de texto."""


class OCRConfigurationError(OCRServiceError):
    """Configuração local do OCR ausente ou inválida."""


class OCRAuthenticationError(OCRServiceError):
    """A chave do OCR foi recusada."""


class OCRQuotaError(OCRServiceError):
    """A cota do OCR foi atingida."""


class OCRTimeoutError(OCRServiceError):
    """O serviço de OCR não respondeu dentro do limite."""


class OCRResponseError(OCRServiceError):
    """O OCR respondeu com conteúdo inválido ou informou falha."""


def extrair_texto_documento(arquivo_imagem) -> str:
    """Envia uma imagem ao OCR.space e devolve apenas o texto reconhecido."""
    if not arquivo_imagem:
        raise ValueError("Uma imagem é obrigatória para executar o OCR.")

    chave_api, url, engine, idioma, timeout = _ler_configuracao()
    conteudo = _ler_imagem(arquivo_imagem)
    nome = getattr(arquivo_imagem, "name", "redacao.jpg")
    tipo = getattr(arquivo_imagem, "content_type", None) or "application/octet-stream"

    try:
        resposta = httpx.post(
            url,
            headers={"apikey": chave_api},
            files={"file": (nome, conteudo, tipo)},
            data={
                "OCREngine": engine,
                "language": idioma,
                "isOverlayRequired": "false",
                "detectOrientation": "true",
                "scale": "true",
            },
            timeout=timeout,
        )
    except httpx.TimeoutException as erro:
        logger.warning("OCR.space excedeu o tempo limite.")
        raise OCRTimeoutError(
            "O serviço de OCR demorou demais para responder. Tente novamente."
        ) from erro
    except httpx.RequestError as erro:
        logger.warning("Falha de comunicação com OCR.space: %s", type(erro).__name__)
        raise OCRServiceError(
            "Não foi possível acessar o serviço de OCR. Tente novamente mais tarde."
        ) from erro

    _validar_status_http(resposta)
    try:
        dados = resposta.json()
    except ValueError as erro:
        raise OCRResponseError(
            "O serviço de OCR retornou uma resposta inválida."
        ) from erro

    return _extrair_texto_resposta(dados)


def _ler_configuracao() -> tuple[str, str, str, str, float]:
    chave_api = os.getenv("OCR_SPACE_API_KEY", "").strip()
    url = os.getenv("OCR_SPACE_API_URL", URL_PADRAO).strip()
    engine = os.getenv("OCR_SPACE_ENGINE", ENGINE_PADRAO).strip()
    idioma = os.getenv("OCR_SPACE_LANGUAGE", IDIOMA_PADRAO).strip()

    if not chave_api or chave_api == "troque-pela-chave-do-ocr-space":
        raise OCRConfigurationError("OCR_SPACE_API_KEY não está configurada.")
    if not url.startswith("https://"):
        raise OCRConfigurationError("OCR_SPACE_API_URL deve usar HTTPS.")
    if engine not in {"1", "2", "3"}:
        raise OCRConfigurationError("OCR_SPACE_ENGINE deve ser 1, 2 ou 3.")

    try:
        timeout = float(os.getenv("OCR_SPACE_TIMEOUT_SECONDS", TIMEOUT_PADRAO))
    except ValueError as erro:
        raise OCRConfigurationError(
            "OCR_SPACE_TIMEOUT_SECONDS possui valor inválido."
        ) from erro
    if timeout <= 0:
        raise OCRConfigurationError("O timeout do OCR deve ser positivo.")

    return chave_api, url, engine, idioma, timeout


def _ler_imagem(arquivo_imagem) -> bytes:
    try:
        with arquivo_imagem.open("rb") as arquivo:
            return arquivo.read()
    except OSError as erro:
        logger.exception("Não foi possível ler a imagem armazenada.")
        raise OCRServiceError(
            "Não foi possível ler a imagem enviada para executar o OCR."
        ) from erro


def _validar_status_http(resposta: httpx.Response) -> None:
    if resposta.status_code in {401, 403}:
        raise OCRAuthenticationError("A chave do OCR.space foi recusada.")
    if resposta.status_code == 429:
        raise OCRQuotaError(
            "O limite de uso do OCR foi atingido. Tente novamente mais tarde."
        )
    if resposta.is_error:
        logger.warning("OCR.space falhou com código HTTP %s.", resposta.status_code)
        raise OCRServiceError(
            "Não foi possível acessar o serviço de OCR. Tente novamente mais tarde."
        )


def _extrair_texto_resposta(dados: Any) -> str:
    if not isinstance(dados, dict):
        raise OCRResponseError("O serviço de OCR retornou uma resposta inválida.")

    codigo = _inteiro_ou_none(dados.get("OCRExitCode"))
    if dados.get("IsErroredOnProcessing") is True or codigo in {3, 4}:
        raise OCRResponseError("O OCR.space não conseguiu processar esta imagem.")
    if codigo not in {1, 2}:
        raise OCRResponseError("O serviço de OCR retornou um código desconhecido.")

    resultados = dados.get("ParsedResults")
    if not isinstance(resultados, list):
        raise OCRResponseError("A resposta do OCR não contém resultados válidos.")

    textos = []
    resultados_processados = 0
    for resultado in resultados:
        if not isinstance(resultado, dict):
            raise OCRResponseError("A resposta do OCR contém um resultado inválido.")
        if _inteiro_ou_none(resultado.get("FileParseExitCode")) != 1:
            if codigo == 1:
                raise OCRResponseError("O OCR.space não conseguiu interpretar a imagem.")
            continue
        resultados_processados += 1
        texto = resultado.get("ParsedText")
        if texto is not None and not isinstance(texto, str):
            raise OCRResponseError("O texto retornado pelo OCR possui formato inválido.")
        if texto and texto.strip():
            textos.append(texto.strip())

    if not resultados_processados:
        raise OCRResponseError("O OCR.space não conseguiu interpretar a imagem.")

    return "\n\n".join(textos)


def _inteiro_ou_none(valor: Any) -> int | None:
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None
