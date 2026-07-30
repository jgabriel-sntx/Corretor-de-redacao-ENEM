from io import BytesIO
from datetime import timedelta
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from google.api_core.exceptions import GoogleAPICallError, ResourceExhausted
from google.auth.exceptions import DefaultCredentialsError
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from django.urls import reverse
from PIL import Image

from .forms import RedacaoForm, RevisaoTranscricaoForm
from .models import Redacao
from .services.gemini_service import GeminiServiceError
from .services.vision_service import (
    VisionCredentialsError,
    VisionQuotaError,
    VisionServiceError,
    extrair_texto_documento,
)
from .validators import TAMANHO_MAXIMO_IMAGEM, validar_tamanho_imagem


def criar_imagem_png():
    conteudo = BytesIO()
    Image.new("RGB", (10, 10), "white").save(conteudo, format="PNG")
    return SimpleUploadedFile(
        "redacao.png",
        conteudo.getvalue(),
        content_type="image/png",
    )


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

        with self.assertRaisesRegex(ValidationError, "10 MB"):
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
    def test_envio_por_texto_nao_chama_google_vision(self, mock_ocr):
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
        "redacoes.views.avaliar_redacao_com_gemini",
        return_value={"schema_version": "1.0", "nota_total": 800},
    )
    def test_confirmar_salva_texto_revisado_sem_alterar_ocr(self, mock_gemini):
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
        mock_gemini.assert_called_once_with(self.redacao.tema, texto_corrigido)
        self.assertRedirects(
            response,
            self.url,
            fetch_redirect_response=False,
        )

    @patch(
        "redacoes.views.avaliar_redacao_com_gemini",
        return_value={"schema_version": "1.0"},
    )
    def test_confirmacao_exibe_mensagem_apos_redirect(self, mock_gemini):
        response = self.client.post(
            self.url,
            {"texto_revisado": "Transcrição confirmada."},
            follow=True,
        )

        self.assertRedirects(response, self.url)
        self.assertContains(response, "avaliação estruturada concluída")

    @patch(
        "redacoes.views.avaliar_redacao_com_gemini",
        side_effect=GeminiServiceError("Falha controlada do Gemini."),
    )
    def test_falha_do_gemini_preserva_revisao_e_limpa_resultado_antigo(
        self, mock_gemini
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
        self.assertContains(response, "Falha controlada do Gemini")

    def test_texto_revisado_vazio_nao_e_salvo(self):
        response = self.client.post(self.url, {"texto_revisado": "   "})

        self.redacao.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.redacao.texto_revisado, "")
        self.assertContains(response, "Revise e confirme um texto não vazio")

    @patch("redacoes.views.avaliar_redacao_com_gemini")
    def test_texto_invalido_nao_chama_gemini(self, mock_gemini):
        self.client.post(self.url, {"texto_revisado": "   "})

        mock_gemini.assert_not_called()

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
        chamada = cliente_mock.return_value.document_text_detection.call_args
        self.assertEqual(chamada.kwargs["timeout"], 30)
        self.assertEqual(chamada.kwargs["image"].content, b"conteudo-da-imagem")
        self.assertEqual(texto, "Primeira linha.\nSegunda linha.")

    @patch("redacoes.services.vision_service.vision.ImageAnnotatorClient")
    def test_documento_sem_texto_retorna_string_vazia(self, cliente_mock):
        resposta = cliente_mock.return_value.document_text_detection.return_value
        resposta.error.message = ""
        resposta.full_text_annotation.text = "   "

        texto = extrair_texto_documento(
            SimpleUploadedFile("redacao.png", b"conteudo-da-imagem")
        )

        self.assertEqual(texto, "")

    def test_imagem_ausente_e_rejeitada_antes_do_cliente(self):
        with self.assertRaisesRegex(ValueError, "imagem"):
            extrair_texto_documento(None)

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

    @patch("redacoes.services.vision_service.vision.ImageAnnotatorClient")
    def test_falha_generica_da_api_recebe_mensagem_segura(self, cliente_mock):
        cliente_mock.return_value.document_text_detection.side_effect = (
            GoogleAPICallError("detalhe interno")
        )

        with self.assertRaises(VisionServiceError) as contexto:
            extrair_texto_documento(
                SimpleUploadedFile("redacao.png", b"conteudo-da-imagem")
            )

        self.assertNotIn("detalhe interno", str(contexto.exception))
