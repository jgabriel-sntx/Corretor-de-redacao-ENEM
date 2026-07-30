from django import forms

from .models import Redacao


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
            "imagem": "Envie uma imagem de até 10 MB.",
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
