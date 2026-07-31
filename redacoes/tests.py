from io import BytesIO
from datetime import timedelta
import os
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

import httpx
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from django.urls import reverse
from PIL import Image

from .forms import RedacaoForm, RevisaoTranscricaoForm
from .models import Redacao
from .services.ai_service import AIServiceError
from .services.ocr_service import (
    OCRAuthenticationError,
    OCRConfigurationError,
    OCRQuotaError,
    OCRResponseError,
    OCRServiceError,
    OCRTimeoutError,
    extrair_texto_documento,
)
from .services.prompt_builder import NOMES_COMPETENCIAS
from .validators import TAMANHO_MAXIMO_IMAGEM, validar_tamanho_imagem


def criar_imagem_png():
    conteudo = BytesIO()
    Image.new("RGB", (10, 10), "white").save(conteudo, format="PNG")
    return SimpleUploadedFile(
        "redacao.png",
        conteudo.getvalue(),
        content_type="image/png",
    )


def criar_resultado_avaliacao():
    return {
        "schema_version": "1.0",
        "avaliacao_possivel": True,
        "motivo_impedimento": None,
        "situacoes_nota_zero": [],
        "competencias": [
            {
                "numero": numero,
                "nome": NOMES_COMPETENCIAS[numero],
                "nota": 160,
                "justificativa": f"Justificativa da competência {numero}.",
                "evidencias": [],
                "pontos_fortes": [f"Ponto forte {numero}."],
                "melhorias": [f"Melhoria {numero}."],
            }
            for numero in range(1, 6)
        ],
        "nota_total": 800,
        "proposta_intervencao": {
            "presente": True,
            "agente": "Escolas",
            "acao": "Criar clubes de leitura",
            "meio_modo": "Encontros semanais",
            "finalidade": "Ampliar o acesso aos livros",
            "detalhamento": "Com acompanhamento dos professores",
            "respeita_direitos_humanos": True,
            "evidencias": [],
        },
        "diagnostico_geral": "A redação apresenta uma argumentação consistente.",
        "prioridades_melhoria": ["Aprofundar os argumentos."],
        "confianca": "media",
        "limitacoes": ["Textos motivadores não fornecidos."],
    }


class RedacaoModelTests(TestCase):
    def test_valores_padrao_e_representacao(self):
        redacao = Redacao.objects.create(
            tema="Tema para redação",
            texto_original="Conteúdo suficiente.",
        )

        self.assertEqual(redacao.status, Redacao.Status.ENVIADA)
        self.assertEqual(redacao.resultado_json, {})
        self.assertEqual(str(redacao), "Tema para redação")
        self.assertIsNotNone(redacao.criada_em)
        self.assertIsNotNone(redacao.atualizada_em)

    def test_clean_remove_espacos_de_tema_e_texto(self):
        redacao = Redacao(
            tema="  Tema normalizado  ",
            texto_original="  Texto normalizado.  ",
        )

        redacao.full_clean()

        self.assertEqual(redacao.tema, "Tema normalizado")
        self.assertEqual(redacao.texto_original, "Texto normalizado.")

    def test_exige_imagem_ou_texto_original(self):
        redacao = Redacao(tema="Tema sem conteúdo")

        with self.assertRaises(ValidationError) as contexto:
            redacao.full_clean()

        self.assertIn("Informe uma imagem", str(contexto.exception))

    def test_tema_respeita_tamanho_minimo(self):
        redacao = Redacao(tema="abc", texto_original="Texto presente.")

        with self.assertRaises(ValidationError) as contexto:
            redacao.full_clean()

        self.assertIn("tema", contexto.exception.message_dict)

    def test_ordenacao_padrao_exibe_mais_recente_primeiro(self):
        antiga = Redacao.objects.create(tema="Tema antigo", texto_original="Texto.")
        recente = Redacao.objects.create(tema="Tema recente", texto_original="Texto.")
        agora = timezone.now()
        Redacao.objects.filter(pk=antiga.pk).update(criada_em=agora - timedelta(days=1))
        Redacao.objects.filter(pk=recente.pk).update(criada_em=agora)

        self.assertEqual(list(Redacao.objects.all()), [recente, antiga])


class RedacaoFormTests(TestCase):
    def test_formulario_aceita_envio_apenas_com_texto(self):
        form = RedacaoForm(
            data={"tema": "Tema válido", "texto_original": "  Redação digitada.  "}
        )

        self.assertTrue(form.is_valid(), form.errors)
        redacao = form.save()
        self.assertEqual(redacao.texto_original, "Redação digitada.")

    def test_formulario_aceita_envio_apenas_com_imagem(self):
        form = RedacaoForm(
            data={"tema": "Tema por imagem"},
            files={"imagem": criar_imagem_png()},
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_formulario_rejeita_ausencia_de_imagem_e_texto(self):
        form = RedacaoForm(data={"tema": "Tema incompleto"})

        self.assertFalse(form.is_valid())
        self.assertIn("__all__", form.errors)

    def test_formulario_rejeita_arquivo_que_nao_e_imagem(self):
        arquivo = SimpleUploadedFile("arquivo.txt", b"texto", content_type="text/plain")
        form = RedacaoForm(data={"tema": "Tema válido"}, files={"imagem": arquivo})

        self.assertFalse(form.is_valid())
        self.assertIn("imagem", form.errors)

    def test_validador_rejeita_imagem_acima_de_dez_megabytes(self):
        arquivo = Mock(size=TAMANHO_MAXIMO_IMAGEM + 1)

        with self.assertRaisesRegex(ValidationError, "1 MB"):
            validar_tamanho_imagem(arquivo)

    def test_formulario_revisao_remove_espacos_e_exige_texto(self):
        redacao = Redacao.objects.create(
            tema="Tema em revisão", texto_original="Texto original."
        )
        valido = RevisaoTranscricaoForm(
            data={"texto_revisado": "  Texto revisto.  "}, instance=redacao
        )
        vazio = RevisaoTranscricaoForm(
            data={"texto_revisado": "   "}, instance=redacao
        )

        self.assertTrue(valido.is_valid(), valido.errors)
        self.assertEqual(valido.cleaned_data["texto_revisado"], "Texto revisto.")
        self.assertFalse(vazio.is_valid())
        self.assertIn("texto_revisado", vazio.errors)


class PaginaInicialTests(TestCase):
    def setUp(self):
        self.url = reverse("redacoes:inicio")

    def test_pagina_inicial_exibe_formulario(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nova redação")
        self.assertContains(response, 'enctype="multipart/form-data"')
        self.assertContains(response, 'name="tema"')
        self.assertContains(response, 'name="imagem"')
        self.assertContains(response, 'name="texto_original"')

    def test_envio_por_texto_salva_e_redireciona(self):
        response = self.client.post(
            self.url,
            {
                "tema": "Desafios da educação brasileira",
                "texto_original": "Texto da redação para armazenamento.",
            },
        )

        self.assertEqual(Redacao.objects.count(), 1)
        redacao = Redacao.objects.get()
        self.assertRedirects(
            response,
            reverse("redacoes:revisao", kwargs={"pk": redacao.pk}),
            fetch_redirect_response=False,
        )

    @patch("redacoes.views.extrair_texto_documento")
    def test_envio_por_texto_nao_chama_ocr(self, mock_ocr):
        self.client.post(
            self.url,
            {"tema": "Tema somente texto", "texto_original": "Texto digitado."},
        )

        mock_ocr.assert_not_called()

    def test_metodo_http_nao_permitido_retorna_405(self):
        self.assertEqual(self.client.put(self.url).status_code, 405)

    def test_envio_invalido_exibe_erros_e_nao_salva(self):
        response = self.client.post(self.url, {"tema": "Tema sem conteúdo"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Redacao.objects.count(), 0)
        self.assertContains(response, "Informe uma imagem da redação ou o texto original")
        self.assertContains(response, "Não foi possível enviar a redação")

    def test_arquivo_que_nao_e_imagem_nao_salva(self):
        arquivo = SimpleUploadedFile(
            "redacao.txt",
            b"conteudo sem formato de imagem",
            content_type="text/plain",
        )

        response = self.client.post(
            self.url,
            {"tema": "Tema válido", "imagem": arquivo},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Redacao.objects.count(), 0)
        self.assertContains(response, "Envie uma imagem válida")

    @patch(
        "redacoes.views.extrair_texto_documento",
        return_value="Texto reconhecido pelo OCR.space.",
    )
    def test_envio_com_imagem_executa_ocr_e_salva_transcricao(self, mock_ocr):
        with TemporaryDirectory() as pasta_media, self.settings(
            MEDIA_ROOT=pasta_media
        ):
            response = self.client.post(
                self.url,
                {"tema": "Tema enviado por imagem", "imagem": criar_imagem_png()},
            )

        redacao = Redacao.objects.get()
        mock_ocr.assert_called_once()
        self.assertEqual(
            redacao.texto_transcrito,
            "Texto reconhecido pelo OCR.space.",
        )
        self.assertEqual(redacao.status, Redacao.Status.CONCLUIDA)
        self.assertRedirects(
            response,
            reverse("redacoes:revisao", kwargs={"pk": redacao.pk}),
            fetch_redirect_response=False,
        )

    @patch(
        "redacoes.views.extrair_texto_documento",
        side_effect=OCRServiceError("Falha controlada no OCR."),
    )
    def test_falha_do_ocr_preserva_redacao_e_marca_erro(self, mock_ocr):
        with TemporaryDirectory() as pasta_media, self.settings(
            MEDIA_ROOT=pasta_media
        ):
            response = self.client.post(
                self.url,
                {"tema": "Tema com falha no OCR", "imagem": criar_imagem_png()},
                follow=True,
            )

        redacao = Redacao.objects.get()
        mock_ocr.assert_called_once()
        self.assertEqual(redacao.status, Redacao.Status.ERRO)
        self.assertEqual(redacao.texto_transcrito, "")
        self.assertContains(response, "Falha controlada no OCR")


class PaginaRevisaoTests(TestCase):
    def setUp(self):
        self.redacao = Redacao.objects.create(
            tema="Desafios da educação brasileira",
            imagem="redacoes/2026/07/redacao-teste.png",
            texto_transcrito="Primeiro parágrafo do OCR.\n\nSegundo parágrafo.",
            status=Redacao.Status.CONCLUIDA,
        )
        self.url = reverse("redacoes:revisao", kwargs={"pk": self.redacao.pk})

    def test_revisao_exibe_imagem_ocr_textarea_e_botao(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.redacao.tema)
        self.assertContains(response, self.redacao.imagem.url)
        self.assertContains(response, "Primeiro parágrafo do OCR")
        self.assertContains(response, 'name="texto_revisado"')
        self.assertContains(response, "Confirmar texto")
        self.assertContains(response, self.redacao.texto_transcrito)

    def test_get_inicializa_textarea_com_texto_ocr(self):
        response = self.client.get(self.url)

        self.assertEqual(
            response.context["form"].initial["texto_revisado"],
            self.redacao.texto_transcrito,
        )

    @patch(
        "redacoes.views.avaliar_redacao",
        return_value={"schema_version": "1.0", "nota_total": 800},
    )
    def test_confirmar_salva_texto_revisado_sem_alterar_ocr(self, mock_ia):
        texto_ocr_original = self.redacao.texto_transcrito
        texto_corrigido = "Primeiro parágrafo corrigido.\n\nSegundo parágrafo."

        response = self.client.post(
            self.url,
            {"texto_revisado": texto_corrigido},
        )

        self.redacao.refresh_from_db()
        self.assertEqual(self.redacao.texto_revisado, texto_corrigido)
        self.assertEqual(self.redacao.texto_transcrito, texto_ocr_original)
        self.assertEqual(self.redacao.resultado_json["nota_total"], 800)
        mock_ia.assert_called_once_with(self.redacao.tema, texto_corrigido)
        self.assertRedirects(
            response,
            reverse("redacoes:resultado", kwargs={"pk": self.redacao.pk}),
            fetch_redirect_response=False,
        )

    @patch(
        "redacoes.views.avaliar_redacao",
        return_value={"schema_version": "1.0"},
    )
    def test_confirmacao_exibe_mensagem_apos_redirect(self, mock_ia):
        response = self.client.post(
            self.url,
            {"texto_revisado": "Transcrição confirmada."},
            follow=True,
        )

        self.assertRedirects(
            response,
            reverse("redacoes:resultado", kwargs={"pk": self.redacao.pk}),
        )
        self.assertContains(response, "avaliação estruturada concluída")

    @patch(
        "redacoes.views.avaliar_redacao",
        side_effect=AIServiceError("Falha controlada da NVIDIA."),
    )
    def test_falha_da_ia_preserva_revisao_e_limpa_resultado_antigo(
        self, mock_ia
    ):
        self.redacao.resultado_json = {"nota_total": 1000}
        self.redacao.save(update_fields=["resultado_json"])

        response = self.client.post(
            self.url,
            {"texto_revisado": "Texto humano confirmado."},
            follow=True,
        )

        self.redacao.refresh_from_db()
        self.assertEqual(self.redacao.texto_revisado, "Texto humano confirmado.")
        self.assertEqual(self.redacao.resultado_json, {})
        self.assertContains(response, "Falha controlada da NVIDIA")

    def test_texto_revisado_vazio_nao_e_salvo(self):
        response = self.client.post(self.url, {"texto_revisado": "   "})

        self.redacao.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.redacao.texto_revisado, "")
        self.assertContains(response, "Revise e confirme um texto não vazio")

    @patch("redacoes.views.avaliar_redacao")
    def test_texto_invalido_nao_chama_ia(self, mock_ia):
        self.client.post(self.url, {"texto_revisado": "   "})

        mock_ia.assert_not_called()

    def test_metodo_http_nao_permitido_retorna_405(self):
        self.assertEqual(self.client.delete(self.url).status_code, 405)

    def test_revisao_inexistente_retorna_404(self):
        response = self.client.get(
            reverse("redacoes:revisao", kwargs={"pk": 999999})
        )

        self.assertEqual(response.status_code, 404)

    def test_mensagem_de_sucesso_aparece_na_revisao(self):
        response = self.client.post(
            reverse("redacoes:inicio"),
            {
                "tema": "Mobilidade nas cidades brasileiras",
                "texto_original": "Conteúdo enviado pelo formulário.",
            },
            follow=True,
        )

        nova_redacao = Redacao.objects.get(tema="Mobilidade nas cidades brasileiras")
        self.assertRedirects(
            response,
            reverse("redacoes:revisao", kwargs={"pk": nova_redacao.pk}),
        )
        self.assertContains(response, "Redação salva com sucesso")


class PaginaResultadoTests(TestCase):
    def setUp(self):
        self.redacao = Redacao.objects.create(
            tema="A importância da leitura",
            texto_original="Texto original.",
            texto_revisado="Texto revisado.",
            resultado_json=criar_resultado_avaliacao(),
        )
        self.url = reverse(
            "redacoes:resultado", kwargs={"pk": self.redacao.pk}
        )

    def test_resultado_exibe_nota_competencias_e_diagnostico(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Resultado da redação")
        self.assertContains(response, "800")
        self.assertContains(response, "de 1000")
        self.assertContains(response, "Justificativa da competência 1")
        self.assertContains(response, "Justificativa da competência 5")
        self.assertContains(response, "Aprofundar os argumentos")
        self.assertContains(response, "Criar clubes de leitura")
        self.assertContains(response, "Confiança: media")

    def test_resultado_oferece_revisao_e_nova_redacao(self):
        response = self.client.get(self.url)

        self.assertContains(
            response,
            reverse("redacoes:revisao", kwargs={"pk": self.redacao.pk}),
        )
        self.assertContains(response, reverse("redacoes:inicio"))

    def test_sem_resultado_redireciona_para_revisao(self):
        self.redacao.resultado_json = {}
        self.redacao.save(update_fields=["resultado_json"])

        response = self.client.get(self.url, follow=True)

        self.assertRedirects(
            response,
            reverse("redacoes:revisao", kwargs={"pk": self.redacao.pk}),
        )
        self.assertContains(response, "ainda não possui uma avaliação concluída")

    def test_resultado_inexistente_retorna_404(self):
        response = self.client.get(
            reverse("redacoes:resultado", kwargs={"pk": 999999})
        )

        self.assertEqual(response.status_code, 404)

    def test_resultado_aceita_apenas_get(self):
        self.assertEqual(self.client.post(self.url).status_code, 405)

    def test_avaliacao_impossivel_exibe_motivo(self):
        resultado = criar_resultado_avaliacao()
        resultado["avaliacao_possivel"] = False
        resultado["motivo_impedimento"] = "Texto insuficiente para avaliação."
        resultado["nota_total"] = None
        for competencia in resultado["competencias"]:
            competencia["nota"] = None
        self.redacao.resultado_json = resultado
        self.redacao.save(update_fields=["resultado_json"])

        response = self.client.get(self.url)

        self.assertContains(response, "Não foi possível atribuir notas")
        self.assertContains(response, "Texto insuficiente para avaliação")


class OCRServiceTests(TestCase):
    def setUp(self):
        self.ambiente = patch.dict(
            os.environ,
            {
                "OCR_SPACE_API_KEY": "chave-teste",
                "OCR_SPACE_API_URL": "https://api.ocr.space/Parse/Image",
                "OCR_SPACE_ENGINE": "3",
                "OCR_SPACE_LANGUAGE": "auto",
                "OCR_SPACE_TIMEOUT_SECONDS": "60",
            },
        )
        self.ambiente.start()
        self.addCleanup(self.ambiente.stop)

    @staticmethod
    def resposta_mock(status=200, dados=None):
        resposta = Mock(status_code=status, is_error=status >= 400)
        resposta.json.return_value = dados
        return resposta

    @patch("redacoes.services.ocr_service.httpx.post")
    def test_envia_imagem_e_retorna_texto(self, post_mock):
        post_mock.return_value = self.resposta_mock(
            dados={
                "OCRExitCode": 1,
                "IsErroredOnProcessing": False,
                "ParsedResults": [
                    {"FileParseExitCode": 1, "ParsedText": "  Texto reconhecido.  "}
                ],
            }
        )

        texto = extrair_texto_documento(
            SimpleUploadedFile("redacao.png", b"imagem", content_type="image/png")
        )

        chamada = post_mock.call_args.kwargs
        self.assertEqual(chamada["headers"], {"apikey": "chave-teste"})
        self.assertEqual(chamada["files"]["file"][1], b"imagem")
        self.assertEqual(chamada["data"]["OCREngine"], "3")
        self.assertEqual(chamada["data"]["language"], "auto")
        self.assertEqual(chamada["timeout"], 60)
        self.assertEqual(texto, "Texto reconhecido.")

    @patch("redacoes.services.ocr_service.httpx.post")
    def test_sucesso_parcial_ignora_resultado_com_erro(self, post_mock):
        post_mock.return_value = self.resposta_mock(
            dados={
                "OCRExitCode": 2,
                "IsErroredOnProcessing": False,
                "ParsedResults": [
                    {"FileParseExitCode": 1, "ParsedText": "Página válida."},
                    {"FileParseExitCode": -20, "ParsedText": None},
                ],
            }
        )

        texto = extrair_texto_documento(SimpleUploadedFile("redacao.png", b"imagem"))

        self.assertEqual(texto, "Página válida.")

    @patch("redacoes.services.ocr_service.httpx.post")
    def test_documento_sem_texto_retorna_string_vazia(self, post_mock):
        post_mock.return_value = self.resposta_mock(
            dados={
                "OCRExitCode": 1,
                "IsErroredOnProcessing": False,
                "ParsedResults": [{"FileParseExitCode": 1, "ParsedText": "   "}],
            }
        )

        texto = extrair_texto_documento(SimpleUploadedFile("redacao.png", b"imagem"))

        self.assertEqual(texto, "")

    @patch("redacoes.services.ocr_service.httpx.post")
    def test_chave_recusada_recebe_erro_especifico(self, post_mock):
        post_mock.return_value = self.resposta_mock(status=403)

        with self.assertRaises(OCRAuthenticationError):
            extrair_texto_documento(SimpleUploadedFile("redacao.png", b"imagem"))

    @patch("redacoes.services.ocr_service.httpx.post")
    def test_cota_esgotada_recebe_erro_especifico(self, post_mock):
        post_mock.return_value = self.resposta_mock(status=429)

        with self.assertRaises(OCRQuotaError):
            extrair_texto_documento(SimpleUploadedFile("redacao.png", b"imagem"))

    @patch("redacoes.services.ocr_service.httpx.post")
    def test_timeout_recebe_erro_especifico(self, post_mock):
        post_mock.side_effect = httpx.ReadTimeout("demorou")

        with self.assertRaises(OCRTimeoutError):
            extrair_texto_documento(SimpleUploadedFile("redacao.png", b"imagem"))

    @patch("redacoes.services.ocr_service.httpx.post")
    def test_json_invalido_e_rejeitado(self, post_mock):
        resposta = self.resposta_mock()
        resposta.json.side_effect = ValueError("detalhe interno")
        post_mock.return_value = resposta

        with self.assertRaises(OCRResponseError):
            extrair_texto_documento(SimpleUploadedFile("redacao.png", b"imagem"))

    @patch("redacoes.services.ocr_service.httpx.post")
    def test_falha_informada_no_json_e_rejeitada(self, post_mock):
        post_mock.return_value = self.resposta_mock(
            dados={
                "OCRExitCode": 3,
                "IsErroredOnProcessing": True,
                "ErrorMessage": "detalhe interno",
            }
        )

        with self.assertRaises(OCRResponseError) as contexto:
            extrair_texto_documento(SimpleUploadedFile("redacao.png", b"imagem"))

        self.assertNotIn("detalhe interno", str(contexto.exception))

    @patch("redacoes.services.ocr_service.httpx.post")
    def test_sucesso_parcial_sem_pagina_valida_e_rejeitado(self, post_mock):
        post_mock.return_value = self.resposta_mock(
            dados={
                "OCRExitCode": 2,
                "IsErroredOnProcessing": False,
                "ParsedResults": [
                    {"FileParseExitCode": -20, "ParsedText": None}
                ],
            }
        )

        with self.assertRaises(OCRResponseError):
            extrair_texto_documento(SimpleUploadedFile("redacao.png", b"imagem"))

    @patch("redacoes.services.ocr_service.httpx.post")
    def test_chave_ausente_falha_antes_da_rede(self, post_mock):
        with patch.dict(os.environ, {"OCR_SPACE_API_KEY": ""}):
            with self.assertRaises(OCRConfigurationError):
                extrair_texto_documento(SimpleUploadedFile("redacao.png", b"imagem"))

        post_mock.assert_not_called()

    def test_imagem_ausente_e_rejeitada(self):
        with self.assertRaisesRegex(ValueError, "imagem"):
            extrair_texto_documento(None)
