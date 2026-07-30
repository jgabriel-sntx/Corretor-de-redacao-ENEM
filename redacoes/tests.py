from io import BytesIO
from tempfile import TemporaryDirectory
from unittest.mock import patch

from google.api_core.exceptions import ResourceExhausted
from google.auth.exceptions import DefaultCredentialsError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from .models import Redacao
from .services.vision_service import (
    VisionCredentialsError,
    VisionQuotaError,
    VisionServiceError,
    extrair_texto_documento,
)


def criar_imagem_png():
    conteudo = BytesIO()
    Image.new("RGB", (10, 10), "white").save(conteudo, format="PNG")
    return SimpleUploadedFile(
        "redacao.png",
        conteudo.getvalue(),
        content_type="image/png",
    )


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
        return_value="Texto reconhecido pelo Google Vision.",
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
            "Texto reconhecido pelo Google Vision.",
        )
        self.assertEqual(redacao.status, Redacao.Status.CONCLUIDA)
        self.assertRedirects(
            response,
            reverse("redacoes:revisao", kwargs={"pk": redacao.pk}),
            fetch_redirect_response=False,
        )

    @patch(
        "redacoes.views.extrair_texto_documento",
        side_effect=VisionServiceError("Falha controlada no OCR."),
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
            texto_original="Primeiro parágrafo.\n\nSegundo parágrafo.",
        )
        self.url = reverse("redacoes:revisao", kwargs={"pk": self.redacao.pk})

    def test_revisao_exibe_dados_salvos_sem_processamento(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.redacao.tema)
        self.assertContains(response, "Primeiro parágrafo")
        self.assertContains(response, "Enviada")
        self.assertContains(response, "Sem correção por IA")
        self.assertNotContains(response, "texto_transcrito")
        self.assertNotContains(response, "resultado_json")

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


class VisionServiceTests(TestCase):
    @patch("redacoes.services.vision_service.vision.ImageAnnotatorClient")
    def test_document_text_detection_retorna_texto_completo(self, cliente_mock):
        resposta = cliente_mock.return_value.document_text_detection.return_value
        resposta.error.message = ""
        resposta.full_text_annotation.text = "  Primeira linha.\nSegunda linha.  "

        texto = extrair_texto_documento(
            SimpleUploadedFile("redacao.png", b"conteudo-da-imagem")
        )

        cliente_mock.return_value.document_text_detection.assert_called_once()
        self.assertEqual(texto, "Primeira linha.\nSegunda linha.")

    @patch("redacoes.services.vision_service.vision.ImageAnnotatorClient")
    def test_erro_retornado_pela_api_e_convertido(self, cliente_mock):
        resposta = cliente_mock.return_value.document_text_detection.return_value
        resposta.error.message = "imagem inválida"

        with self.assertRaises(VisionServiceError):
            extrair_texto_documento(
                SimpleUploadedFile("redacao.png", b"conteudo-da-imagem")
            )

    @patch(
        "redacoes.services.vision_service.vision.ImageAnnotatorClient",
        side_effect=DefaultCredentialsError("sem credenciais"),
    )
    def test_credenciais_ausentes_recebem_erro_especifico(self, cliente_mock):
        with self.assertRaises(VisionCredentialsError):
            extrair_texto_documento(
                SimpleUploadedFile("redacao.png", b"conteudo-da-imagem")
            )

    @patch("redacoes.services.vision_service.vision.ImageAnnotatorClient")
    def test_cota_esgotada_recebe_erro_especifico(self, cliente_mock):
        cliente_mock.return_value.document_text_detection.side_effect = (
            ResourceExhausted("cota esgotada")
        )

        with self.assertRaises(VisionQuotaError):
            extrair_texto_documento(
                SimpleUploadedFile("redacao.png", b"conteudo-da-imagem")
            )
