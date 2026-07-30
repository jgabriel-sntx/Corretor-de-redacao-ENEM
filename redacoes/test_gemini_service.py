import os
from unittest.mock import Mock, patch

from django.test import SimpleTestCase
from google.genai import errors

from .services.gemini_service import (
    GeminiAPIError,
    GeminiConfigurationError,
    GeminiResponseError,
    avaliar_redacao_com_gemini,
)
from .services.prompt_builder import PromptResponseValidationError


TEMA = "Desafios da educação brasileira"
REDACAO = "A educação exige políticas públicas consistentes."


class GeminiServiceTests(SimpleTestCase):
    @patch("redacoes.services.gemini_service.validar_resposta_correcao")
    @patch("redacoes.services.gemini_service.genai.Client")
    def test_le_configuracao_envia_prompt_e_retorna_json_validado(
        self, cliente_classe, validar_resposta
    ):
        cliente = Mock()
        cliente_classe.return_value.__enter__.return_value = cliente
        cliente.models.generate_content.return_value.text = '{"schema_version":"1.0"}'
        validar_resposta.return_value = {"schema_version": "1.0", "nota_total": 800}

        with patch.dict(
            os.environ,
            {"GEMINI_API_KEY": "chave-de-teste", "GEMINI_MODEL": "modelo-teste"},
        ):
            resultado = avaliar_redacao_com_gemini(TEMA, REDACAO)

        cliente_classe.assert_called_once()
        chamada = cliente.models.generate_content.call_args.kwargs
        self.assertEqual(chamada["model"], "modelo-teste")
        self.assertIn("# HIERARQUIA E PAPEL", chamada["contents"])
        self.assertEqual(chamada["config"].response_mime_type, "application/json")
        self.assertEqual(chamada["config"].temperature, 0)
        validar_resposta.assert_called_once_with(
            '{"schema_version":"1.0"}',
            REDACAO,
        )
        self.assertEqual(resultado["nota_total"], 800)
        cliente_classe.return_value.__exit__.assert_called_once()

    @patch("redacoes.services.gemini_service.genai.Client")
    def test_chave_ausente_e_rejeitada_antes_da_api(self, cliente_classe):
        with patch.dict(
            os.environ,
            {"GEMINI_API_KEY": "", "GEMINI_MODEL": "gemini-3.6-flash"},
        ):
            with self.assertRaises(GeminiConfigurationError):
                avaliar_redacao_com_gemini(TEMA, REDACAO)

        cliente_classe.assert_not_called()

    def test_modelo_invalido_e_rejeitado(self):
        with patch.dict(
            os.environ,
            {"GEMINI_API_KEY": "chave", "GEMINI_MODEL": "modelo com espaços"},
        ):
            with self.assertRaises(GeminiConfigurationError):
                avaliar_redacao_com_gemini(TEMA, REDACAO)

    @patch("redacoes.services.gemini_service.genai.Client")
    def test_erro_de_cota_e_convertido_em_erro_seguro(self, cliente_classe):
        cliente = Mock()
        cliente_classe.return_value.__enter__.return_value = cliente
        cliente.models.generate_content.side_effect = errors.ClientError(
            429,
            {"message": "detalhe interno da cota"},
        )

        with patch.dict(
            os.environ,
            {"GEMINI_API_KEY": "chave", "GEMINI_MODEL": "gemini-3.6-flash"},
        ):
            with self.assertRaisesRegex(GeminiAPIError, "cota") as contexto:
                avaliar_redacao_com_gemini(TEMA, REDACAO)

        self.assertEqual(contexto.exception.codigo, "limite_api")
        self.assertEqual(contexto.exception.status_http, 429)

    @patch("redacoes.services.gemini_service.genai.Client")
    def test_erro_de_autenticacao_e_classificado(self, cliente_classe):
        cliente = Mock()
        cliente_classe.return_value.__enter__.return_value = cliente
        cliente.models.generate_content.side_effect = errors.ClientError(
            403, {"message": "detalhe interno"}
        )

        with patch.dict(
            os.environ,
            {"GEMINI_API_KEY": "chave", "GEMINI_MODEL": "gemini-3.6-flash"},
        ):
            with self.assertRaises(GeminiAPIError) as contexto:
                avaliar_redacao_com_gemini(TEMA, REDACAO)

        self.assertEqual(contexto.exception.codigo, "autenticacao")
        self.assertNotIn("detalhe interno", str(contexto.exception))

    @patch("redacoes.services.gemini_service.genai.Client")
    def test_resposta_vazia_e_rejeitada(self, cliente_classe):
        cliente = Mock()
        cliente_classe.return_value.__enter__.return_value = cliente
        cliente.models.generate_content.return_value.text = ""

        with patch.dict(
            os.environ,
            {"GEMINI_API_KEY": "chave", "GEMINI_MODEL": "gemini-3.6-flash"},
        ):
            with self.assertRaises(GeminiResponseError) as contexto:
                avaliar_redacao_com_gemini(TEMA, REDACAO)

        self.assertEqual(contexto.exception.codigo, "resposta_invalida")

    @patch(
        "redacoes.services.gemini_service.validar_resposta_correcao",
        side_effect=PromptResponseValidationError(
            "JSON inválido", codigo="json_invalido"
        ),
    )
    @patch("redacoes.services.gemini_service.genai.Client")
    def test_resposta_fora_do_contrato_e_rejeitada(
        self, cliente_classe, validar_resposta
    ):
        cliente = Mock()
        cliente_classe.return_value.__enter__.return_value = cliente
        cliente.models.generate_content.return_value.text = '{"campo":"errado"}'

        with patch.dict(
            os.environ,
            {"GEMINI_API_KEY": "chave", "GEMINI_MODEL": "gemini-3.6-flash"},
        ):
            with self.assertRaises(GeminiResponseError) as contexto:
                avaliar_redacao_com_gemini(TEMA, REDACAO)

        self.assertEqual(contexto.exception.codigo, "json_invalido")
