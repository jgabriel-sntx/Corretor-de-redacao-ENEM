from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .forms import RedacaoForm, RevisaoTranscricaoForm
from .models import Redacao
from .services.gemini_service import GeminiServiceError, avaliar_redacao_com_gemini
from .services.vision_service import VisionServiceError, extrair_texto_documento


@require_http_methods(["GET", "POST"])
def pagina_inicial(request):
    if request.method == "POST":
        form = RedacaoForm(request.POST, request.FILES)
        if form.is_valid():
            redacao = form.save()

            if redacao.imagem:
                redacao.status = Redacao.Status.PROCESSANDO
                redacao.save(update_fields=["status", "atualizada_em"])

                try:
                    redacao.texto_transcrito = extrair_texto_documento(
                        redacao.imagem
                    )
                except VisionServiceError as erro:
                    redacao.status = Redacao.Status.ERRO
                    messages.error(request, str(erro))
                else:
                    redacao.status = Redacao.Status.CONCLUIDA
                    if redacao.texto_transcrito:
                        messages.success(
                            request,
                            "OCR concluído. Confira o texto extraído abaixo.",
                        )
                    else:
                        messages.warning(
                            request,
                            "O OCR foi concluído, mas nenhum texto foi reconhecido na imagem.",
                        )

                redacao.save(
                    update_fields=[
                        "texto_transcrito",
                        "status",
                        "atualizada_em",
                    ]
                )
            else:
                messages.success(
                    request,
                    "Redação salva com sucesso. Nenhum OCR foi necessário.",
                )

            return redirect("redacoes:revisao", pk=redacao.pk)

        messages.error(
            request,
            "Não foi possível enviar a redação. Revise os campos destacados.",
        )
    else:
        form = RedacaoForm()

    return render(request, "redacoes/inicio.html", {"form": form})


@require_http_methods(["GET", "POST"])
def revisar_redacao(request, pk):
    redacao = get_object_or_404(Redacao, pk=pk)

    if request.method == "POST":
        form = RevisaoTranscricaoForm(request.POST, instance=redacao)
        if form.is_valid():
            redacao = form.save(commit=False)
            redacao.resultado_json = {}
            redacao.save(
                update_fields=[
                    "texto_revisado",
                    "resultado_json",
                    "atualizada_em",
                ]
            )

            try:
                resultado = avaliar_redacao_com_gemini(
                    redacao.tema,
                    redacao.texto_revisado,
                )
            except GeminiServiceError as erro:
                messages.error(
                    request,
                    f"Texto revisado salvo, mas a avaliação não foi concluída: {erro}",
                )
            else:
                redacao.resultado_json = resultado
                redacao.save(update_fields=["resultado_json", "atualizada_em"])
                messages.success(
                    request,
                    "Texto revisado salvo e avaliação estruturada concluída.",
                )

            return redirect("redacoes:revisao", pk=redacao.pk)

        messages.error(
            request,
            "Não foi possível confirmar o texto. Revise o campo destacado.",
        )
    else:
        form = RevisaoTranscricaoForm(
            instance=redacao,
            initial={
                "texto_revisado": redacao.texto_revisado
                or redacao.texto_transcrito
            },
        )

    return render(
        request,
        "redacoes/revisao.html",
        {"redacao": redacao, "form": form},
    )
