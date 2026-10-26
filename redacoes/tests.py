from unittest import mock

from django.test import TestCase
from django.urls import reverse

from contas.models import Turma, Usuario

from .forms import CorrigirRedacaoForm
from .models import Redacao
from .services.prompt_builder import NOMES_COMPETENCIAS


def _resultado_ia(nota=160):
    return {
        "schema_version": "1.0",
        "avaliacao_possivel": True,
        "motivo_impedimento": None,
        "situacoes_nota_zero": [],
        "proposta_intervencao": {
            "presente": True,
            "agente": "Governo",
            "acao": "criar campanhas",
            "meio_modo": "anúncios",
            "finalidade": "reduzir o problema",
            "detalhamento": None,
            "respeita_direitos_humanos": True,
            "evidencias": [],
        },
        "competencias": [
            {
                "numero": numero,
                "nome": nome,
                "nota": nota,
                "justificativa": "Justificativa da IA.",
                "evidencias": [],
                "pontos_fortes": [],
                "melhorias": [],
            }
            for numero, nome in NOMES_COMPETENCIAS.items()
        ],
        "nota_total": nota * 5,
        "diagnostico_geral": "Diagnóstico da IA.",
        "prioridades_melhoria": [],
        "confianca": "media",
        "limitacoes": [],
    }


class CorrecaoProfessorTests(TestCase):
    def setUp(self):
        self.professor = Usuario.objects.create_user(
            "prof@example.com", "senha-teste-123", tipo=Usuario.Tipo.PROFESSOR
        )
        turma = Turma.objects.create(professor=self.professor, nome="Turma")
        self.aluno = Usuario.objects.create_user(
            "aluno@example.com", "senha-teste-123", tipo=Usuario.Tipo.ALUNO, turma=turma
        )
        self.redacao = Redacao.objects.create(
            aluno=self.aluno,
            tema="Tema de teste",
            texto_original="Texto " * 80,
            texto_revisado="Texto " * 80,
            resultado_json=_resultado_ia(160),
        )

    def _dados_do_professor(self, nota):
        form = CorrigirRedacaoForm()
        form.initial_a_partir_de(self.redacao)
        dados = {chave: valor for chave, valor in form.initial.items()}
        for numero in range(1, 6):
            dados[f"competencia_{numero}_nota"] = str(nota)
        dados["comentario_professor"] = "Bom trabalho."
        return dados

    def test_resultado_final_prioriza_o_professor(self):
        self.assertEqual(self.redacao.resultado_final["nota_total"], 800)
        self.redacao.resultado_professor = _resultado_ia(200)
        self.assertEqual(self.redacao.resultado_final["nota_total"], 1000)

    def test_professor_salva_sem_apagar_a_avaliacao_da_ia(self):
        self.client.force_login(self.professor)
        url = reverse("redacoes:professor_corrigir_redacao", args=[self.redacao.pk])

        formulario = self.client.get(url)
        self.assertEqual(formulario.context["form"].initial["competencia_1_nota"], "160")

        resposta = self.client.post(url, self._dados_do_professor(200))
        self.assertEqual(resposta.status_code, 302)

        self.redacao.refresh_from_db()
        self.assertEqual(self.redacao.resultado_json["nota_total"], 800)
        self.assertEqual(self.redacao.resultado_professor["nota_total"], 1000)
        self.assertEqual(self.redacao.resultado_final["nota_total"], 1000)
        self.assertEqual(self.redacao.corrigido_por, self.professor)

    def test_professor_reabre_a_propria_correcao_como_base(self):
        self.redacao.resultado_professor = _resultado_ia(200)
        self.redacao.save()
        self.client.force_login(self.professor)
        url = reverse("redacoes:professor_corrigir_redacao", args=[self.redacao.pk])
        formulario = self.client.get(url)
        self.assertEqual(formulario.context["form"].initial["competencia_1_nota"], "200")

    def test_nova_correcao_da_ia_nao_altera_a_do_professor(self):
        self.redacao.resultado_professor = _resultado_ia(200)
        self.redacao.save()
        self.client.force_login(self.aluno)

        with mock.patch("redacoes.views.avaliar_redacao", return_value=_resultado_ia(120)):
            self.client.post(
                reverse("redacoes:revisao", args=[self.redacao.pk]),
                {"texto_revisado": "Texto novo " * 40},
            )

        self.redacao.refresh_from_db()
        self.assertEqual(self.redacao.resultado_json["nota_total"], 600)
        self.assertEqual(self.redacao.resultado_professor["nota_total"], 1000)
        resposta = self.client.get(reverse("redacoes:resultado", args=[self.redacao.pk]))
        self.assertEqual(resposta.context["resultado"]["nota_total"], 1000)
