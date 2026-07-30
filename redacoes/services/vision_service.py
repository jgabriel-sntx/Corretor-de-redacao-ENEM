import logging

from google.api_core.exceptions import GoogleAPICallError, ResourceExhausted, RetryError
from google.auth.exceptions import DefaultCredentialsError
from google.cloud import vision


logger = logging.getLogger(__name__)


class VisionServiceError(Exception):
    """Erro esperado durante a comunicação com o Google Cloud Vision."""


class VisionCredentialsError(VisionServiceError):
    """Credenciais do Google Cloud ausentes ou inválidas."""


class VisionQuotaError(VisionServiceError):
    """Cota do Google Cloud Vision esgotada."""


def extrair_texto_documento(arquivo_imagem):
    """Extrai texto denso de uma imagem usando DOCUMENT_TEXT_DETECTION."""
    if not arquivo_imagem:
        raise ValueError("Uma imagem é obrigatória para executar o OCR.")

    try:
        with arquivo_imagem.open("rb") as arquivo:
            conteudo = arquivo.read()
    except OSError as erro:
        logger.exception("Não foi possível ler a imagem armazenada.")
        raise VisionServiceError(
            "Não foi possível ler a imagem enviada para executar o OCR."
        ) from erro

    try:
        cliente = vision.ImageAnnotatorClient()
        imagem = vision.Image(content=conteudo)
        resposta = cliente.document_text_detection(image=imagem, timeout=30)
    except DefaultCredentialsError as erro:
        logger.exception("Credenciais do Google Cloud Vision não configuradas.")
        raise VisionCredentialsError(
            "O serviço de OCR não está autenticado. Configure as credenciais do Google Cloud."
        ) from erro
    except ResourceExhausted as erro:
        logger.exception("Cota do Google Cloud Vision esgotada.")
        raise VisionQuotaError(
            "O limite de uso do OCR foi atingido. Tente novamente mais tarde."
        ) from erro
    except (GoogleAPICallError, RetryError) as erro:
        logger.exception("Falha na chamada ao Google Cloud Vision.")
        raise VisionServiceError(
            "Não foi possível acessar o serviço de OCR. Tente novamente mais tarde."
        ) from erro

    if resposta.error.message:
        logger.error("Google Cloud Vision retornou erro: %s", resposta.error.message)
        raise VisionServiceError(
            "O Google Cloud Vision não conseguiu processar esta imagem."
        )

    return resposta.full_text_annotation.text.strip()
