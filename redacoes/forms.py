from django import forms

from .models import Redacao
from .services.prompt_builder import NOMES_COMPETENCIAS, NOTAS_VALIDAS


class RedacaoForm(forms.ModelForm):
    class Meta:
        model = Redacao
        fields = ["tema", "imagem", "texto_original"]
        widgets = {
            "tema": forms.TextInput(
                attrs={
                    "class": "form-control form-control-lg",
                    "placeholder": "Ex.: Desafios para a valorização da educação",
                    "autocomplete": "off",
                }
            ),
            "imagem": forms.ClearableFileInput(
                attrs={
                    "class": "form-control",
                    "accept": "image/*",
                    "aria-describedby": "imagem-ajuda",
                }
            ),
            "texto_original": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 10,
                    "placeholder": "Digite ou cole sua redação aqui...",
                    "aria-describedby": "texto-ajuda",
                }
            ),
        }
        help_texts = {
            "imagem": "Envie uma imagem de até 1 MB.",
            "texto_original": "Informe o texto ou envie uma imagem.",
        }


class RevisaoTranscricaoForm(forms.ModelForm):
    texto_revisado = forms.CharField(
        label="Texto revisado",
        required=True,
        strip=True,
        widget=forms.Textarea(
            attrs={
                "class": "form-control review-textarea",
                "rows": 18,
                "placeholder": "Revise a transcrição antes de confirmar...",
                "aria-describedby": "revisao-ajuda",
            }
        ),
        error_messages={"required": "Revise e confirme um texto não vazio."},
    )

    class Meta:
        model = Redacao
        fields = ["texto_revisado"]


NOTA_CHOICES = [(str(nota), str(nota)) for nota in sorted(NOTAS_VALIDAS)]
SIM_NAO_CHOICES = [("", "Não verificável"), ("sim", "Sim"), ("nao", "Não")]


class CorrigirRedacaoForm(forms.Form):
    """Permite ao professor alterar a correção estruturada da IA e comentar."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for numero in range(1, 6):
            nome_competencia = NOMES_COMPETENCIAS[numero]
            self.fields[f"competencia_{numero}_nota"] = forms.ChoiceField(
                label=f"Nota — Competência {numero}",
                choices=NOTA_CHOICES,
                widget=forms.Select(attrs={"class": "form-select"}),
                help_text=nome_competencia,
            )
            self.fields[f"competencia_{numero}_justificativa"] = forms.CharField(
                label="Justificativa",
                widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            )
            self.fields[f"competencia_{numero}_pontos_fortes"] = forms.CharField(
                label="Pontos fortes",
                required=False,
                widget=forms.Textarea(attrs={"class": "form-control", "rows": 2}),
                help_text="Um item por linha.",
            )
            self.fields[f"competencia_{numero}_melhorias"] = forms.CharField(
                label="Como melhorar",
                required=False,
                widget=forms.Textarea(attrs={"class": "form-control", "rows": 2}),
                help_text="Um item por linha.",
            )

        self.fields["diagnostico_geral"] = forms.CharField(
            label="Diagnóstico geral",
            widget=forms.Textarea(attrs={"class": "form-control", "rows": 4}),
        )
        self.fields["prioridades_melhoria"] = forms.CharField(
            label="Prioridades de melhoria",
            required=False,
            widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            help_text="Um item por linha.",
        )
        self.fields["pi_presente"] = forms.ChoiceField(
            label="Proposta de intervenção presente",
            choices=SIM_NAO_CHOICES,
            required=False,
            widget=forms.Select(attrs={"class": "form-select"}),
        )
        self.fields["pi_agente"] = forms.CharField(
            label="Agente",
            required=False,
            widget=forms.TextInput(attrs={"class": "form-control"}),
        )
        self.fields["pi_acao"] = forms.CharField(
            label="Ação",
            required=False,
            widget=forms.TextInput(attrs={"class": "form-control"}),
        )
        self.fields["pi_meio_modo"] = forms.CharField(
            label="Meio/modo",
            required=False,
            widget=forms.TextInput(attrs={"class": "form-control"}),
        )
        self.fields["pi_finalidade"] = forms.CharField(
            label="Finalidade",
            required=False,
            widget=forms.TextInput(attrs={"class": "form-control"}),
        )
        self.fields["pi_detalhamento"] = forms.CharField(
            label="Detalhamento",
            required=False,
            widget=forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        )
        self.fields["pi_direitos_humanos"] = forms.ChoiceField(
            label="Respeita os direitos humanos",
            choices=SIM_NAO_CHOICES,
            required=False,
            widget=forms.Select(attrs={"class": "form-select"}),
        )
        self.fields["comentario_professor"] = forms.CharField(
            label="Comentário do professor",
            required=False,
            widget=forms.Textarea(attrs={"class": "form-control", "rows": 5}),
            help_text="Visível para o aluno junto ao resultado.",
        )

    def initial_a_partir_de(self, redacao):
        resultado = redacao.resultado_json or {}
        inicial = {"comentario_professor": redacao.comentario_professor}

        if resultado.get("avaliacao_possivel"):
            for competencia in resultado.get("competencias", []):
                numero = competencia.get("numero")
                if numero not in range(1, 6):
                    continue
                inicial[f"competencia_{numero}_nota"] = str(competencia.get("nota"))
                inicial[f"competencia_{numero}_justificativa"] = competencia.get(
                    "justificativa", ""
                )
                inicial[f"competencia_{numero}_pontos_fortes"] = "\n".join(
                    competencia.get("pontos_fortes") or []
                )
                inicial[f"competencia_{numero}_melhorias"] = "\n".join(
                    competencia.get("melhorias") or []
                )

            inicial["diagnostico_geral"] = resultado.get("diagnostico_geral", "")
            inicial["prioridades_melhoria"] = "\n".join(
                resultado.get("prioridades_melhoria") or []
            )

            intervencao = resultado.get("proposta_intervencao") or {}
            inicial["pi_presente"] = _bool_para_escolha(intervencao.get("presente"))
            inicial["pi_agente"] = intervencao.get("agente") or ""
            inicial["pi_acao"] = intervencao.get("acao") or ""
            inicial["pi_meio_modo"] = intervencao.get("meio_modo") or ""
            inicial["pi_finalidade"] = intervencao.get("finalidade") or ""
            inicial["pi_detalhamento"] = intervencao.get("detalhamento") or ""
            inicial["pi_direitos_humanos"] = _bool_para_escolha(
                intervencao.get("respeita_direitos_humanos")
            )

        self.initial = inicial
        return self

    def aplicar_ao_resultado(self, resultado_json):
        """Retorna uma cópia de resultado_json com os valores do professor aplicados."""
        resultado = dict(resultado_json or {})
        dados = self.cleaned_data

        competencias = []
        notas = []
        for numero in range(1, 6):
            nota = int(dados[f"competencia_{numero}_nota"])
            notas.append(nota)
            competencias.append(
                {
                    "numero": numero,
                    "nome": NOMES_COMPETENCIAS[numero],
                    "nota": nota,
                    "justificativa": dados[f"competencia_{numero}_justificativa"].strip(),
                    "evidencias": _evidencias_originais(resultado, numero),
                    "pontos_fortes": _linhas(dados[f"competencia_{numero}_pontos_fortes"]),
                    "melhorias": _linhas(dados[f"competencia_{numero}_melhorias"]),
                }
            )

        resultado["competencias"] = competencias
        resultado["nota_total"] = sum(notas)
        resultado["diagnostico_geral"] = dados["diagnostico_geral"].strip()
        resultado["prioridades_melhoria"] = _linhas(dados["prioridades_melhoria"])

        intervencao_original = resultado.get("proposta_intervencao") or {}
        resultado["proposta_intervencao"] = {
            "presente": _escolha_para_bool(dados["pi_presente"]),
            "agente": dados["pi_agente"].strip() or None,
            "acao": dados["pi_acao"].strip() or None,
            "meio_modo": dados["pi_meio_modo"].strip() or None,
            "finalidade": dados["pi_finalidade"].strip() or None,
            "detalhamento": dados["pi_detalhamento"].strip() or None,
            "respeita_direitos_humanos": _escolha_para_bool(dados["pi_direitos_humanos"]),
            "evidencias": intervencao_original.get("evidencias", []),
        }

        return resultado


def _linhas(texto):
    return [linha.strip() for linha in (texto or "").splitlines() if linha.strip()]


def _bool_para_escolha(valor):
    if valor is True:
        return "sim"
    if valor is False:
        return "nao"
    return ""


def _escolha_para_bool(valor):
    if valor == "sim":
        return True
    if valor == "nao":
        return False
    return None


def _evidencias_originais(resultado, numero):
    for competencia in resultado.get("competencias", []) or []:
        if competencia.get("numero") == numero:
            return competencia.get("evidencias", [])
    return []
