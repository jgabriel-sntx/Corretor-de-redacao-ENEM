import os
from unittest.mock import Mock, patch

import httpx
from django.test import SimpleTestCase

from .services.ai_service import (
    AIAPIError,
    AIConfigurationError,
    AIResponseError,
    avaliar_redacao,
)
from .services.prompt_builder import PromptResponseValidationError


TEMA = "Desafios da educação brasileira"
REDACAO = "A educação exige políticas públicas consistentes."


class AIServiceTests(SimpleTestCase):
    def setUp(self):
        self.ambiente = patch.dict(
            os.environ,
            {
                "NVIDIA_API_KEY": "chave-de-teste",
                "NVIDIA_API_URL": (
                    "https://integrate.api.nvidia.com/v1/chat/completions"
                ),
                "NVIDIA_MODEL": "meta/llama-3.1-8b-instruct",
                "NVIDIA_TIMEOUT_SECONDS": "120",
                "NVIDIA_MAX_OUTPUT_TOKENS": "3000",
            },
        )
        self.ambiente.start()
        self.addCleanup(self.ambiente.stop)
        self.sleep_patcher = patch("redacoes.services.ai_service.time.sleep")
        self.sleep_mock = self.sleep_patcher.start()
        self.addCleanup(self.sleep_patcher.stop)

    @staticmethod
    def resposta_mock(status=200, conteudo='{"schema_version":"1.0"}'):
        resposta = Mock(status_code=status, is_error=status >= 400)
        resposta.json.return_value = {
            "choices": [{"message": {"content": conteudo}}]
        }
        return resposta

    @patch("redacoes.services.ai_service.validar_resposta_correcao")
    @patch("redacoes.services.ai_service.httpx.post")
    def test_envia_prompt_e_retorna_json_validado(self, post_mock, validar_mock):
        post_mock.return_value = self.resposta_mock()
        validar_mock.return_value = {"schema_version": "1.0", "nota_total": 800}

        resultado = avaliar_redacao(TEMA, REDACAO)

        chamada = post_mock.call_args.kwargs
        self.assertEqual(
            chamada["headers"]["Authorization"], "Bearer chave-de-teste"
        )
        self.assertEqual(
            chamada["json"]["model"], "meta/llama-3.1-8b-instruct"
        )
        self.assertEqual(chamada["json"]["temperature"], 0)
        self.assertEqual(chamada["json"]["max_tokens"], 3000)
        self.assertFalse(chamada["json"]["stream"])
        self.assertEqual(chamada["json"]["messages"][0]["role"], "system")
        self.assertIn(
            "# HIERARQUIA E PAPEL",
            chamada["json"]["messages"][1]["content"],
        )
        self.assertEqual(chamada["timeout"], 120)
        validar_mock.assert_called_once_with('{"schema_version":"1.0"}', REDACAO)
        self.assertEqual(resultado["nota_total"], 800)

    @patch("redacoes.services.ai_service.httpx.post")
    def test_chave_ausente_e_rejeitada_antes_da_api(self, post_mock):
        with patch.dict(os.environ, {"NVIDIA_API_KEY": ""}):
            with self.assertRaises(AIConfigurationError):
                avaliar_redacao(TEMA, REDACAO)

        post_mock.assert_not_called()

    def test_modelo_invalido_e_rejeitado(self):
        with patch.dict(os.environ, {"NVIDIA_MODEL": "modelo com espaços"}):
            with self.assertRaises(AIConfigurationError):
                avaliar_redacao(TEMA, REDACAO)

    @patch("redacoes.services.ai_service.httpx.post")
    def test_erro_de_cota_e_convertido_em_erro_seguro(self, post_mock):
        post_mock.return_value = self.resposta_mock(status=429)

        with self.assertRaisesRegex(AIAPIError, "cota") as contexto:
            avaliar_redacao(TEMA, REDACAO)

        self.assertEqual(contexto.exception.codigo, "limite_api")
        self.assertEqual(contexto.exception.status_http, 429)
        self.assertEqual(post_mock.call_count, 2)

    @patch("redacoes.services.ai_service.httpx.post")
    def test_erro_de_autenticacao_e_classificado(self, post_mock):
        post_mock.return_value = self.resposta_mock(status=403)

        with self.assertRaises(AIAPIError) as contexto:
            avaliar_redacao(TEMA, REDACAO)

        self.assertEqual(contexto.exception.codigo, "autenticacao")

    @patch("redacoes.services.ai_service.httpx.post")
    def test_timeout_e_classificado(self, post_mock):
        post_mock.side_effect = httpx.ReadTimeout("detalhe interno")

        with self.assertRaises(AIAPIError) as contexto:
            avaliar_redacao(TEMA, REDACAO)

        self.assertEqual(contexto.exception.codigo, "timeout")
        self.assertNotIn("detalhe interno", str(contexto.exception))
        self.assertEqual(post_mock.call_count, 1)

    @patch("redacoes.services.ai_service.httpx.post")
    def test_sobrecarga_da_nvidia_e_classificada(self, post_mock):
        post_mock.return_value = self.resposta_mock(status=529)

        with self.assertRaises(AIAPIError) as contexto:
            avaliar_redacao(TEMA, REDACAO)

        self.assertEqual(contexto.exception.codigo, "servico_indisponivel")
        self.assertEqual(contexto.exception.status_http, 529)
        self.assertEqual(post_mock.call_count, 2)

    @patch("redacoes.services.ai_service.httpx.post")
    def test_resposta_vazia_e_rejeitada(self, post_mock):
        post_mock.return_value = self.resposta_mock(conteudo="")

        with self.assertRaises(AIResponseError):
            avaliar_redacao(TEMA, REDACAO)

    @patch("redacoes.services.ai_service.httpx.post")
    def test_envelope_invalido_e_rejeitado(self, post_mock):
        resposta = self.resposta_mock()
        resposta.json.return_value = {"resultado": "inesperado"}
        post_mock.return_value = resposta

        with self.assertRaises(AIResponseError):
            avaliar_redacao(TEMA, REDACAO)

    @patch(
        "redacoes.services.ai_service.validar_resposta_correcao",
        side_effect=PromptResponseValidationError(
            "JSON inválido", codigo="json_invalido"
        ),
    )
    @patch("redacoes.services.ai_service.httpx.post")
    def test_resposta_fora_do_contrato_preserva_codigo(
        self, post_mock, validar_mock
    ):
        post_mock.return_value = self.resposta_mock(conteudo='{"campo":"errado"}')

        with self.assertRaises(AIResponseError) as contexto:
            avaliar_redacao(TEMA, REDACAO)

        self.assertEqual(contexto.exception.codigo, "json_invalido")
        self.assertEqual(post_mock.call_count, 2)

    @patch("redacoes.services.ai_service.validar_resposta_correcao")
    @patch("redacoes.services.ai_service.httpx.post")
    def test_primeira_resposta_invalida_e_corrigida_uma_vez(
        self, post_mock, validar_mock
    ):
        post_mock.side_effect = [
            self.resposta_mock(conteudo='{"tentativa":1}'),
            self.resposta_mock(conteudo='{"tentativa":2}'),
        ]
        validar_mock.side_effect = [
            PromptResponseValidationError(
                "Trecho inexistente",
                codigo="trecho_inexistente",
                caminho="competencias[0].evidencias[0].trecho",
            ),
            {"schema_version": "1.0", "nota_total": 600},
        ]

        resultado = avaliar_redacao(TEMA, REDACAO)

        self.assertEqual(resultado["nota_total"], 600)
        self.assertEqual(post_mock.call_count, 2)
        segunda_chamada = post_mock.call_args_list[1].kwargs["json"]["messages"]
        self.assertEqual(segunda_chamada[-2]["role"], "assistant")
        self.assertIn("trecho_inexistente", segunda_chamada[-1]["content"])
