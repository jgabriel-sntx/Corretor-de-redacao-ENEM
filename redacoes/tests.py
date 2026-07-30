from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .models import Redacao


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
            follow=True,
        )

        self.assertRedirects(response, self.url)
        self.assertEqual(Redacao.objects.count(), 1)
        self.assertContains(response, "Redação enviada com sucesso")

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
